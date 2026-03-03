## LLM Backends

This project supports two LLM backends:

- Cloud (Groq API)
- Local (TinyLlama + LoRA)

Selection is controlled by environment variables in `.env` and a non-hidden
`llm.env.example` file (loaded after `.env` so it can override LLM values).
This is read by `config.py` and `llm/__init__.py`.

## Cloud (Groq)

Required settings:

- `GROQ_API_KEY`
- `GROQ_MODEL` (optional, default `llama-3.1-8b-instant`)

Example:

```
USE_LOCAL_LLM=false
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

## Local (TinyLlama + LoRA)

Required settings:

- `USE_LOCAL_LLM=true`
- `LOCAL_LLM_BASE_MODEL`
- `LOCAL_LLM_LORA_PATH`
- `LOCAL_LLM_DEVICE` (auto, cpu, or cuda)

Example:

```
USE_LOCAL_LLM=true
LOCAL_LLM_BASE_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0
LOCAL_LLM_LORA_PATH=models/tinyllama-lora-qa
LOCAL_LLM_DEVICE=auto
```

## Shared LLM Settings

These apply to both backends:

- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`

For the local backend, temperature is forced to 0.0 to ensure deterministic
output.

Example:

```
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

## Using a Non-Hidden LLM File

Use `llm.env.example` in the project root for LLM settings.
It will override values from `.env`.

You can also point to a custom file:

```
LLM_ENV_FILE=path/to/llm.env
```

## How the Backend is Chosen

The factory in `llm/__init__.py` selects the backend in this order:

1. Explicit override in code (force_local / force_cloud)
2. `USE_LOCAL_LLM` environment variable
3. Default to cloud

## Troubleshooting

- If local model fails to load, confirm:
  - `models/tinyllama-lora-qa/adapter_config.json`
  - `models/tinyllama-lora-qa/adapter_model.safetensors`
- If cloud calls fail, confirm `GROQ_API_KEY` is set.
- If generation errors occur with long prompts, reduce `LLM_MAX_TOKENS`.
