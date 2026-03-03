# Step 6: Add RAG at Inference Time

## Critical Concept

**RAG is NOT used during training. RAG is added ONLY at runtime.**

The TinyLlama + LoRA model is trained to be a QA automation expert. RAG provides real-time context about:
- Available UI elements
- Valid step patterns
- Framework rules
- Current page structure

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Prompt                              │
│  "Generate steps for clicking the Add to cart button"          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RAG Retriever                              │
│                                                                 │
│  Query: "clicking Add to cart button"                          │
│                                                                 │
│  Retrieved Documents:                                           │
│  1. [step_definition] @when: clicks the "{button}" button      │
│  2. [ui_discovery] Buttons: Add to cart, Checkout, Login       │
│  3. [framework_rule] Use "the user" as subject                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Enriched Prompt                              │
│                                                                 │
│  === RETRIEVED CONTEXT ===                                      │
│  [step_definition] @when: clicks the "{button}" button         │
│  [ui_discovery] Buttons: Add to cart, Checkout, Login          │
│  [framework_rule] Use "the user" as subject                    │
│  === END CONTEXT ===                                           │
│                                                                 │
│  Generate steps for clicking the Add to cart button            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TinyLlama + LoRA                              │
│                                                                 │
│  Output: When the user clicks the "Add to cart" button         │
└─────────────────────────────────────────────────────────────────┘
```

## RAG Module Structure

```
rag/
├── __init__.py           # Module exports and singleton
├── retriever.py          # TF-IDF based retrieval
├── context_builder.py    # Format documents for prompt
├── sources.py            # Load source documents
└── sources/              # Source document storage
    ├── framework_rules/  # Canonical grammar rules
    │   ├── canonical_grammar.txt
    │   ├── step_definition_rules.txt
    │   └── refusal_patterns.txt
    └── gherkin_examples/ # Example feature files
        ├── login_checkout.feature
        ├── form_validation.feature
        └── search_workflow.feature
```

## RAG Sources

### 1. Canonical Step Definitions

Located in: `features/steps/`

These are the actual step definitions from your project. The RAG system extracts patterns like:

```
@when: the user clicks the "{button_name}" button
@then: the user should see text "{text}"
```

### 2. Framework Rules

Located in: `rag/sources/framework_rules/`

Rules that define correct behavior:
- Canonical grammar patterns
- Subject normalization ("the user")
- Refusal behavior requirements

### 3. UI Discovery Outputs

Located in: `reports/`

Dynamic content from UI discovery:
- Available buttons
- Form fields
- Page structure

### 4. Gherkin Examples

Located in: `rag/sources/gherkin_examples/`

Example feature files showing correct patterns.

## Retrieval Algorithm

The RAG system uses TF-IDF (Term Frequency-Inverse Document Frequency):

1. **Index Building**: Documents are tokenized and IDF scores calculated
2. **Query Processing**: User query is tokenized
3. **Scoring**: Documents scored by TF-IDF similarity
4. **Ranking**: Top-K documents returned

### Why TF-IDF (Not Vector Embeddings)?

For QA automation:
- Step patterns are keyword-based (exact match matters)
- Determinism is critical (embeddings can vary)
- Lower computational overhead
- No external embedding model needed

## Usage

### Basic Usage

```python
from rag import get_rag_retriever

retriever = get_rag_retriever()
docs = retriever.retrieve("How to click a button?", top_k=5)

for doc in docs:
    print(f"Source: {doc['source']}")
    print(f"Content: {doc['content'][:100]}...")
```

### With Context Builder

```python
from rag import get_rag_retriever, build_context

context = build_context("Generate login steps", max_tokens=500)
print(context)
# === RETRIEVED CONTEXT FOR REFERENCE ===
# 📋 CANONICAL STEP PATTERNS
# @when: the user clicks the "{button}" button
# ...
# === END OF CONTEXT ===
```

### Add Runtime Documents

```python
# Add UI discovery results at runtime
retriever.add_document(
    content="Buttons found: Login, Submit, Cancel",
    source="runtime_discovery",
    doc_type="ui_discovery"
)
```

## Configuration

### Environment Variables

```bash
# .env
RAG_ENABLED=true
RAG_TOP_K=5
RAG_MAX_CONTEXT_TOKENS=1000
```

### Programmatic

```python
from rag import get_rag_retriever

retriever = get_rag_retriever()

# Retrieve with custom settings
docs = retriever.retrieve(
    query="click button",
    top_k=3,
    doc_type_filter="step_definition",
    min_score=0.2
)
```

## Document Types

| Type | Source | Purpose |
|------|--------|---------|
| `step_definition` | features/steps/*.py | Available step patterns |
| `framework_rule` | rag/sources/framework_rules/ | Grammar and behavior rules |
| `gherkin_example` | rag/sources/gherkin_examples/ | Example features |
| `ui_discovery` | reports/*.json | Discovered UI elements |
| `xpath_locator` | reports/ui_locators.properties | Element locators |

## Context Priority

When building context, documents are prioritized:

1. **Framework Rules** (highest) - Must be followed
2. **Step Definitions** - Available patterns
3. **UI Discovery** - Current page state
4. **XPath Locators** - Element selectors
5. **Gherkin Examples** - Reference patterns

## Stats and Monitoring

```python
stats = retriever.get_stats()
print(stats)
# {
#     'total_documents': 45,
#     'documents_by_type': {
#         'step_definition': 15,
#         'framework_rule': 3,
#         'gherkin_example': 3,
#         'ui_discovery': 2,
#         'xpath_locator': 1
#     },
#     'vocabulary_size': 1234,
#     'is_initialized': True
# }
```
