#!/usr/bin/env python3
"""Самый простой eval: прогоняет кейсы через настоящий код проекта и проверяет результат.

Запуск (из корня проекта, с активированным окружением):

    python evals/run_evals.py                 # все кейсы
    python evals/run_evals.py --suite critique
    python evals/run_evals.py --case slow_ballad --repeat 3

Провайдер LLM берётся из обычных настроек (.env или переменные окружения), например:

    LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:latest python evals/run_evals.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# RAG для первого знакомства выключаем: он грузит модель эмбеддингов (~1,4 ГБ)
# и сильно замедляет прогон. Включить: RAG_ENABLED=true python evals/run_evals.py
os.environ.setdefault("RAG_ENABLED", "false")

from evals.cases import CRITIQUE_CASES, REVIEW_CASES  # noqa: E402

SECTIONS = ("summary", "rhythm", "tonality", "production", "verdict")


# --- Проверки (graders) -----------------------------------------------------
# Каждая проверка возвращает (прошла_ли, пояснение). Пояснение показывается,
# когда проверка не прошла — именно оно помогает понять, почему.


def cyrillic_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    cyrillic = [c for c in letters if "а" <= c.lower() <= "я" or c in "ёЁ"]
    return len(cyrillic) / len(letters)


def check_review(review: dict, expect: dict) -> list[tuple[str, bool, str]]:
    text = review.get("full_text", "")
    sections = review.get("sections") or {}
    score = review.get("score")
    checks = []

    # 0. Самая важная проверка: ответил ли именно LLM. Если он упал, код молча
    #    подставляет шаблонный обзор — остальные проверки он бы мог пройти "зря".
    used_llm = review.get("source") != "template" and "llm_error" not in review
    checks.append(("used_llm", used_llm,
                   f"source={review.get('source')!r}, llm_error={review.get('llm_error')!r}"))

    # 1. Все пять разделов на месте и не пустые.
    missing = [s for s in SECTIONS if len(str(sections.get(s, ""))) < 30]
    checks.append(("has_all_sections", not missing, f"пустые или короткие разделы: {missing}"))

    # 2. Оценка в допустимых пределах.
    ok_score = isinstance(score, (int, float)) and 1 <= score <= 10
    checks.append(("score_in_range", ok_score, f"score={score!r}"))

    # 3. Текст по-русски.
    share = cyrillic_share(text)
    checks.append(("is_russian", share >= 0.8, f"доля кириллицы {share:.0%}"))

    # 4. Обзор "опирается на параметры": называет темп примерно как во входе.
    #    Проверка намеренно грубая: ищем любое число в пределах ±5 от нужного.
    if "bpm" in expect:
        numbers = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", text)]
        close = any(abs(n - expect["bpm"]) <= 5 for n in numbers)
        checks.append(("mentions_bpm", close, f"нет числа около {expect['bpm']} BPM"))

    # 5. Не выдумывает громкость, если её не посчитали.
    if expect.get("no_lufs"):
        invented = re.search(r"\d\s*LUFS", text, re.IGNORECASE)
        checks.append(("no_invented_lufs", not invented,
                       f"в тексте есть значение LUFS: {invented.group(0)!r}" if invented else ""))

    return checks


def run_review_case(case: dict) -> tuple[list, dict]:
    from app.review_generator import generate_review

    review = generate_review(case["features"])
    return check_review(review, case.get("expect", {})), review


def run_critique_case(case: dict) -> tuple[list, dict]:
    from app.agents import critique_agent as critique_module
    from app.agents.state import GrowthState, VoiceProfile

    # critique_agent при сбое LLM молча возвращает "проверка пройдена". Чтобы
    # отличить это от настоящего вердикта, подглядываем, вернул ли LLM ответ.
    llm_answered: list[bool] = []
    original = critique_module.invoke_structured

    def spy(*args, **kwargs):
        answer = original(*args, **kwargs)
        llm_answered.append(answer is not None)
        return answer

    critique_module.invoke_structured = spy
    try:
        profile = case["profile"]
        state = GrowthState(
            voice_profile=VoiceProfile(tone=profile["tone"], recurring_themes=profile["themes"],
                                       avoid_list=profile["avoid"]),
            drafts=case["drafts"],
        )
        result = critique_module.critique_agent(state)
    finally:
        critique_module.invoke_structured = original

    got, want = result["critique_passed"], case["expect_passed"]
    checks = [
        ("used_llm", bool(llm_answered) and all(llm_answered), "LLM не ответил, сработал запасной вариант"),
        ("correct_verdict", got == want, f"критик сказал passed={got}, ожидалось {want}"),
    ]
    return checks, {"passed": got, "feedback": result["critique_feedback"]}


# --- Прогон и отчёт ---------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Простейший eval для Muse Analyse")
    parser.add_argument("--suite", choices=["review", "critique", "all"], default="all")
    parser.add_argument("--case", help="id одного кейса (для быстрых экспериментов)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="сколько раз гонять каждый кейс (LLM отвечает по-разному)")
    args = parser.parse_args()

    from app.llm_providers import LLMProviderFactory

    try:
        provider = LLMProviderFactory.get_provider()
    except ValueError as exc:
        print(f"Нет доступного LLM-провайдера: {exc}")
        print("Задайте ключ в .env или запустите Ollama, например:")
        print("  LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:latest python evals/run_evals.py")
        return 2
    print(f"Провайдер: {provider.name} ({provider.model}), RAG: {os.environ['RAG_ENABLED']}\n")

    suites = []
    if args.suite in ("review", "all"):
        suites.append(("обзор", REVIEW_CASES, run_review_case))
    if args.suite in ("critique", "all"):
        suites.append(("критик", CRITIQUE_CASES, run_critique_case))

    records = []
    totals: dict[tuple[str, str], list[bool]] = {}  # (набор, проверка) -> [прошла?, ...]

    for suite_name, cases, runner in suites:
        for case in cases:
            if args.case and case["id"] != args.case:
                continue
            for attempt in range(1, args.repeat + 1):
                started = time.time()
                checks, output = runner(case)
                seconds = time.time() - started

                suffix = f" #{attempt}" if args.repeat > 1 else ""
                print(f"[{suite_name}] {case['id']}{suffix}  ({seconds:.0f} с)")
                for name, ok, detail in checks:
                    print(f"   {'✓' if ok else '✗'} {name}" + ("" if ok else f" — {detail}"))
                    totals.setdefault((suite_name, name), []).append(ok)
                if not all(ok for _, ok, _ in checks):
                    snippet = json.dumps(output, ensure_ascii=False)[:300]
                    print(f"   вывод: {snippet}")

                records.append({
                    "suite": suite_name, "case": case["id"], "attempt": attempt,
                    "seconds": round(seconds, 1), "output": output,
                    "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks],
                })

    if not records:
        print("Ни один кейс не подошёл под фильтры.")
        return 1

    print("\n=== ИТОГО ===")
    for (suite_name, name), results in totals.items():
        print(f"  {suite_name:7} {name:18} {sum(results)}/{len(results)}")
    all_results = [r for results in totals.values() for r in results]
    print(f"\nПройдено проверок: {sum(all_results)} из {len(all_results)} "
          f"({sum(all_results) / len(all_results):.0%})")

    out_dir = ROOT / "evals" / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{provider.name}.json"
    out_path.write_text(json.dumps({"provider": provider.name, "model": provider.model,
                                    "records": records}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"Подробности сохранены: {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
