"""
RAG Module - Retrieval Augmented Generation for QA Automation

This module provides RAG capabilities to enhance LLM inference with
retrieved context from canonical sources:
- Step definition patterns
- UI discovery outputs
- XPath locators
- Framework rules

CRITICAL: RAG is used at INFERENCE time only, NOT during training.
The model is trained without RAG; RAG provides runtime grounding.

Usage:
    from rag import get_rag_retriever, RAGRetriever
    
    retriever = get_rag_retriever()
    docs = retriever.retrieve("How to click a button?", top_k=5)
"""

from rag.retriever import RAGRetriever
from rag.context_builder import ContextBuilder
from rag.sources import SourceManager

# Singleton retriever instance
_retriever_instance = None


def get_rag_retriever(force_new: bool = False) -> RAGRetriever:
    """
    Get the RAG retriever singleton.
    
    Args:
        force_new: If True, create a new instance even if one exists
    
    Returns:
        RAGRetriever instance
    """
    global _retriever_instance
    
    if _retriever_instance is None or force_new:
        _retriever_instance = RAGRetriever()
        _retriever_instance.initialize()
    
    return _retriever_instance


def build_context(query: str, max_tokens: int = 1000) -> str:
    """
    Build context string from retrieved documents.
    
    Args:
        query: The query to retrieve context for
        max_tokens: Maximum approximate tokens in context
    
    Returns:
        Formatted context string
    """
    retriever = get_rag_retriever()
    builder = ContextBuilder()
    return builder.build(retriever.retrieve(query), max_tokens=max_tokens)


__all__ = [
    'get_rag_retriever',
    'build_context',
    'RAGRetriever',
    'ContextBuilder',
    'SourceManager',
]
