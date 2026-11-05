"""RAG module: indexes textbooks and finds the passages that matter."""

from app.rag.knowledge import KnowledgeBase, get_knowledge_base

__all__ = ["KnowledgeBase", "get_knowledge_base"]
