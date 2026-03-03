# Step 7: Wire RAG into LocalLLMClient

## Overview

RAG is wired into LocalLLMClient so that context is automatically injected before every generation. Agents don't need to know about RAG - it's handled transparently.

## Wiring Flow

```
Agent.generate_response(prompt)
        │
        ▼
LocalLLMClient.generate_response(prompt)
        │
        ▼
_inject_rag_context(prompt)  ◄── RAG happens here
        │
        ▼
_format_chat_prompt(enriched_prompt)
        │
        ▼
_generate_deterministic(formatted_prompt)
        │
        ▼
_apply_guardrails(response)
        │
        ▼
return response
```

## Automatic Wiring via Factory

The LLM factory automatically attaches RAG when creating a local client:

```python
# llm/__init__.py
def _get_local_client():
    from llm.local_llm_client import LocalLLMClient
    
    # Automatically attach RAG
    rag_retriever = None
    try:
        from rag import get_rag_retriever
        rag_retriever = get_rag_retriever()
    except ImportError:
        print("[LLM] RAG module not found")
    
    return LocalLLMClient(rag_retriever=rag_retriever)
```

## Manual Wiring

If you need explicit control:

```python
from llm.local_llm_client import LocalLLMClient
from rag import get_rag_retriever

# Create retriever
retriever = get_rag_retriever()

# Attach to client
client = LocalLLMClient(rag_retriever=retriever)

# Or attach later
client = LocalLLMClient()
client.set_rag_retriever(retriever)
```

## Context Injection Implementation

```python
def _inject_rag_context(self, prompt: str, system_prompt: str = None) -> str:
    """Inject RAG-retrieved context into the prompt."""
    if self.rag_retriever is None:
        return prompt
    
    try:
        # Retrieve relevant documents
        docs = self.rag_retriever.retrieve(prompt, top_k=5)
        
        if not docs:
            return prompt
        
        # Build context block
        context = "=== RETRIEVED CONTEXT ===\n"
        for doc in docs:
            context += f"\n[{doc['source']}]:\n{doc['content']}\n"
        context += "\n=== END CONTEXT ===\n\n"
        
        # Prepend to prompt
        return context + prompt
        
    except Exception as e:
        print(f"[LocalLLM] RAG retrieval failed: {e}")
        return prompt  # Continue without RAG on error
```

## Agent Transparency

Agents remain unchanged - they don't know about RAG:

```python
# RequirementsToFeatureAgent (unchanged)
class RequirementsToFeatureAgent:
    def __init__(self):
        # Uses factory - RAG automatically attached
        from llm import get_llm_client
        self.llm_client = get_llm_client()
    
    def convert_requirements_to_feature(self, requirements):
        # RAG context injected automatically
        response = self.llm_client.generate_response(
            prompt=requirements,
            system_prompt=self.SYSTEM_PROMPT
        )
        return response
```

## Prompt Structure After RAG

Before RAG:
```
<|system|>
You are a QA automation expert.</s>
<|user|>
Generate steps for clicking the Login button</s>
<|assistant|>
```

After RAG:
```
<|system|>
You are a QA automation expert.</s>
<|user|>
=== RETRIEVED CONTEXT ===

[step_definition]: @when: the user clicks the "{button}" button
[ui_discovery]: Available buttons: Login, Submit, Cancel
[framework_rule]: Subject must be "the user"

=== END CONTEXT ===

Generate steps for clicking the Login button</s>
<|assistant|>
```

## Dynamic Context Updates

### Adding UI Discovery at Runtime

When the UI discovery agent runs, add results to RAG:

```python
# In orchestrator or agent
def run_ui_discovery(self, base_url):
    # Run discovery
    ui_elements = self.web_discovery_agent.discover(base_url)
    
    # Add to RAG for subsequent agents
    from rag import get_rag_retriever
    retriever = get_rag_retriever()
    retriever.add_document(
        content=f"Discovered UI elements:\n{ui_elements}",
        source="runtime_ui_discovery",
        doc_type="ui_discovery"
    )
```

### Refreshing Sources

To reload all sources:

```python
from rag import get_rag_retriever

retriever = get_rag_retriever(force_new=True)  # Creates fresh instance
```

## Error Handling

RAG failures should not break generation:

```python
def _inject_rag_context(self, prompt, system_prompt=None):
    if self.rag_retriever is None:
        return prompt  # No RAG configured
    
    try:
        docs = self.rag_retriever.retrieve(prompt)
        # ... build context
    except Exception as e:
        # Log warning but continue
        print(f"[WARNING] RAG failed: {e}")
        return prompt  # Return original prompt
```

## Disabling RAG

### Via Environment

```bash
RAG_ENABLED=false
```

### Via Code

```python
# Don't attach retriever
client = LocalLLMClient(rag_retriever=None)
```

### Via Config

```python
from config import Config

if not Config.RAG_ENABLED:
    client = LocalLLMClient()  # No RAG
else:
    from rag import get_rag_retriever
    client = LocalLLMClient(rag_retriever=get_rag_retriever())
```

## Monitoring RAG Usage

Track what's being retrieved:

```python
class LocalLLMClient:
    def __init__(self, ...):
        self.rag_stats = {
            'calls': 0,
            'docs_retrieved': 0,
            'failures': 0
        }
    
    def _inject_rag_context(self, prompt, system_prompt=None):
        self.rag_stats['calls'] += 1
        
        try:
            docs = self.rag_retriever.retrieve(prompt)
            self.rag_stats['docs_retrieved'] += len(docs)
            # ...
        except Exception:
            self.rag_stats['failures'] += 1
            # ...
    
    def get_rag_stats(self):
        return self.rag_stats
```

## Testing RAG Wiring

```python
def test_rag_wiring():
    from llm import get_llm_client
    
    client = get_llm_client(force_local=True)
    
    # Check RAG is attached
    assert client.rag_retriever is not None
    
    # Generate with RAG
    response = client.generate_response("Generate login steps")
    
    # Response should be informed by RAG context
    assert "the user" in response.lower()
```
