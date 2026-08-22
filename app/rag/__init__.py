"""RAG-модуль: индексация учебников и поиск релевантных фрагментов."""

from app.rag.knowledge import KnowledgeBase, get_knowledge_base

__all__ = ["KnowledgeBase", "get_knowledge_base"]
