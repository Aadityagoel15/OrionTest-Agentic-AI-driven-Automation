"""
RAG Retriever - Document Retrieval for Context Injection

This module provides the core retrieval functionality for RAG.
It supports multiple retrieval strategies:
1. Keyword/TF-IDF based (fast, deterministic)
2. Vector-based (semantic, requires embeddings)
3. Hybrid (combines both)

For QA Automation, keyword-based retrieval is often sufficient
because step definitions follow canonical patterns.
"""

import os
import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
import math


class Document:
    """Represents a retrievable document."""
    
    def __init__(
        self,
        content: str,
        source: str,
        doc_type: str,
        metadata: Dict[str, Any] = None
    ):
        self.content = content
        self.source = source
        self.doc_type = doc_type
        self.metadata = metadata or {}
        self.tokens = self._tokenize(content)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for TF-IDF."""
        text = text.lower()
        # Remove special characters but keep underscores (common in code)
        text = re.sub(r'[^\w\s_]', ' ', text)
        return text.split()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for retrieval results."""
        return {
            'content': self.content,
            'source': self.source,
            'doc_type': self.doc_type,
            'metadata': self.metadata
        }


class RAGRetriever:
    """
    RAG Retriever using TF-IDF based keyword matching.
    
    This retriever is optimized for QA automation contexts where:
    - Documents follow canonical patterns
    - Exact keyword matching is often more reliable than semantic
    - Determinism is critical
    """
    
    def __init__(self):
        self.documents: List[Document] = []
        self.idf_scores: Dict[str, float] = {}
        self.doc_term_freq: List[Dict[str, int]] = []
        self._is_initialized = False
    
    def initialize(self):
        """Initialize the retriever by loading all sources."""
        if self._is_initialized:
            return
        
        from rag.sources import SourceManager
        
        manager = SourceManager()
        raw_docs = manager.load_all_sources()
        
        for doc_data in raw_docs:
            doc = Document(
                content=doc_data['content'],
                source=doc_data['source'],
                doc_type=doc_data['doc_type'],
                metadata=doc_data.get('metadata', {})
            )
            self.documents.append(doc)
        
        # Build TF-IDF index
        self._build_index()
        self._is_initialized = True
        
        print(f"[RAG] Initialized with {len(self.documents)} documents")
    
    def _build_index(self):
        """Build TF-IDF index for all documents."""
        # Calculate document frequency for each term
        doc_freq = defaultdict(int)
        self.doc_term_freq = []
        
        for doc in self.documents:
            term_freq = defaultdict(int)
            for token in doc.tokens:
                term_freq[token] += 1
            self.doc_term_freq.append(dict(term_freq))
            
            # Count document frequency
            for token in set(doc.tokens):
                doc_freq[token] += 1
        
        # Calculate IDF scores
        n_docs = len(self.documents)
        for term, df in doc_freq.items():
            self.idf_scores[term] = math.log((n_docs + 1) / (df + 1)) + 1
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        doc_type_filter: str = None,
        min_score: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: The search query
            top_k: Maximum number of documents to return
            doc_type_filter: Optional filter by document type
            min_score: Minimum relevance score threshold
        
        Returns:
            List of document dictionaries sorted by relevance
        """
        if not self._is_initialized:
            self.initialize()
        
        # Tokenize query
        query_tokens = Document("", "", "").tokens  # Dummy for tokenization
        query_lower = query.lower()
        query_tokens = re.sub(r'[^\w\s_]', ' ', query_lower).split()
        
        # Calculate query term frequency
        query_tf = defaultdict(int)
        for token in query_tokens:
            query_tf[token] += 1
        
        # Score each document
        scores = []
        for i, doc in enumerate(self.documents):
            # Apply type filter if specified
            if doc_type_filter and doc.doc_type != doc_type_filter:
                continue
            
            score = self._calculate_score(query_tf, i)
            
            # Boost exact matches
            if any(token in doc.content.lower() for token in query_tokens if len(token) > 3):
                score *= 1.2
            
            if score >= min_score:
                scores.append((score, i))
        
        # Sort by score descending
        scores.sort(reverse=True, key=lambda x: x[0])
        
        # Return top-k results
        results = []
        for score, idx in scores[:top_k]:
            doc_dict = self.documents[idx].to_dict()
            doc_dict['relevance_score'] = score
            results.append(doc_dict)
        
        return results
    
    def _calculate_score(self, query_tf: Dict[str, int], doc_idx: int) -> float:
        """Calculate TF-IDF similarity score."""
        doc_tf = self.doc_term_freq[doc_idx]
        
        score = 0.0
        for term, tf in query_tf.items():
            if term in doc_tf:
                # TF-IDF weighting
                doc_tf_weight = 1 + math.log(doc_tf[term]) if doc_tf[term] > 0 else 0
                query_tf_weight = 1 + math.log(tf) if tf > 0 else 0
                idf = self.idf_scores.get(term, 1.0)
                
                score += doc_tf_weight * query_tf_weight * idf
        
        return score
    
    def add_document(
        self,
        content: str,
        source: str,
        doc_type: str,
        metadata: Dict[str, Any] = None
    ):
        """
        Add a document to the retriever at runtime.
        
        This is useful for adding UI discovery results dynamically.
        """
        doc = Document(content, source, doc_type, metadata)
        self.documents.append(doc)
        
        # Update index incrementally
        term_freq = defaultdict(int)
        for token in doc.tokens:
            term_freq[token] += 1
        self.doc_term_freq.append(dict(term_freq))
        
        # Update IDF scores (simplified - full rebuild would be more accurate)
        n_docs = len(self.documents)
        for token in set(doc.tokens):
            current_df = sum(1 for dtf in self.doc_term_freq if token in dtf)
            self.idf_scores[token] = math.log((n_docs + 1) / (current_df + 1)) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retriever statistics."""
        type_counts = defaultdict(int)
        for doc in self.documents:
            type_counts[doc.doc_type] += 1
        
        return {
            'total_documents': len(self.documents),
            'documents_by_type': dict(type_counts),
            'vocabulary_size': len(self.idf_scores),
            'is_initialized': self._is_initialized
        }
