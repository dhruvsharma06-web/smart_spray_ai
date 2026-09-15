"""
RAG / Knowledge Retrieval Package.
Provides retrieval-augmented access to verified agricultural knowledge.
"""

from .knowledge_base import KnowledgeBase, get_knowledge_base

__all__ = ["KnowledgeBase", "get_knowledge_base"]
