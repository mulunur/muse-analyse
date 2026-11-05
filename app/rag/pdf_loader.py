"""Extracting text from PDF files."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> list[dict[str, str | int]]:
    """
    Extracts text from a PDF, page by page.

    Returns:
        A list of dicts with the keys page (1-based) and text.
    """
    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise ImportError(
            "Для извлечения текста из PDF установите pymupdf: pip install pymupdf"
        ) from exc

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")

    pages: list[dict[str, str | int]] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                pages.append({"page": i + 1, "text": text})

    logger.info("Извлечено %d страниц из %s", len(pages), pdf_path.name)
    return pages
