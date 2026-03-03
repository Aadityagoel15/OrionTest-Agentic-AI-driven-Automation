# Step 4: LocalLLMClient Implementation

## Overview

The `LocalLLMClient` is a drop-in replacement for `GroqClient`. It provides the same interface but uses a locally-hosted TinyLlama + LoRA model instead of cloud API calls.

## File Location

```
llm/
├── __init__.py           # Factory pattern
└── local_llm_client.py   # LocalLLMClient implementation
```

## Interface Compatibility

The LocalLLMClient implements the same methods as GroqClient:

| Method | Description |
|--------|-------------|
| `generate_response(prompt, system_prompt)` | Generate text response |
| `generate_structured_response(prompt, system_prompt)` | Generate JSON response |

This allows seamless swapping between cloud and local inference.

## Key Features

### 1. Deterministic Generation

```python
# Deterministic settings (CRITICAL)
DO_SAMPLE = False       # Greedy decoding
TEMPERATURE = 0.0       # No randomness
TOP_P = 1.0            # No nucleus sampling
TOP_K = 1              # Only top token
REPETITION_PENALTY = 1.0
```

These settings ensure the same input always produces the same output.

### 2. RAG Integration

RAG context is injected automatically when a retriever is attached:

```python
client = LocalLLMClient(rag_retriever=retriever)
```

RAG flow:
1. User prompt received
2. RAG retriever finds relevant documents
3. Context prepended to prompt
4. Model generates with enriched context

### 3. Guardrails

Built-in validation and safety checks:

- **Refusal detection**: Recognizes proper refusal responses
- **Length validation**: Rejects too-short outputs
- **Hallucination warnings**: Flags uncertainty indicators
- **Output cleaning**: Removes formatting artifacts

### 4. Lazy Loading

Model is loaded on first use, not at instantiation:

```python
client = LocalLLMClient()  # No model loaded yet
response = client.generate_response(...)  # Model loads here
```

## Usage Examples

### Basic Usage

```python
from llm.local_llm_client import LocalLLMClient

client = LocalLLMClient()

response = client.generate_response(
    prompt="Generate a Gherkin step for clicking the Login button",
    system_prompt="You are a QA automation expert."
)

print(response)
```

### With RAG

```python
from llm.local_llm_client import LocalLLMClient
from rag import get_rag_retriever

retriever = get_rag_retriever()
client = LocalLLMClient(rag_retriever=retriever)

# RAG context is automatically injected
response = client.generate_response(
    prompt="Generate steps for user login",
    system_prompt="Generate valid Gherkin only."
)
```

### Structured Response

```python
response = client.generate_structured_response(
    prompt="Return a JSON with step type and pattern",
    system_prompt="Return valid JSON only."
)

# response is a dict, e.g., {"step_type": "when", "pattern": "..."}
```

### Health Check

```python
health = client.health_check()
print(health)
# {
#     'model_loaded': True,
#     'device': 'cuda',
#     'lora_path_exists': True,
#     'base_model': 'TinyLlama/TinyLlama-1.1B-Chat-v1.0',
#     'memory_allocated': '2.5 GB'
# }
```

### Gherkin Validation

```python
gherkin_content = """
Feature: Login
  Scenario: User logs in
    Given the user navigates to "https://example.com"
    When the user clicks the "Login" button
"""

validation = client.validate_gherkin(gherkin_content)
print(validation)
# {'valid': True, 'errors': []}
```

## Configuration Options

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_model_name` | str | TinyLlama-1.1B-Chat | HuggingFace model name |
| `lora_path` | str | models/tinyllama-lora-qa | Path to LoRA adapter |
| `max_tokens` | int | 4096 | Max tokens to generate |
| `rag_retriever` | object | None | RAG retriever instance |
| `device` | str | "auto" | Device: "cuda", "cpu", "auto" |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_LOCAL_LLM` | false | Enable local LLM |
| `LOCAL_LLM_BASE_MODEL` | TinyLlama-1.1B | Base model name |
| `LOCAL_LLM_LORA_PATH` | models/tinyllama-lora-qa | LoRA path |
| `LOCAL_LLM_DEVICE` | auto | Device selection |

## Prompt Formatting

TinyLlama uses ChatML format:

```
<|system|>
{system_message}</s>
<|user|>
{user_message}</s>
<|assistant|>
```

The LocalLLMClient handles this formatting automatically.

## Error Handling

### Missing LoRA Files

If LoRA adapter files are not found:

```python
# Warning is logged, base model used without LoRA
[LocalLLM] WARNING: LoRA path not found, using base model only
```

### Refusal Response

When model properly refuses:

```python
response = client.generate_response("Click nonexistent button")
# "ERROR: Required UI element not present in discovery or context."
```

## Class Diagram

```
┌─────────────────────────────────────────────────────┐
│                  LocalLLMClient                     │
├─────────────────────────────────────────────────────┤
│ - _model: PeftModel                                 │
│ - _tokenizer: AutoTokenizer                         │
│ - _is_loaded: bool                                  │
│ - rag_retriever: RAGRetriever                       │
│ - max_tokens: int                                   │
│ - device: str                                       │
├─────────────────────────────────────────────────────┤
│ + generate_response(prompt, system_prompt) → str    │
│ + generate_structured_response(...) → dict          │
│ + set_rag_retriever(retriever)                      │
│ + validate_gherkin(content) → dict                  │
│ + validate_step_definitions(content) → dict         │
│ + health_check() → dict                             │
├─────────────────────────────────────────────────────┤
│ - _ensure_loaded()                                  │
│ - _format_chat_prompt(prompt, system_prompt) → str  │
│ - _generate_deterministic(prompt) → str             │
│ - _inject_rag_context(prompt, system_prompt) → str  │
│ - _apply_guardrails(response, prompt) → str         │
│ - _is_refusal(response) → bool                      │
│ - _clean_response(response) → str                   │
└─────────────────────────────────────────────────────┘
```

## Integration with Agents

Agents can use the LLM factory to get the appropriate client:

```python
from llm import get_llm_client

class RequirementsToFeatureAgent:
    def __init__(self):
        self.llm_client = get_llm_client()  # Auto-selects based on config
    
    def convert_requirements_to_feature(self, requirements):
        response = self.llm_client.generate_response(
            prompt=requirements,
            system_prompt=self.SYSTEM_PROMPT
        )
        return response
```
