# Local LLM Integration Overview

## Introduction

This documentation covers the complete integration of a locally-hosted TinyLlama + LoRA model for QA Automation. The system replaces cloud-based LLM inference (Groq) with a fine-tuned local model that provides:

- **Deterministic outputs** - Same input always produces same output
- **No API costs** - Runs entirely on local hardware
- **Privacy** - No data leaves your infrastructure
- **Trained QA behavior** - Model fine-tuned for BDD/Gherkin generation

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Orchestrator                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                           Agents                                │
│  (RequirementsToFeature, FeatureToStepDef, etc.)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Factory (llm/__init__.py)                │
│                                                                 │
│   ┌─────────────────┐           ┌─────────────────┐            │
│   │   GroqClient    │    OR     │  LocalLLMClient │            │
│   │   (Cloud)       │           │  (Local)        │            │
│   └─────────────────┘           └─────────────────┘            │
│                                         │                       │
│                                         ▼                       │
│                               ┌─────────────────┐              │
│                               │  RAG Retriever  │              │
│                               │  (Context)      │              │
│                               └─────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TinyLlama + LoRA Model                       │
│                                                                 │
│   Base: TinyLlama-1.1B-Chat-v1.0                               │
│   Adapter: models/tinyllama-lora-qa/                           │
│                                                                 │
│   - adapter_config.json                                        │
│   - adapter_model.safetensors                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| LocalLLMClient | `llm/local_llm_client.py` | Main LLM client for local inference |
| LLM Factory | `llm/__init__.py` | Factory pattern for client selection |
| RAG Retriever | `rag/retriever.py` | TF-IDF based document retrieval |
| Context Builder | `rag/context_builder.py` | Formats retrieved docs for prompts |
| Source Manager | `rag/sources.py` | Loads documents from various sources |
| Config | `config.py` | Configuration with LLM backend selection |

## Quick Start

### 1. Enable Local LLM

Add to your `.env` file:
```
USE_LOCAL_LLM=true
```

Or set at runtime:
```python
from config import Config, LLMBackend
Config.set_llm_backend(LLMBackend.LOCAL)
```

### 2. Get LLM Client

```python
from llm import get_llm_client

client = get_llm_client()  # Automatically selects based on config
response = client.generate_response(prompt, system_prompt)
```

### 3. Run Smoke Tests

```bash
pytest tests/test_local_llm_smoke.py -v
```

## Documentation Index

| Step | Document | Description |
|------|----------|-------------|
| 1 | [01-MODEL-FREEZE.md](01-MODEL-FREEZE.md) | Freeze the trained model |
| 2 | [02-MODEL-PLACEMENT.md](02-MODEL-PLACEMENT.md) | Place model files in project |
| 3 | [03-MODEL-LOADING.md](03-MODEL-LOADING.md) | Load model correctly (Base + LoRA) |
| 4 | [04-LOCAL-LLM-CLIENT.md](04-LOCAL-LLM-CLIENT.md) | LocalLLMClient implementation |
| 5 | [05-SMOKE-TESTS.md](05-SMOKE-TESTS.md) | Model behavior verification |
| 6 | [06-RAG-INTEGRATION.md](06-RAG-INTEGRATION.md) | RAG at inference time |
| 7 | [07-RAG-WIRING.md](07-RAG-WIRING.md) | Wire RAG into LocalLLMClient |
| 8 | [08-AGENT-INTEGRATION.md](08-AGENT-INTEGRATION.md) | Integrate with agents |
| 9 | [09-GUARDRAILS.md](09-GUARDRAILS.md) | Add guardrails and validation |
| 10 | [10-GOVERNANCE.md](10-GOVERNANCE.md) | Documentation and governance |

## Requirements

### Hardware
- **GPU**: 4GB+ VRAM (recommended for speed)
- **CPU-only**: 8GB+ RAM (slower but works)

### Software
- Python 3.9+
- PyTorch 2.0+
- Transformers 4.36+
- PEFT 0.7+

### Model Files
```
models/tinyllama-lora-qa/
├── adapter_config.json
└── adapter_model.safetensors
```
