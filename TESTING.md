# Testing Guide

## Quick System Test

Run the automated test script to verify everything is set up correctly:

```bash
python test_system.py
```

This script checks:
- ✓ All required modules can be imported
- ✓ All dependencies are installed
- ✓ Configuration is correct
- ✓ Directories are created
- ✓ Groq API connection works (cloud mode)
- ✓ Local model can initialize (local mode)
- ✓ All agents can be initialized
- ✓ Simple end-to-end test works

## Manual Testing Steps

### 1. Test Individual Components

#### Test Configuration
```python
from config import Config
Config.ensure_directories()
print("Backend:", "local" if Config.is_local_llm() else "cloud")
if Config.is_cloud_llm():
    print("GROQ_API_KEY:", (Config.GROQ_API_KEY[:10] + "...") if Config.GROQ_API_KEY else "(missing)")
else:
    print("LOCAL_LLM_BASE_MODEL:", Config.LOCAL_LLM_BASE_MODEL)
    print("LOCAL_LLM_LORA_PATH:", Config.LOCAL_LLM_LORA_PATH)
    print("RAG_ENABLED:", Config.RAG_ENABLED)
```

#### Test Groq API Connection (cloud mode)
```python
from groq_client import GroqClient

client = GroqClient()
response = client.generate_response("Say hello", "You are helpful")
print(response)  # Should print a response
```

#### Test Local LLM (local mode)
```python
from llm.local_llm_client import LocalLLMClient

client = LocalLLMClient()
print(client.health_check())
print(client.generate_response("Say hello", "You are helpful"))
```

#### Test Requirements to Feature Agent
```python
from agents.requirements_to_feature_agent import RequirementsToFeatureAgent

agent = RequirementsToFeatureAgent()
requirements = "As a user, I want to login so that I can access my account"
feature = agent.convert_requirements_to_feature(requirements, "login_test")
print(feature)
```

### 2. Test Full Pipeline

> For web runs, set `BASE_URL` in `.env` or `bdd.config.yaml` so discovery and Behave can reach the application.

#### Using Command Line
```bash
python orchestrator.py --requirements "As a user, I want to search for products" --feature-name search_test
```

#### Using Python Script
```python
from orchestrator import BDDAutomationOrchestrator

orchestrator = BDDAutomationOrchestrator()
results = orchestrator.run_full_pipeline(
    requirements="As a user, I want to add items to cart",
    feature_name="cart_test"
)
print(results)
```

## Expected Outputs

### Successful Test Run Should Show:

1. **Feature Generation**:
   ```
   ✓ Feature file created: features/login.feature
   ```

2. **Step Definition Generation**:
   ```
   ✓ Step definitions created: features/steps/login_steps.py
   ```

3. **(Web) UI Locator Discovery**:
   ```
   ✓ UI locators saved: reports/ui_locators.properties
   ```

4. **Test Execution**:
   ```
   ✓ Tests executed successfully
   ```

5. **Report Generation**:
   ```
   ✓ Report generated: reports/test_report_20240101_120000.json
   ✓ Summary available: reports/test_report_summary_20240101_120000.txt
   ```

6. **Defect Identification**:
   ```
   ✓ Defects identified: 0
   ```

## Troubleshooting Tests

### Issue: "GROQ_API_KEY not found"
**Solution**: 
- Create `.env` file in project root
- Add: `GROQ_API_KEY=your_actual_key_here`
- Get key from: https://console.groq.com/

### Issue: "Module not found"
**Solution**:
```bash
pip install -r requirements.txt
```

### Issue: "behave command not found"
**Solution**:
```bash
pip install behave
```

### Issue: "Import errors"
**Solution**:
- Make sure you're running from project root directory
- Check that all files are in correct locations
- Verify Python path includes project directory

### Issue: "API connection failed"
**Solution**:
- Verify API key is correct
- Check internet connection
- Verify Groq API service is available
- Check if you've reached rate limits

## Test Files Location

After running tests, check these directories:

- `features/` - Generated feature files
- `features/steps/` - Generated step definitions
- `reports/` - Test reports and execution results

## Continuous Testing

For ongoing testing, you can:

1. Run test script before each deployment:
   ```bash
   python test_system.py
   ```

2. Add to CI/CD pipeline (if applicable)

3. Run smoke test with minimal requirements:
   ```bash
   python orchestrator.py --requirements "Test" --feature-name smoke_test
   ```

## Performance Testing

To test performance with larger requirements:

```python
large_requirements = """
As an e-commerce user,
I want to:
- Browse products
- Search for items
- Filter results
- Add to cart
- Checkout
- Track orders
So that I can complete my shopping experience.
"""

orchestrator = BDDAutomationOrchestrator()
results = orchestrator.run_full_pipeline(large_requirements, "ecommerce_test")
```

## Validation Checklist

Before considering the system production-ready:

- [ ] All imports work
- [ ] Dependencies installed
- [ ] API key configured
- [ ] API connection successful
- [ ] All agents initialize
- [ ] Feature generation works
- [ ] Step definition generation works
- [ ] Test execution works
- [ ] Reports are generated
- [ ] Defects are identified
- [ ] Full pipeline completes end-to-end










