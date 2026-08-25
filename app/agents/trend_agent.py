"""Агент практического рыночного контекста."""

from __future__ import annotations

from typing import Any

from app.agents.llm import ask_llm, parse_json_response
from app.agents.state import GrowthState, TrendContext


def _genre_hint(state: GrowthState) -> str:
    """Даёт поиску осторожную метку без попытки угадать жанр как факт."""
    materials = " ".join(state.artist_materials).lower()
    for genre in ("pop", "rock", "jazz", "electronic", "hip-hop", "indie", "folk"):
        if genre in materials:
            return genre
    if state.audio_features:
        energy = state.audio_features.energy
        return "энергичная независимая музыка" if energy >= 0.6 else "созерцательная независимая музыка"
    return "независимая музыка"


def trend_agent(state: GrowthState) -> dict[str, TrendContext]:
    """Делает до двух запросов Tavily и отделяет рынок от художественного голоса."""
    urls: list[str] = []
    search_texts: list[str] = []
    try:
        from tavily import TavilyClient

        import os

        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        genre = _genre_hint(state)
        for query in (f"плейлисты {genre} активные кураторы 2026", f"похожие артисты {genre} тренды"):
            response = client.search(query=query, max_results=3)
            for result in response.get("results", []):
                search_texts.append(str(result.get("content", "")))
                if result.get("url"):
                    urls.append(str(result["url"]))
    except (ImportError, KeyError, OSError):
        pass

    prompt = (
        "Ты собираешь практический рыночный контекст для независимого артиста: активные плейлисты и форматы контента. "
        "Это НЕ должно влиять на тон или художественный голос артиста, только на логистику: куда и в каком формате питчить. "
        "Верни JSON с полями active_playlists, genre_context_summary, source_urls.\n" + "\n".join(search_texts)
    )
    parsed: Any = parse_json_response(ask_llm(prompt), {})
    context = TrendContext(
        active_playlists=[str(item) for item in parsed.get("active_playlists", [])] if isinstance(parsed, dict) else [],
        genre_context_summary=str(parsed.get("genre_context_summary", "Рыночные данные пока недоступны.")) if isinstance(parsed, dict) else "Рыночные данные пока недоступны.",
        source_urls=list(dict.fromkeys(urls + ([str(item) for item in parsed.get("source_urls", [])] if isinstance(parsed, dict) else []))),
    )
    return {"trend_context": context}