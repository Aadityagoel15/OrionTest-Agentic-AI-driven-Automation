"""
Source Manager - Loads and Manages RAG Sources

This module handles loading documents from various sources:
1. Canonical step definitions (from features/steps/)
2. Framework rules (from rag/sources/framework_rules/)
3. UI discovery outputs (from reports/)
4. XPath locators (from reports/ui_locators.properties)
5. Optional custom docs (from RAG_CUSTOM_PATH)

Sources are loaded at initialization and can be refreshed at runtime.
"""

import os
import re
import glob
from typing import List, Dict, Any


class SourceManager:
    """
    Manages loading and refreshing of RAG source documents.
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize the source manager.
        
        Args:
            base_path: Base path for the project (defaults to project root)
        """
        if base_path:
            self.base_path = base_path
        else:
            # Determine project root
            self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Source directories
        self.step_defs_dir = os.path.join(self.base_path, "features", "steps")
        self.framework_rules_dir = os.path.join(self.base_path, "rag", "sources", "framework_rules")
        self.gherkin_examples_dir = os.path.join(self.base_path, "rag", "sources", "gherkin_examples")
        self.reports_dir = os.path.join(self.base_path, "reports")
        self.company_docs_dir = os.path.join(self.base_path, "rag", "sources", "company_docs")
        self.custom_docs_path = os.getenv("RAG_CUSTOM_PATH", "").strip()
        self.custom_docs_exts = self._parse_custom_exts(os.getenv("RAG_CUSTOM_EXTS", ""))
        self.custom_docs_max_bytes = self._parse_custom_max_bytes(os.getenv("RAG_CUSTOM_MAX_BYTES", ""))
    
    def load_all_sources(self) -> List[Dict[str, Any]]:
        """
        Load all available sources.
        
        Returns:
            List of document dictionaries
        """
        documents = []
        
        # 1. Load canonical step definitions
        documents.extend(self._load_step_definitions())
        
        # 2. Load framework rules
        documents.extend(self._load_framework_rules())
        
        # 3. Load Gherkin examples
        documents.extend(self._load_gherkin_examples())
        
        # 4. Load company docs (if present)
        documents.extend(self._load_company_docs())
        
        # 5. Load optional custom docs (if configured)
        documents.extend(self._load_custom_sources())
        
        # 6. Load UI discovery outputs (if available)
        documents.extend(self._load_ui_discovery())
        
        # 7. Load XPath locators (if available)
        documents.extend(self._load_xpath_locators())
        
        return documents
    
    def _load_step_definitions(self) -> List[Dict[str, Any]]:
        """Load step definitions from features/steps/."""
        documents = []
        
        if not os.path.exists(self.step_defs_dir):
            return documents
        
        # Find all Python files in steps directory
        for root, dirs, files in os.walk(self.step_defs_dir):
            for filename in files:
                if filename.endswith('_steps.py') or filename.endswith('.py'):
                    if filename.startswith('__'):
                        continue
                    
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Extract individual step definitions
                        steps = self._extract_step_patterns(content)
                        for step in steps:
                            documents.append({
                                'content': step,
                                'source': f"steps/{filename}",
                                'doc_type': 'step_definition',
                                'metadata': {'file': filepath}
                            })
                    except Exception as e:
                        print(f"[RAG] Failed to load {filepath}: {e}")
        
        return documents
    
    def _extract_step_patterns(self, content: str) -> List[str]:
        """Extract step patterns from step definition file."""
        patterns = []
        
        # Match @given, @when, @then decorators with their patterns
        decorator_pattern = r'@(given|when|then)\([\'"](.+?)[\'"]\)'
        matches = re.findall(decorator_pattern, content, re.IGNORECASE)
        
        for decorator, pattern in matches:
            # Format as a readable pattern
            formatted = f"@{decorator.lower()}: {pattern}"
            patterns.append(formatted)
        
        # Also extract docstrings for context
        func_pattern = r'@(given|when|then)\([\'"](.+?)[\'"]\)\s*\ndef\s+\w+\([^)]*\):\s*[\']{3}(.+?)[\']{3}'
        doc_matches = re.findall(func_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for decorator, pattern, docstring in doc_matches:
            formatted = f"@{decorator.lower()}: {pattern}\nUsage: {docstring.strip()}"
            patterns.append(formatted)
        
        return patterns

    def _parse_custom_exts(self, env_value: str) -> List[str]:
        """Parse allowed extensions for custom docs."""
        if env_value:
            raw = [ext.strip().lstrip(".").lower() for ext in env_value.split(",")]
            return [ext for ext in raw if ext]
        return [
            "md", "txt", "feature",
            "py", "java", "js", "ts", "tsx", "jsx",
            "json", "yaml", "yml",
        ]

    def _parse_custom_max_bytes(self, env_value: str) -> int:
        """Parse max bytes for custom docs."""
        try:
            value = int(env_value) if env_value else 1_000_000
            return max(1_024, value)
        except ValueError:
            return 1_000_000

    def _load_directory_docs(self, path: str, source_prefix: str) -> List[Dict[str, Any]]:
        """Load docs from a directory using configured filters."""
        documents = []
        if not path:
            return documents
        if not os.path.exists(path):
            return documents

        for root, dirs, files in os.walk(path):
            for filename in files:
                ext = os.path.splitext(filename)[1].lstrip(".").lower()
                if ext not in self.custom_docs_exts:
                    continue

                filepath = os.path.join(root, filename)
                try:
                    if os.path.getsize(filepath) > self.custom_docs_max_bytes:
                        continue
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if not content.strip():
                        continue

                    source = os.path.relpath(filepath, path)
                    documents.append({
                        'content': content,
                        'source': f"{source_prefix}/{source}",
                        'doc_type': 'custom_doc',
                        'metadata': {'file': filepath}
                    })
                except Exception as e:
                    print(f"[RAG] Failed to load custom doc {filepath}: {e}")

        return documents

    def _load_company_docs(self) -> List[Dict[str, Any]]:
        """Load docs from rag/sources/company_docs if present."""
        return self._load_directory_docs(self.company_docs_dir, "company_docs")

    def _load_custom_sources(self) -> List[Dict[str, Any]]:
        """Load custom docs from a configured path."""
        documents = []
        if not self.custom_docs_path:
            return documents
        if not os.path.exists(self.custom_docs_path):
            print(f"[RAG] Custom docs path not found: {self.custom_docs_path}")
            return documents
        return self._load_directory_docs(self.custom_docs_path, "custom_docs")
    
    def _load_framework_rules(self) -> List[Dict[str, Any]]:
        """Load framework rules from rag/sources/framework_rules/."""
        documents = []
        
        if not os.path.exists(self.framework_rules_dir):
            # Create default rules if directory doesn't exist
            self._create_default_framework_rules()
        
        if not os.path.exists(self.framework_rules_dir):
            return documents
        
        for filename in os.listdir(self.framework_rules_dir):
            if filename.endswith('.txt') or filename.endswith('.md'):
                filepath = os.path.join(self.framework_rules_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    documents.append({
                        'content': content,
                        'source': f"framework_rules/{filename}",
                        'doc_type': 'framework_rule',
                        'metadata': {'file': filepath}
                    })
                except Exception as e:
                    print(f"[RAG] Failed to load {filepath}: {e}")
        
        return documents
    
    def _load_gherkin_examples(self) -> List[Dict[str, Any]]:
        """Load Gherkin examples from rag/sources/gherkin_examples/."""
        documents = []
        
        if not os.path.exists(self.gherkin_examples_dir):
            # Create default examples if directory doesn't exist
            self._create_default_gherkin_examples()
        
        if not os.path.exists(self.gherkin_examples_dir):
            return documents
        
        for filename in os.listdir(self.gherkin_examples_dir):
            if filename.endswith('.feature') or filename.endswith('.txt'):
                filepath = os.path.join(self.gherkin_examples_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    documents.append({
                        'content': content,
                        'source': f"gherkin_examples/{filename}",
                        'doc_type': 'gherkin_example',
                        'metadata': {'file': filepath}
                    })
                except Exception as e:
                    print(f"[RAG] Failed to load {filepath}: {e}")
        
        return documents
    
    def _load_ui_discovery(self) -> List[Dict[str, Any]]:
        """Load UI discovery outputs from reports/."""
        documents = []
        
        if not os.path.exists(self.reports_dir):
            return documents
        
        # Look for UI discovery JSON files
        for filename in os.listdir(self.reports_dir):
            if 'ui_discovery' in filename.lower() and filename.endswith('.json'):
                filepath = os.path.join(self.reports_dir, filename)
                try:
                    import json
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Convert to readable format
                    content = self._format_ui_discovery(data)
                    
                    documents.append({
                        'content': content,
                        'source': f"reports/{filename}",
                        'doc_type': 'ui_discovery',
                        'metadata': {'file': filepath, 'raw_data': data}
                    })
                except Exception as e:
                    print(f"[RAG] Failed to load {filepath}: {e}")
        
        return documents
    
    def _format_ui_discovery(self, data: Dict[str, Any]) -> str:
        """Format UI discovery data as readable text."""
        lines = ["UI Elements Discovered:"]
        
        # Handle various data formats
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    lines.append(f"\n{key}:")
                    for item in value[:10]:  # Limit to first 10
                        lines.append(f"  - {item}")
                else:
                    lines.append(f"{key}: {value}")
        elif isinstance(data, list):
            for item in data[:20]:  # Limit to first 20
                lines.append(f"  - {item}")
        
        return "\n".join(lines)
    
    def _load_xpath_locators(self) -> List[Dict[str, Any]]:
        """Load XPath locators from ui_locators.properties."""
        documents = []
        
        locator_file = os.path.join(self.reports_dir, "ui_locators.properties")
        if not os.path.exists(locator_file):
            return documents
        
        try:
            with open(locator_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            documents.append({
                'content': content,
                'source': "reports/ui_locators.properties",
                'doc_type': 'xpath_locator',
                'metadata': {'file': locator_file}
            })
        except Exception as e:
            print(f"[RAG] Failed to load {locator_file}: {e}")
        
        return documents
    
    def _create_default_framework_rules(self):
        """Create default framework rules directory and files."""
        os.makedirs(self.framework_rules_dir, exist_ok=True)
        
        # Create canonical grammar rules
        grammar_rules = """# Canonical Gherkin Grammar Rules

## Step Format Rules
1. All steps MUST start with: Given, When, Then, And, or But
2. Subject must be "the user" (not "I" or "User")
3. Use present tense for actions

## Canonical Step Patterns

### Navigation
- the user navigates to "{url}"

### Form Input
- the user enters "{value}" into the "{field_name}" field

### Button Clicks
- the user clicks the "{button_name}" button

### Verification
- the user should see text "{expected_text}"
- the user should be on the {page_name} page
- the action should succeed

## Refusal Behavior
If required UI elements are not present in the discovery or context:
- MUST return: ERROR: Required UI element not present in discovery or context.
- Do NOT invent element names
- Do NOT hallucinate locators

## Output Format
- Return ONLY valid Gherkin
- NO explanations
- NO markdown formatting around feature content
- NO invented steps
"""
        
        rules_file = os.path.join(self.framework_rules_dir, "canonical_grammar.txt")
        with open(rules_file, 'w', encoding='utf-8') as f:
            f.write(grammar_rules)
        
        print(f"[RAG] Created default framework rules at {self.framework_rules_dir}")
    
    def _create_default_gherkin_examples(self):
        """Create default Gherkin examples directory and files."""
        os.makedirs(self.gherkin_examples_dir, exist_ok=True)
        
        # Create example feature file
        example_feature = """Feature: Example Login Flow

Background:
  Given the user navigates to "https://example.com"
  Given the user enters "testuser" into the "username" field
  Given the user enters "password123" into the "password" field
  Given the user clicks the "Login" button

Scenario: User adds item to cart and completes checkout
  When the user clicks the "Add to cart" button for the item "Sample Product"
  When the user clicks the "Cart" button
  When the user clicks the "Checkout" button
  When the user enters "John" into the "first-name" field
  When the user enters "Doe" into the "last-name" field
  When the user enters "12345" into the "postal-code" field
  When the user clicks the "Continue" button
  When the user clicks the "Finish" button
  Then the user should see text "Thank you for your order"
"""
        
        example_file = os.path.join(self.gherkin_examples_dir, "login_checkout.feature")
        with open(example_file, 'w', encoding='utf-8') as f:
            f.write(example_feature)
        
        print(f"[RAG] Created default Gherkin examples at {self.gherkin_examples_dir}")
    
    def refresh_ui_discovery(self, discovery_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add new UI discovery data at runtime.
        
        Args:
            discovery_data: UI discovery data to add
        
        Returns:
            Document dictionary that was created
        """
        content = self._format_ui_discovery(discovery_data)
        
        return {
            'content': content,
            'source': 'runtime_ui_discovery',
            'doc_type': 'ui_discovery',
            'metadata': {'raw_data': discovery_data}
        }
