# Step 9: Add Guardrails

## Purpose

Guardrails ensure the model produces safe, valid, and useful outputs. They act as a safety net between model generation and agent consumption.

## Mandatory Guardrails

### 1. Deterministic Generation

```python
# CRITICAL: These settings MUST be enforced
DO_SAMPLE = False       # Greedy decoding only
TEMPERATURE = 0.0       # No randomness
TOP_P = 1.0            # No nucleus sampling
TOP_K = 1              # Only top token
```

These settings are hardcoded in LocalLLMClient and cannot be overridden.

### 2. Schema Validation

Validate generated content matches expected format.

#### Gherkin Validation

```python
def validate_gherkin(self, content: str) -> Dict[str, Any]:
    errors = []
    
    # Must have Feature keyword
    if not re.search(r'^Feature:', content, re.MULTILINE):
        errors.append("Missing 'Feature:' keyword")
    
    # Must have at least one Scenario
    if not re.search(r'^\s*Scenario:', content, re.MULTILINE):
        errors.append("Missing 'Scenario:' keyword")
    
    # Must have step keywords
    if not re.search(r'^\s*(Given|When|Then|And|But)\s+', content, re.MULTILINE):
        errors.append("No valid step keywords found")
    
    return {'valid': len(errors) == 0, 'errors': errors}
```

#### Step Definition Validation

```python
def validate_step_definitions(self, content: str) -> Dict[str, Any]:
    errors = []
    
    # Must have decorators
    if '@given' not in content.lower() and '@when' not in content.lower():
        errors.append("Missing step decorators")
    
    # Must have functions
    if 'def ' not in content:
        errors.append("No function definitions found")
    
    return {'valid': len(errors) == 0, 'errors': errors}
```

### 3. Refusal Detection

Recognize when model properly refuses:

```python
REFUSAL_PATTERNS = [
    r"ERROR:\s*Required UI element not present",
    r"ERROR:\s*Missing required context",
    r"ERROR:\s*Cannot generate without",
    r"REFUSE:\s*",
    r"I cannot generate .* without",
]

def _is_refusal(self, response: str) -> bool:
    for pattern in self.REFUSAL_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            return True
    return False
```

Refusal is **expected behavior**, not an error.

### 4. Output Length Validation

```python
def _validate_length(self, response: str) -> bool:
    # Too short - likely incomplete
    if len(response.strip()) < 10:
        return False
    
    # Too long - likely hallucinating
    if len(response) > 50000:
        return False
    
    return True
```

### 5. Hallucination Detection

Flag potential hallucinations:

```python
HALLUCINATION_INDICATORS = [
    "I think",
    "I believe",
    "probably",
    "maybe",
    "I'm not sure",
    "I don't have access",
    "based on my training",
    "as an AI",
]

def _check_hallucination(self, response: str) -> List[str]:
    warnings = []
    for indicator in self.HALLUCINATION_INDICATORS:
        if indicator.lower() in response.lower():
            warnings.append(f"Possible hallucination: '{indicator}'")
    return warnings
```

## Guardrail Pipeline

```
Model Output
     │
     ▼
┌────────────────────┐
│ 1. Check Refusal   │──► If refusal, return as-is
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ 2. Validate Length │──► If too short/long, return error
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ 3. Check Hallucin. │──► Log warnings (don't block)
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ 4. Clean Response  │──► Remove artifacts
└────────────────────┘
     │
     ▼
┌────────────────────┐
│ 5. Schema Validate │──► Validate format
└────────────────────┘
     │
     ▼
Clean Response
```

## Implementation

```python
def _apply_guardrails(self, response: str, original_prompt: str) -> str:
    """Apply all guardrails to model output."""
    
    # 1. Check for refusal (expected behavior)
    if self._is_refusal(response):
        return response  # Return refusal as-is
    
    # 2. Validate length
    if len(response.strip()) < 10:
        return "ERROR: Generated output too short. Missing required context."
    
    if len(response) > 50000:
        return "ERROR: Generated output exceeds maximum length."
    
    # 3. Check for hallucination indicators (log, don't block)
    warnings = self._check_hallucination(response)
    for warning in warnings:
        print(f"[LocalLLM] WARNING: {warning}")
    
    # 4. Clean response
    response = self._clean_response(response)
    
    return response

def _clean_response(self, response: str) -> str:
    """Remove formatting artifacts."""
    # Remove leaked special tokens
    response = re.sub(r'</s>.*$', '', response, flags=re.DOTALL)
    response = re.sub(r'<\|.*?\|>', '', response)
    
    # Remove excessive whitespace
    response = re.sub(r'\n{3,}', '\n\n', response)
    
    return response.strip()
```

## Agent-Level Guardrails

Agents can add their own guardrails:

```python
class RequirementsToFeatureAgent:
    def convert_requirements_to_feature(self, requirements):
        response = self.llm_client.generate_response(...)
        
        # Agent-specific validation
        validation = self.llm_client.validate_gherkin(response)
        
        if not validation['valid']:
            raise FeatureGenerationError(
                f"Invalid Gherkin: {validation['errors']}"
            )
        
        # Additional agent-level normalization
        response = self._normalize_subject(response)
        response = self._validate_canonical_grammar(response)
        
        return response
```

## Configuration

### Environment Variables

```bash
# .env
GUARDRAIL_MIN_LENGTH=10
GUARDRAIL_MAX_LENGTH=50000
GUARDRAIL_STRICT_MODE=true
```

### Strict Mode

In strict mode, hallucination indicators cause rejection:

```python
if Config.GUARDRAIL_STRICT_MODE:
    if self._check_hallucination(response):
        return "ERROR: Response contains uncertainty indicators."
```

## Logging and Monitoring

```python
class GuardrailMetrics:
    def __init__(self):
        self.total_checks = 0
        self.refusals = 0
        self.length_failures = 0
        self.hallucination_warnings = 0
        self.cleaning_applied = 0
    
    def record(self, check_type, result):
        self.total_checks += 1
        if check_type == 'refusal' and result:
            self.refusals += 1
        # ... etc
    
    def report(self):
        return {
            'total': self.total_checks,
            'refusal_rate': self.refusals / self.total_checks,
            'hallucination_warning_rate': self.hallucination_warnings / self.total_checks
        }
```

## Testing Guardrails

```python
def test_guardrail_refusal_detection():
    client = LocalLLMClient()
    
    # Test refusal patterns
    assert client._is_refusal("ERROR: Required UI element not present")
    assert client._is_refusal("I cannot generate steps without context")
    assert not client._is_refusal("When the user clicks the button")

def test_guardrail_length_validation():
    client = LocalLLMClient()
    
    # Too short
    result = client._apply_guardrails("Hi", "prompt")
    assert "ERROR" in result
    
    # Valid length
    result = client._apply_guardrails("When the user clicks the button", "prompt")
    assert "ERROR" not in result

def test_guardrail_hallucination_warning():
    client = LocalLLMClient()
    
    warnings = client._check_hallucination("I think this might work")
    assert len(warnings) > 0
```

## Best Practices

1. **Don't over-block**: Guardrails should prevent bad outputs, not good ones
2. **Log everything**: Track what's being caught for model improvement
3. **Fail gracefully**: Return meaningful errors, not crashes
4. **Layer guardrails**: Client-level + Agent-level for defense in depth
5. **Test guardrails**: Ensure they catch what they should
