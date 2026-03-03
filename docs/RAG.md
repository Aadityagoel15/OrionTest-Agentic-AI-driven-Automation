## RAG Overview

RAG (Retrieval Augmented Generation) provides runtime grounding for LLM output.
It retrieves rules, examples, and optional custom documentation and injects
that context into prompts before generation.

RAG is used at inference time only.

## Default Sources

The source manager loads documents from:

- `features/steps/` (step definitions, parsed into step patterns)
- `rag/sources/framework_rules/` (rules and refusal patterns)
- `rag/sources/gherkin_examples/` (example features)
- `reports/` (UI discovery outputs)
- `reports/ui_locators.properties` (XPath locators)

## Company Documentation

You can drop client documentation into:

```
rag/sources/company_docs/
```

Any files with approved extensions will be indexed.

## Custom Documentation Path

You can also point to an external folder with `RAG_CUSTOM_PATH`:

```
RAG_CUSTOM_PATH=C:\client_repo\docs
RAG_CUSTOM_EXTS=md,txt,feature,py,java,js,ts,tsx,jsx,json,yaml,yml
RAG_CUSTOM_MAX_BYTES=1000000
```

## Extension and Size Filters

- `RAG_CUSTOM_EXTS` controls which file types are indexed.
- `RAG_CUSTOM_MAX_BYTES` prevents large files from being loaded.

Files that exceed the size limit or are empty are skipped.

## Retrieval Strategy

The retriever uses deterministic keyword TF-IDF matching. This favors exact
phrases and canonical step patterns, which improves reliability for BDD steps.

## Where to Change Behavior

- `rag/sources.py` controls source loading and filters
- `rag/retriever.py` controls retrieval and scoring
- `rag/context_builder.py` controls how context is formatted
