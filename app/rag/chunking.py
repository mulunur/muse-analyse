"""Разбиение текста на перекрывающиеся фрагменты."""

from __future__ import annotations

import re
from typing import Any


def _split_into_paragraphs(text: str) -> list[str]:
    """Делит текст на абзацы, сохраняя смысловые блоки."""
    paragraphs = re.split(r"\n\s*\n+", text)
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_pages(
    pages: list[dict[str, Any]],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
    source: str = "",
) -> list[dict[str, Any]]:
    """
    Разбивает страницы PDF на чанки с перекрытием.

    Стратегия: объединяем абзацы, пока не достигнем chunk_size;
    при переполнении начинаем новый чанк с overlap из предыдущего.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size должен быть больше нуля")

    effective_overlap = min(max(chunk_overlap, 0), chunk_size - 1)
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for page_data in pages:
        page_num = page_data["page"]
        paragraphs = _split_into_paragraphs(str(page_data["text"]))

        buffer = ""
        for para in paragraphs:
            candidate = f"{buffer}\n\n{para}".strip() if buffer else para

            if len(candidate) <= chunk_size:
                buffer = candidate
                continue

            if buffer:
                chunks.append(
                    {
                        "id": f"{source}_p{page_num}_c{chunk_index}",
                        "text": buffer,
                        "page": page_num,
                        "source": source,
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1

                if effective_overlap > 0 and len(buffer) > effective_overlap:
                    buffer = buffer[-effective_overlap:] + "\n\n" + para
                else:
                    buffer = para
            else:
                # Один абзац длиннее chunk_size — режем по предложениям
                sentences = re.split(r"(?<=[.!?…])\s+", para)
                buffer = ""
                for sentence in sentences:
                    candidate = f"{buffer} {sentence}".strip() if buffer else sentence
                    if len(candidate) <= chunk_size:
                        buffer = candidate
                    else:
                        if buffer:
                            chunks.append(
                                {
                                    "id": f"{source}_p{page_num}_c{chunk_index}",
                                    "text": buffer,
                                    "page": page_num,
                                    "source": source,
                                    "chunk_index": chunk_index,
                                }
                            )
                            chunk_index += 1
                        buffer = sentence

        if buffer.strip():
            chunks.append(
                {
                    "id": f"{source}_p{page_num}_c{chunk_index}",
                    "text": buffer.strip(),
                    "page": page_num,
                    "source": source,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1

    bounded_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        text = chunk["text"]
        if len(text) <= chunk_size:
            bounded_chunks.append(chunk)
            continue

        step = chunk_size - effective_overlap
        for split_index, start in enumerate(range(0, len(text), step)):
            split_chunk = dict(chunk)
            split_chunk["id"] = f"{chunk['id']}_s{split_index}"
            split_chunk["text"] = text[start : start + chunk_size]
            bounded_chunks.append(split_chunk)

    return bounded_chunks
