#!/usr/bin/env python3
"""CLI для построения/перестроения RAG-индекса учебных материалов."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.rag.knowledge import get_knowledge_base  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Индексация PDF-учебников для RAG (Muse Analyse)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Пересоздать индекс с нуля",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Показать статус индекса без переиндексации",
    )
    args = parser.parse_args()

    kb = get_knowledge_base()

    if args.status:
        status = kb.get_status()
        print("RAG Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        return 0

    pdf_files = kb.list_source_files()
    if not pdf_files:
        logger.error("PDF не найдены в %s", kb.knowledge_dir)
        logger.info("Поместите PDF в data/knowledge/ и повторите")
        return 1

    logger.info("Найдено PDF: %s", ", ".join(p.name for p in pdf_files))
    result = kb.build_index(force=args.force)

    if result["success"]:
        logger.info("✓ %s", result["message"])
        logger.info("  Источники: %s", ", ".join(result["sources"]))
        return 0

    logger.error("✗ %s", result["message"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
