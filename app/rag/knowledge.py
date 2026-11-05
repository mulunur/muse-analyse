"""RAG knowledge base: PDF indexing and semantic search."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import (
    KNOWLEDGE_DIR,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_EMBEDDING_MODEL,
    RAG_ENABLED,
    RAG_INDEX_DIR,
    RAG_TOP_K,
)
from app.rag.chunking import chunk_pages
from app.rag.embeddings import embed_texts
from app.rag.pdf_loader import extract_text_from_pdf

logger = logging.getLogger(__name__)

COLLECTION_NAME = "music_theory"


def build_retrieval_query(features: dict[str, Any]) -> str:
    """Builds a search query from the audio-analysis features."""
    rhythm = features.get("rhythm", {})
    tonal = features.get("tonal", {})
    spectral = features.get("spectral", {})
    dynamics = features.get("dynamics", {})

    bpm = rhythm.get("bpm", 0)
    key = tonal.get("key", "?")
    scale = tonal.get("scale", "unknown")
    key_strength = tonal.get("key_strength", 0)
    danceability = tonal.get("danceability")
    energy = features.get("energy", 0.5)
    brightness = spectral.get("spectral_brightness", 0.5)
    dyn_complexity = dynamics.get("dynamic_complexity")

    scale_ru = {"major": "мажор", "minor": "минор"}.get(str(scale).lower(), scale)

    parts = [
        "Теория современной композиции:",
        f"ритм темп {bpm} BPM, метр, пульсация",
        f"тональность {key} {scale_ru}, гармония, лад, аккорды",
        f"сила тональности {key_strength:.0%}",
        f"спектральная яркость {brightness:.2f}, тембр, регистр",
        f"энергия {energy:.2f}, динамика",
    ]

    if danceability is not None:
        parts.append(f"танцевальность {danceability:.2f}, ритмическая структура")
    if dyn_complexity is not None:
        parts.append(f"динамическая сложность {dyn_complexity:.2f}, контраст")

    parts.extend(
        [
            "композиционная форма, фактура, полифония, гомофония",
            "современные приёмы композиции, атonalность, модальность",
        ]
    )

    return ". ".join(parts)


class KnowledgeBase:
    """A ChromaDB index of the study materials."""

    def __init__(
        self,
        *,
        knowledge_dir: Path | None = None,
        index_dir: Path | None = None,
        embedding_model: str | None = None,
        top_k: int | None = None,
    ):
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        self.index_dir = index_dir or RAG_INDEX_DIR
        self.embedding_model = embedding_model or RAG_EMBEDDING_MODEL
        self.top_k = top_k or RAG_TOP_K
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
        except ImportError as exc:
            raise ImportError(
                "Для RAG установите chromadb: pip install chromadb"
            ) from exc

        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.index_dir))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    def list_source_files(self) -> list[Path]:
        """Returns the PDF files in the knowledge directory."""
        if not self.knowledge_dir.exists():
            return []
        return sorted(self.knowledge_dir.glob("*.pdf"))

    def get_status(self) -> dict[str, Any]:
        """Status of the index and its sources."""
        sources = [p.name for p in self.list_source_files()]
        chunk_count = 0
        indexed = False

        try:
            collection = self._get_collection()
            chunk_count = collection.count()
            indexed = chunk_count > 0
        except Exception as exc:
            logger.debug("RAG status check failed: %s", exc)

        return {
            "enabled": RAG_ENABLED,
            "indexed": indexed,
            "chunk_count": chunk_count,
            "sources": sources,
            "knowledge_dir": str(self.knowledge_dir),
            "index_dir": str(self.index_dir),
            "embedding_model": self.embedding_model,
            "top_k": self.top_k,
        }

    def build_index(self, *, force: bool = False) -> dict[str, Any]:
        """
        Indexes every PDF from knowledge_dir.

        Args:
            force: Rebuild the index from scratch.
        """
        pdf_files = self.list_source_files()
        if not pdf_files:
            return {
                "success": False,
                "message": f"PDF не найдены в {self.knowledge_dir}",
                "chunk_count": 0,
                "sources": [],
            }

        collection = self._get_collection()

        if force:
            try:
                self._client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            self._collection = None
            collection = self._get_collection()

        all_chunks: list[dict[str, Any]] = []
        for pdf_path in pdf_files:
            pages = extract_text_from_pdf(pdf_path)
            chunks = chunk_pages(
                pages,
                chunk_size=RAG_CHUNK_SIZE,
                chunk_overlap=RAG_CHUNK_OVERLAP,
                source=pdf_path.stem,
            )
            all_chunks.extend(chunks)
            logger.info("%s: %d чанков", pdf_path.name, len(chunks))

        if not all_chunks:
            return {
                "success": False,
                "message": "Не удалось извлечь текст из PDF",
                "chunk_count": 0,
                "sources": [p.name for p in pdf_files],
            }

        texts = [c["text"] for c in all_chunks]
        ids = [c["id"] for c in all_chunks]
        metadatas = [
            {
                "page": c["page"],
                "source": c["source"],
                "chunk_index": c["chunk_index"],
            }
            for c in all_chunks
        ]

        logger.info("Вычисление эмбеддингов для %d чанков...", len(texts))
        embeddings = embed_texts(self.embedding_model, texts)

        # Remove chunks that are no longer in the current PDFs.
        indexed_ids = set(collection.get(include=[]).get("ids", []))
        current_ids = set(ids)
        stale_ids = indexed_ids - current_ids
        if stale_ids:
            collection.delete(ids=list(stale_ids))

        # ChromaDB upsert, in batches
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            collection.upsert(
                ids=ids[i:end],
                documents=texts[i:end],
                embeddings=embeddings[i:end],
                metadatas=metadatas[i:end],
            )

        return {
            "success": True,
            "message": f"Проиндексировано {len(all_chunks)} чанков",
            "chunk_count": len(all_chunks),
            "sources": [p.name for p in pdf_files],
        }

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Finds the top-k most relevant passages for a query.

        Returns:
            A list of dicts: text, page, source, score, chunk_index.
        """
        k = top_k or self.top_k
        collection = self._get_collection()

        if collection.count() == 0:
            logger.warning("RAG индекс пуст — поиск невозможен")
            return []

        query_embedding = embed_texts(self.embedding_model, [query])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        passages: list[dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances, strict=False):
            passages.append(
                {
                    "text": doc,
                    "page": meta.get("page"),
                    "source": meta.get("source"),
                    "chunk_index": meta.get("chunk_index"),
                    "score": round(1 - dist, 4) if dist is not None else None,
                }
            )

        return passages

    def retrieve_for_features(
        self,
        features: dict[str, Any],
        *,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Finds relevant passages using the audio-analysis features."""
        query = build_retrieval_query(features)
        return self.retrieve(query, top_k=top_k)

    def format_context(self, passages: list[dict[str, Any]]) -> str:
        """Formats the passages that were found for the LLM prompt."""
        if not passages:
            return ""

        blocks = []
        for i, p in enumerate(passages, 1):
            source = p.get("source", "учебник")
            page = p.get("page", "?")
            blocks.append(
                f"[Фрагмент {i} | {source}, стр. {page}]\n{p['text']}"
            )

        return (
            "Справочный материал из учебника по теории современной композиции "
            "(используй для обоснования оценок и терминологии):\n\n"
            + "\n\n---\n\n".join(blocks)
        )


_knowledge_base: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    """The shared (singleton) knowledge base."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
    return _knowledge_base


def retrieve_rag_context(features: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """
    Extracts the RAG context used to generate a review.

    Returns:
        (formatted_context, passages): both are empty if RAG is off or the index is empty.
    """
    if not RAG_ENABLED:
        return "", []

    try:
        kb = get_knowledge_base()
        status = kb.get_status()
        if not status["indexed"]:
            logger.info("RAG включён, но индекс пуст — пропуск retrieval")
            return "", []

        passages = kb.retrieve_for_features(features)
        if not passages:
            return "", []

        context = kb.format_context(passages)
        logger.info("RAG: найдено %d релевантных фрагментов", len(passages))
        return context, passages

    except Exception as exc:
        logger.warning("RAG retrieval ошибка (%s) — продолжаем без контекста", exc)
        return "", []
