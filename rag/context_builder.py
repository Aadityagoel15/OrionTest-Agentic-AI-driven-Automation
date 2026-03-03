"""
Context Builder - Assembles Retrieved Documents into Prompts

This module formats retrieved documents into structured context
that can be injected into LLM prompts.

The context format is designed to:
1. Clearly delineate different types of information
2. Prioritize most relevant documents
3. Stay within token limits
4. Provide source attribution for traceability
"""

from typing import List, Dict, Any, Optional


class ContextBuilder:
    """
    Builds formatted context strings from retrieved documents.
    """
    
    # Approximate characters per token (for estimation)
    CHARS_PER_TOKEN = 4
    
    # Section headers by document type
    SECTION_HEADERS = {
        'step_definition': '📋 CANONICAL STEP PATTERNS',
        'ui_discovery': '🖥️ UI ELEMENTS DISCOVERED',
        'xpath_locator': '🎯 XPATH LOCATORS',
        'framework_rule': '📜 FRAMEWORK RULES',
        'gherkin_example': '📝 GHERKIN EXAMPLES',
        'error_pattern': '⚠️ ERROR PATTERNS',
        'custom_doc': '📚 CUSTOM DOCUMENTS',
    }
    
    # Priority order for document types (higher priority first)
    TYPE_PRIORITY = [
        'framework_rule',
        'step_definition',
        'ui_discovery',
        'xpath_locator',
        'gherkin_example',
        'error_pattern',
        'custom_doc',
    ]
    
    def __init__(self):
        pass
    
    def build(
        self,
        documents: List[Dict[str, Any]],
        max_tokens: int = 1000,
        include_sources: bool = True
    ) -> str:
        """
        Build formatted context string from retrieved documents.
        
        Args:
            documents: List of retrieved documents with content and metadata
            max_tokens: Maximum approximate tokens in output
            include_sources: Whether to include source attribution
        
        Returns:
            Formatted context string
        """
        if not documents:
            return ""
        
        max_chars = max_tokens * self.CHARS_PER_TOKEN
        
        # Group documents by type
        grouped = self._group_by_type(documents)
        
        # Build context sections in priority order
        sections = []
        current_chars = 0
        
        for doc_type in self.TYPE_PRIORITY:
            if doc_type not in grouped:
                continue
            
            section = self._build_section(
                doc_type,
                grouped[doc_type],
                max_chars - current_chars,
                include_sources
            )
            
            if section:
                sections.append(section)
                current_chars += len(section)
            
            if current_chars >= max_chars:
                break
        
        # Handle any remaining types not in priority list
        for doc_type, docs in grouped.items():
            if doc_type not in self.TYPE_PRIORITY:
                section = self._build_section(
                    doc_type,
                    docs,
                    max_chars - current_chars,
                    include_sources
                )
                if section:
                    sections.append(section)
                    current_chars += len(section)
        
        if not sections:
            return ""
        
        # Combine sections with clear boundaries
        context = "=== RETRIEVED CONTEXT FOR REFERENCE ===\n\n"
        context += "\n\n".join(sections)
        context += "\n\n=== END OF CONTEXT ===\n"
        
        return context
    
    def _group_by_type(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group documents by their type."""
        grouped = {}
        for doc in documents:
            doc_type = doc.get('doc_type', 'unknown')
            if doc_type not in grouped:
                grouped[doc_type] = []
            grouped[doc_type].append(doc)
        return grouped
    
    def _build_section(
        self,
        doc_type: str,
        documents: List[Dict[str, Any]],
        max_chars: int,
        include_sources: bool
    ) -> Optional[str]:
        """Build a single section for a document type."""
        if max_chars <= 0:
            return None
        
        header = self.SECTION_HEADERS.get(doc_type, f'📄 {doc_type.upper()}')
        section = f"{header}\n" + "-" * 40 + "\n"
        
        for doc in documents:
            if len(section) >= max_chars:
                break
            
            content = doc.get('content', '')
            
            # Truncate if needed
            remaining = max_chars - len(section)
            if len(content) > remaining - 50:  # Leave room for formatting
                content = content[:remaining - 50] + "..."
            
            section += f"\n{content}\n"
            
            if include_sources:
                source = doc.get('source', 'unknown')
                section += f"  [Source: {source}]\n"
        
        return section if len(section) > len(header) + 50 else None
    
    def build_minimal(
        self,
        documents: List[Dict[str, Any]],
        max_tokens: int = 500
    ) -> str:
        """
        Build minimal context with just the essentials.
        
        Useful when token budget is tight.
        """
        if not documents:
            return ""
        
        max_chars = max_tokens * self.CHARS_PER_TOKEN
        context = "Context:\n"
        
        for doc in documents:
            content = doc.get('content', '')
            
            if len(context) + len(content) > max_chars:
                remaining = max_chars - len(context) - 10
                if remaining > 50:
                    context += content[:remaining] + "...\n"
                break
            
            context += content + "\n"
        
        return context
    
    def build_structured(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Build structured context as a dictionary.
        
        Useful when you need to access different types separately.
        """
        result = {}
        grouped = self._group_by_type(documents)
        
        for doc_type, docs in grouped.items():
            result[doc_type] = [doc.get('content', '') for doc in docs]
        
        return result
