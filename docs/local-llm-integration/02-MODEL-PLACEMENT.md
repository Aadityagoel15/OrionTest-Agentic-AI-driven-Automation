# Step 2: Place Model Files in Project

## Recommended Directory Structure

```
BDD-Automation/
├── models/                          # Model files directory
│   └── tinyllama-lora-qa/          # LoRA adapter
│       ├── adapter_config.json     # LoRA configuration
│       └── adapter_model.safetensors # Trained weights
│
├── llm/                             # LLM client module
│   ├── __init__.py                 # Factory pattern
│   └── local_llm_client.py         # Local LLM client
│
├── rag/                             # RAG module
│   ├── __init__.py
│   ├── retriever.py                # Document retrieval
│   ├── context_builder.py          # Context formatting
│   ├── sources.py                  # Source management
│   └── sources/                    # RAG source documents
│       ├── framework_rules/
│       └── gherkin_examples/
│
├── agents/                          # BDD agents
├── features/                        # Feature files
├── config.py                        # Configuration
└── orchestrator.py                  # Main orchestrator
```

## Model File Locations

### Primary Location

The LocalLLMClient looks for model files in this order:

1. `models/tinyllama-lora-qa/` (relative to project root)
2. Path specified in `LOCAL_LLM_LORA_PATH` environment variable
3. Absolute path passed to constructor

### Environment Variable Override

```bash
# .env file
LOCAL_LLM_LORA_PATH=models/tinyllama-lora-qa-v1.0.0
```

### Constructor Override

```python
from llm.local_llm_client import LocalLLMClient

client = LocalLLMClient(
    lora_path="/absolute/path/to/lora/adapter"
)
```

## File Size Considerations

| File | Typical Size | Notes |
|------|--------------|-------|
| adapter_config.json | <1 KB | JSON configuration |
| adapter_model.safetensors | 10-50 MB | Depends on LoRA rank |

### Storage Requirements

- **Development**: Local disk, ~100 MB per version
- **CI/CD**: Artifact cache, downloaded at build time
- **Production**: Pre-deployed with application

## Git Configuration

### .gitignore

Add to prevent committing large files accidentally:

```gitignore
# Model files (use Git LFS or artifact storage)
models/*.safetensors
models/**/*.safetensors

# Keep structure files
!models/.gitkeep
!models/*/README.md
```

### .gitattributes (for Git LFS)

```gitattributes
*.safetensors filter=lfs diff=lfs merge=lfs -text
```

## Deployment Strategies

### Strategy 1: Bundled with Application

Include model files in deployment package:

```dockerfile
# Dockerfile
COPY models/ /app/models/
```

**Pros**: Simple, self-contained
**Cons**: Larger deployment package

### Strategy 2: Downloaded at Startup

Download from artifact storage on first run:

```python
def ensure_model_exists():
    if not os.path.exists("models/tinyllama-lora-qa"):
        download_from_s3("models/tinyllama-lora-qa")
```

**Pros**: Smaller deployment, centralized versioning
**Cons**: Startup delay, network dependency

### Strategy 3: Pre-provisioned Infrastructure

Model files pre-installed on deployment targets:

```bash
# Ansible playbook example
- name: Ensure model directory exists
  file:
    path: /app/models/tinyllama-lora-qa
    state: directory

- name: Download model files
  aws_s3:
    bucket: model-artifacts
    object: "models/{{ model_version }}/adapter_model.safetensors"
    dest: /app/models/tinyllama-lora-qa/adapter_model.safetensors
```

**Pros**: Fastest startup, no network at runtime
**Cons**: More complex infrastructure

## Verification

After placing files, verify with:

```python
from llm import is_local_llm_available

if is_local_llm_available():
    print("✅ Model files found and valid")
else:
    print("❌ Model files not found")
```

Or via command line:

```bash
python -c "from llm import is_local_llm_available; print('Available:', is_local_llm_available())"
```

## Multiple Model Versions

For A/B testing or gradual rollout:

```
models/
├── tinyllama-lora-qa-v1.0.0/
├── tinyllama-lora-qa-v1.1.0/
└── tinyllama-lora-qa/  → symlink to current version
```

Select version via config:

```python
# .env
LOCAL_LLM_LORA_PATH=models/tinyllama-lora-qa-v1.1.0
```
