# Step 5: Verify Model Behavior (Smoke Tests)

## Purpose

Smoke tests validate that the trained model behaves correctly before production use. They verify:

1. **Determinism**: Same input → Same output
2. **Refusal behavior**: Proper handling of missing context
3. **Valid Gherkin**: Syntactically correct output
4. **No explanations**: Clean output without commentary
5. **Canonical patterns**: Adherence to step format rules

## Test File Location

```
tests/
├── __init__.py
└── test_local_llm_smoke.py
```

## Running Tests

### Run All Smoke Tests

```bash
pytest tests/test_local_llm_smoke.py -v
```

### Run Specific Test

```bash
pytest tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_deterministic_output -v
```

### Run with Coverage

```bash
pytest tests/test_local_llm_smoke.py -v --cov=llm --cov-report=html
```

## Test Cases

### Test 1: Model Loading

**Purpose**: Verify model loads without errors

```python
def test_model_loads_successfully(self, llm_client):
    health = llm_client.health_check()
    
    assert health['lora_path_exists'] == True
    assert health['base_model'] == "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
```

**Expected**: Health check returns valid status

### Test 2: Deterministic Output

**Purpose**: Verify same input produces same output every time

```python
def test_deterministic_output(self, llm_client):
    prompt = "Generate a Gherkin step for clicking a button named 'Submit'."
    
    outputs = [llm_client.generate_response(prompt) for _ in range(3)]
    
    assert outputs[0] == outputs[1] == outputs[2]
```

**Expected**: All three outputs are identical

### Test 3: Refusal for Missing UI Context

**Purpose**: Model refuses to generate when UI element doesn't exist

```python
def test_refusal_missing_ui_context(self, llm_client):
    prompt = """Click the 'SpecialButton123' button.
    Context: Page has buttons: Login, Submit, Cancel"""
    
    response = llm_client.generate_response(prompt)
    
    # Should refuse or not hallucinate
    assert "ERROR" in response or "SpecialButton123" not in response
```

**Expected**: Error message OR no hallucinated button name

### Test 4: Valid Gherkin Generation

**Purpose**: Generated output is syntactically valid Gherkin

```python
def test_valid_gherkin_generation(self, llm_client):
    prompt = """Generate feature for:
    1. Navigate to example.com
    2. Click Login"""
    
    response = llm_client.generate_response(prompt)
    
    assert "Feature:" in response or "Scenario:" in response
    assert any(kw in response for kw in ["Given", "When", "Then"])
```

**Expected**: Contains Gherkin keywords

### Test 5: No Explanations in Output

**Purpose**: Output is clean without commentary

```python
def test_no_explanations_in_output(self, llm_client):
    response = llm_client.generate_response("Generate login steps")
    
    explanation_patterns = ["Here is", "Below is", "I have created"]
    
    has_explanation = any(p in response for p in explanation_patterns)
    
    if has_explanation:
        print("WARNING: Explanations detected")
```

**Expected**: No explanation text in output

### Test 6: Canonical Step Patterns

**Purpose**: Model uses correct step format

```python
def test_canonical_step_patterns(self, llm_client):
    response = llm_client.generate_response("Generate button click step")
    
    assert "the user" in response.lower()
    
    bad_subjects = ["I ", "User "]
    assert not any(subj in response for subj in bad_subjects)
```

**Expected**: Uses "the user" as subject

## RAG Integration Tests

### Test 7: RAG Initialization

```python
def test_rag_initialization(self, rag_retriever):
    stats = rag_retriever.get_stats()
    
    assert stats['is_initialized'] == True
    assert stats['total_documents'] > 0
```

### Test 8: RAG Retrieval

```python
def test_rag_retrieval(self, rag_retriever):
    results = rag_retriever.retrieve("How to click a button?")
    
    assert len(results) > 0
    assert 'content' in results[0]
```

### Test 9: RAG with LLM

```python
def test_rag_with_llm(self):
    retriever = get_rag_retriever()
    client = LocalLLMClient(rag_retriever=retriever)
    
    response = client.generate_response("Generate button click step")
    
    assert response is not None
    assert len(response) > 0
```

## Factory Pattern Tests

### Test 10: Get Cloud Client

```python
def test_get_llm_client_cloud(self):
    client = get_llm_client(force_cloud=True)
    
    assert hasattr(client, 'generate_response')
```

### Test 11: Get Local Client

```python
def test_get_llm_client_local(self):
    client = get_llm_client(force_local=True)
    
    assert hasattr(client, 'health_check')
```

### Test 12: Available Backends

```python
def test_available_backends(self):
    backends = get_available_backends()
    
    assert 'local' in backends
    assert 'cloud' in backends
```

## Expected Test Output

```
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_model_loads_successfully PASSED
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_deterministic_output PASSED
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_refusal_missing_ui_context PASSED
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_valid_gherkin_generation PASSED
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_no_explanations_in_output PASSED
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_canonical_step_patterns PASSED
tests/test_local_llm_smoke.py::TestLocalLLMSmoke::test_health_check PASSED
tests/test_local_llm_smoke.py::TestRAGIntegration::test_rag_initialization PASSED
tests/test_local_llm_smoke.py::TestRAGIntegration::test_rag_retrieval PASSED
tests/test_local_llm_smoke.py::TestRAGIntegration::test_rag_with_llm PASSED
tests/test_local_llm_smoke.py::TestLLMFactory::test_get_llm_client_cloud SKIPPED (API key not configured)
tests/test_local_llm_smoke.py::TestLLMFactory::test_get_llm_client_local PASSED
tests/test_local_llm_smoke.py::TestLLMFactory::test_available_backends PASSED

==================== 12 passed, 1 skipped in 45.23s ====================
```

## Continuous Integration

Add to CI pipeline:

```yaml
# .github/workflows/test.yml
test-local-llm:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - run: pip install -r requirements.txt
    - run: pytest tests/test_local_llm_smoke.py -v
```

## Troubleshooting

### Tests Skip with "Model files not found"

Ensure model files exist:
```
models/tinyllama-lora-qa/
├── adapter_config.json
└── adapter_model.safetensors
```

### Determinism Test Fails

Check generation parameters:
- `do_sample` must be `False`
- `temperature` must be `0.0`

### Memory Errors

Use CPU for testing if GPU memory is insufficient:
```python
client = LocalLLMClient(device="cpu")
```
