# BDD Automation Framework

A general-purpose BDD (Behavior-Driven Development) automation framework powered by pluggable LLM backends (Groq cloud or local TinyLlama + LoRA). This framework automatically generates and executes test automation for any website or API - no coding required.

## 🎯 What Can You Test?

- ✅ Web Applications - Any website (desktop or mobile web)
- ✅ REST APIs - Any API endpoint (CRUD operations, authentication, etc.)

**No hardcoding required** - Works with any URL, any credentials, any workflow!

**Locators are site-agnostic.** The framework first uses discovered selectors, then any overrides in `reports/ui_locators.properties`, then heuristic patterns (camelCase/kebab/nospace/underscore), and finally visible text. For new sites, add guaranteed selectors for critical fields/buttons to `reports/ui_locators.properties` to avoid misses.

## Overview

The system runs a coordinated pipeline:

1. **(Optional) Requirements Extraction Agent**: Pulls testable behaviors from code/docs
2. **Requirements-Aware UI Discovery (web)**: Discovers live UI elements and enriches requirements
3. **RAG + LLM Context**: Retrieves framework rules, examples, and optional custom docs to guide generation
4. **Requirements to Feature Agent**: Converts requirements/user stories into Gherkin `.feature` files
5. **Feature to Step Definition Agent**: Generates Python step definitions from feature files
6. **Execution Agent**: Executes BDD tests using the behave framework
7. **Reporting Agent**: Generates comprehensive test execution reports with AI-powered insights
8. **Defect Agent**: Analyzes failures and creates detailed defect reports

For web projects, set `BASE_URL` (or `bdd.config.yaml`) so discovery and execution can reach the application.

## Features

- Requirement extraction and feature file generation
- Live UI discovery and requirements enrichment for web apps
- Automatic step definition generation
- Automated test execution
- Reporting with AI insights
- Defect identification and analysis
- Complete pipeline automation
- Local or cloud LLM support
- RAG support with custom documentation

## Prerequisites

- Python 3.8 or higher
- Groq API key (only if using cloud) ([Get one here](https://console.groq.com/))

## 🚀 Quick Start

**New to the framework?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup instructions.

### Installation

1. **Clone or copy the project:**
   ```bash
   git clone <repository-url>
   cd "BDD Automation"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment (set `BASE_URL` for web runs):**
   ```bash
   # Copy template
   cp env_template.txt .env
   
   # Edit .env and add your Groq API key
   GROQ_API_KEY=your_groq_api_key_here
   BASE_URL=https://your-application-url.com  # Required for web discovery/execution
   ```

4. **Verify setup:**
   ```bash
   python test_system.py
   ```

5. **Run your first test:**
   ```bash
   python orchestrator.py --requirements "Navigate to https://your-app.com and click Login" --feature-name my_test
   ```

## Project Structure

```
BDD-Automation/
├── agents/                          # AI agent modules
│   ├── requirements_to_feature_agent.py
│   ├── feature_to_stepdef_agent.py
│   ├── execution_agent.py
│   ├── reporting_agent.py
│   ├── defect_agent.py
│   ├── requirements_extraction_agent.py
│   ├── web_discovery_agent.py
│   ├── ui_context_agent.py
│   ├── xpath_discovery_agent.py
│   └── requirements_aware_ui_discovery_agent.py
├── features/                        # Generated .feature files
│   └── steps/                       # Generated step definitions
├── reports/                         # Test reports, UI locators, summaries
├── requirements/                    # Input requirements files
├── config.py                        # Configuration settings
├── groq_client.py                   # Groq API client
├── orchestrator.py                  # Main orchestrator
├── behave.ini                       # Behave configuration
└── requirements.txt                 # Python dependencies
```

## Usage

## Usage Examples

### Web Application Testing

**Test any website workflow:**

```bash
python orchestrator.py --requirements "Navigate to https://example.com, click Products menu, search for 'laptop', add to cart" --feature-name web_test
```

**Using a requirements file:**

Create `requirements/my_test.txt`:
```
Navigate to the URL https://your-app.com/
Login with username "testuser" and password "testpass"
Click on the "Dashboard" button
Verify dashboard page is displayed
```

Run:
```bash
python orchestrator.py --requirements requirements/my_test.txt --feature-name my_test
```

### API Testing

Create `requirements/api_test.txt`:
```
Test POST /api/users endpoint
Request body: {"name": "John", "email": "john@example.com"}
Verify response status is 201
Verify response contains "user_id"
```

Run:
```bash
python orchestrator.py --requirements requirements/api_test.txt --feature-name api_test
```

### E-commerce Flow Example

```
Navigate to https://shop.example.com
Add to cart "Wireless Mouse"
Navigate to Cart Page
Click on Checkout button
Enter first name "John", last name "Doe", postal code "12345"
Click Continue button
Verify order confirmation
```

See example requirements in [HOW_TO_RUN.md](HOW_TO_RUN.md#-run-with-your-own-requirements).

### Individual Stages

#### 1. Requirements to Feature File

```python
from agents.requirements_to_feature_agent import RequirementsToFeatureAgent

agent = RequirementsToFeatureAgent()
requirements = "As a user, I want to search for products..."
feature_content = agent.convert_requirements_to_feature(requirements, "search_feature")
feature_file = agent.save_feature_file(feature_content, "search_feature")
```

#### 2. Feature File to Step Definitions

```python
from agents.feature_to_stepdef_agent import FeatureToStepDefAgent

agent = FeatureToStepDefAgent()
step_def_content = agent.generate_step_definitions("features/search_feature.feature")
step_def_file = agent.save_step_definitions(step_def_content, "search_feature")
```

#### 3. Execute Tests

```python
from agents.execution_agent import ExecutionAgent

agent = ExecutionAgent()
results = agent.execute_tests(feature_file="features/search_feature.feature")
```

#### 4. Generate Reports

```python
from agents.reporting_agent import ReportingAgent

agent = ReportingAgent()
report = agent.generate_report(execution_results)
```

#### 5. Identify Defects

```python
from agents.defect_agent import DefectAgent

agent = DefectAgent()
defects = agent.identify_defects(execution_results, test_report)
```

### Command Line Options

```bash
python orchestrator.py --requirements <text-or-file> --feature-name <name>
```

Arguments:
- `--requirements` (required): Inline text or path to a `.txt` file
- `--feature-name` (optional): Used for naming generated files

## Configuration

### Environment Variables (`.env` file)

```env
# Required for cloud LLM
GROQ_API_KEY=your_groq_api_key_here

# Application URL (required for web discovery/execution)
BASE_URL=https://your-application-url.com

# Optional - AI model (default: llama-3.1-8b-instant)
GROQ_MODEL=llama-3.1-8b-instant

# Optional - Local LLM and RAG settings
USE_LOCAL_LLM=false
LLM_MAX_TOKENS=4096
RAG_ENABLED=true
RAG_CUSTOM_PATH=
```

### Project Configuration (`bdd.config.yaml`)

```yaml
project:
  type: web          # api | web
  base_url: https://your-application-url.com
```

**Configuration Priority:**
1. `.env` file values (API key, BASE_URL, model, LLM/RAG settings)
2. `bdd.config.yaml` project block (`type: web` or `api`)
3. Auto-detection from requirements (fallback)

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed configuration options.

## How It Works

1. **You provide requirements** in plain English (file or command line)
2. **(Web)** UI discovery enriches requirements with real element names
3. **AI Agent 1** converts requirements → Gherkin feature files
4. **AI Agent 2** generates Python step definitions automatically
5. **AI Agent 3** executes tests using Behave
6. **AI Agent 4** generates comprehensive test reports with insights
7. **AI Agent 5** identifies and analyzes defects from failures

**No coding required** - Just write requirements in plain English!

## Output Files

All outputs are saved in their respective directories:

- **Features**: `features/*.feature`
- **Step Definitions**: `features/steps/*_steps.py`
- **Execution Reports**: `reports/execution_report_*.json` and `*.html`
- **Test Reports**: `reports/test_report_*.json` and `test_report_summary_*.txt`
- **Defect Reports**: `reports/defects_*.json` and `defect_report_*.txt`
- **UI Locators (web)**: `reports/ui_locators.properties`

## Testing the System

### Quick System Test

Run the automated test script to verify everything is set up correctly:

```bash
python test_system.py
```

This will check:
- ✓ All imports work
- ✓ Dependencies are installed
- ✓ Configuration is correct
- ✓ Groq API connection works
- ✓ All agents can be initialized
- ✓ Simple end-to-end test passes

### Manual Testing

Test the full pipeline with a simple requirement:

```bash
python orchestrator.py --requirements "As a user, I want to click a button so that I can submit a form" --feature-name test_feature
```

For detailed testing instructions, see [TESTING.md](TESTING.md)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `GROQ_API_KEY not found` | Create `.env` file and add your API key |
| `BASE_URL is required` | Set `BASE_URL` in `.env` or include URL in requirements |
| Import errors | Run `pip install -r requirements.txt` |
| Tests fail to execute | Verify application is running and `BASE_URL` is correct |
| Playwright errors | Run `pip install playwright && playwright install` |

**Still having issues?** Run `python test_system.py` to diagnose problems.

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed troubleshooting.

## Extending the System

### Adding Custom Agents

Create a new agent in the `agents/` directory:

```python
from groq_client import GroqClient

class CustomAgent:
    def __init__(self):
        self.groq_client = GroqClient()
    
    def process(self, input_data):
        # Your agent logic here
        pass
```

### Customizing Prompts

Each agent has a `system_prompt` that guides the AI. Modify these in the agent files to customize behavior.

## Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Complete setup guide for new users
- **[HOW_TO_RUN.md](HOW_TO_RUN.md)** - Usage and examples
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Pipeline and agent roles
- **[docs/LLM.md](docs/LLM.md)** - LLM backends and configuration
- **[docs/RAG.md](docs/RAG.md)** - RAG sources and customization
- **[FILE_STRUCTURE.md](FILE_STRUCTURE.md)** - Required/generated files
- **[TESTING.md](TESTING.md)** - Ways to verify the system

## 🤝 Contributing

This is a general-purpose framework designed to work with any website or API. 

**Framework Design Principles:**
- ✅ No hardcoded URLs or credentials
- ✅ Configuration-driven (no code changes needed)
- ✅ Works with any domain, any workflow (tested flows: Web, API)

## 📝 License

This project is for internal company use.

## 💬 Support

For questions or issues:
1. Check [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. Run `python test_system.py` to verify setup
3. Contact your development team

