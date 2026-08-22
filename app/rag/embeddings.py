"""Локальные эмбеддинги через sentence-transformers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model_cache: dict[str, "SentenceTransformer"] = {}


def get_embedding_model(model_name: str) -> "SentenceTransformer":
    """Загружает и кэширует модель эмбеддингов."""
    if model_name not in _model_cache:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "Для RAG установите sentence-transformers: pip install sentence-transformers"
            ) from exc

        logger.info("Загрузка модели эмбеддингов: %s", model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)

    return _model_cache[model_name]


def embed_texts(model_name: str, texts: list[str]) -> list[list[float]]:
    """Возвращает эмбеддинги для списка текстов."""
    if not texts:
        return []

    model = get_embedding_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=len(texts) > 50)
    return embeddings.tolist()
