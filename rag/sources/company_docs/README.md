## Company Documentation (RAG)

Drop client documentation or code snippets in this folder to make them
available to the RAG retriever.

Supported extensions are controlled by `RAG_CUSTOM_EXTS` (see `env_template.txt`).
Files larger than `RAG_CUSTOM_MAX_BYTES` are ignored.

Example:
- `api_contract.md`
- `ui_guidelines.txt`
- `sample_flows.feature`
