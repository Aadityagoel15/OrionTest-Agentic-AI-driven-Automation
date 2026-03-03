# System Architecture

## Overview

The BDD Automation AI Agents system uses a pipeline architecture where each agent handles a specific stage of the BDD workflow. AI-powered stages can use either the Groq cloud API or a local TinyLlama + LoRA model, configured at runtime.

**Supported project types:** Web and API (these are the tested paths in the current release).

## Pipeline Flow

```
Requirements / project artifacts
    ↓
[Optional] Requirements Extraction Agent (from code/docs)
    ↓
[Web] Requirements-Aware UI Discovery + UI context + XPath discovery
    ↓
[RAG retrieval + LLM context]
    ↓
[Agent 1: Requirements → Feature]
    ↓
.feature file (Gherkin)
    ↓
[Agent 2: Feature → Step Definitions]
    ↓
features/steps/*_steps.py
    ↓
[Agent 3: Execution (Behave)]
    ↓
Test Results (JSON)
    ↓
[Agent 4: Reporting] ───┐
    ↓                    │
Report                   │
    ↓                    │
[Agent 5: Defects] ←─────┘
    ↓
Defect Reports
```

## Agent Details

1. **Requirements Extraction Agent** (optional)
   - **Input**: Source code, docs, or user stories
   - **Output**: Testable requirements text
   - **Key Files**: `agents/requirements_extraction_agent.py`

2. **Requirements-Aware UI Discovery Agent** (web)
   - **Input**: Requirements text + `BASE_URL`
   - **Output**: Enriched requirements, requirement→UI mapping, stats
   - **Key Files**: `agents/requirements_aware_ui_discovery_agent.py`
   - **Note**: Runs Playwright headless; requires reachable site

3. **Web Discovery Agent** (web)
   - **Input**: `BASE_URL`
   - **Output**: Deterministic page model (buttons, inputs, links, text)
   - **Key Files**: `agents/web_discovery_agent.py`

4. **UI Context Agent** (web)
   - **Input**: Requirements + page model
   - **Output**: Test intent context (no selectors/code)
   - **Key Files**: `agents/ui_context_agent.py`

5. **XPath Properties Agent** (web)
   - **Input**: `BASE_URL`
   - **Output**: `reports/ui_locators.properties` with robust selectors
   - **Key Files**: `agents/xpath_discovery_agent.py`

6. **Requirements to Feature Agent**
   - **Input**: Natural language requirements/user stories
   - **Output**: Gherkin `.feature` file
   - **AI Task**: Convert requirements into structured BDD scenarios
   - **Key Files**: `agents/requirements_to_feature_agent.py`

7. **Feature to Step Definition Agent**
   - **Input**: `.feature` file (Gherkin)
   - **Output**: Python step definitions file
   - **AI Task**: Generate Python code implementing Gherkin steps
   - **Key Files**: `agents/feature_to_stepdef_agent.py`

8. **Execution Agent**
   - **Input**: Feature files and step definitions
   - **Output**: Test execution results (JSON, console output)
   - **AI Task**: None (executes Behave)
   - **Key Files**: `agents/execution_agent.py`

9. **Reporting Agent**
   - **Input**: Test execution results
   - **Output**: Comprehensive test reports with AI insights
   - **AI Task**: Analyze results and generate insights
   - **Key Files**: `agents/reporting_agent.py`

10. **Defect Agent**
    - **Input**: Test execution results, test reports
    - **Output**: Defect reports with root cause analysis
    - **AI Task**: Identify defects, analyze failures, suggest fixes
    - **Key Files**: `agents/defect_agent.py`

## Core Components

### LLM Backends (`llm/`, `groq_client.py`)
- Groq cloud client (`groq_client.py`)
- Local TinyLlama + LoRA client (`llm/local_llm_client.py`)
- Unified client factory (`llm/__init__.py`) selects backend based on env

### Config (`config.py`)
- Centralized configuration management
- Environment variables handling
- Directory structure management

### Orchestrator (`orchestrator.py`)
- Coordinates all agents
- Manages pipeline execution
- Provides CLI interface

### RAG (`rag/`)
- Source manager loads docs, rules, examples, and optional custom docs
- Retriever uses keyword-based TF-IDF for deterministic matching
- Context builder formats retrieved docs for prompt injection

## Data Flow

1. **Requirements** → Stored in `requirements/` or passed directly
2. **RAG Sources** → Loaded from `rag/sources/`, `features/steps/`, and optional custom docs
3. **Feature Files** → Generated in `features/` directory
4. **Step Definitions** → Generated in `features/steps/` directory
5. **UI Locators (web)** → Generated in `reports/ui_locators.properties`
6. **Execution Results** → Stored in `reports/` as JSON
7. **Test Reports** → Stored in `reports/` as JSON and TXT
8. **Defect Reports** → Stored in `reports/` as JSON and TXT

## Technology Stack

- **Language**: Python 3.8+
- **AI API**: Groq (cloud) or local TinyLlama + LoRA
- **BDD Framework**: behave
- **Configuration**: python-dotenv
- **Reporting**: JSON, TXT, HTML (via behave)

## Extensibility

### Adding New Agents
1. Create new agent class in `agents/` directory
2. Inherit from base patterns (use GroqClient)
3. Add to orchestrator pipeline
4. Update documentation

### Customizing AI Behavior
- Modify `system_prompt` in each agent
- Adjust `temperature` and `max_tokens` in Config
- Change Groq model in Config (e.g., `mixtral-8x7b-32768`)
- Provide domain docs via `rag/sources/company_docs/` or `RAG_CUSTOM_PATH`

## Error Handling

- Each agent includes try-catch blocks
- Groq API errors are caught and reported
- File operations include error handling
- Execution agent handles subprocess errors
- Results include status indicators

## Performance Considerations

- AI API calls are async-capable (can be parallelized)
- File I/O is sequential
- Test execution depends on behave performance
- Reports are generated after execution completes










