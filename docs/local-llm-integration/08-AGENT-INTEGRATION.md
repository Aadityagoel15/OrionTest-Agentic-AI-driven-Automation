# Step 8: Integrate One Agent End-to-End

## Recommended First Agent

Start with **RequirementsToFeatureAgent** because:

1. It's the first stage in the pipeline
2. Has clear validation (`_validate_canonical_grammar`)
3. Output is easily inspectable (Gherkin text)
4. Refusal behavior is critical here

## Integration Strategy

### Option 1: Factory Pattern (Recommended)

Modify agent to use LLM factory:

```python
# agents/requirements_to_feature_agent.py
class RequirementsToFeatureAgent:
    def __init__(self):
        # OLD: self.groq_client = GroqClient()
        
        # NEW: Use factory - auto-selects based on config
        from llm import get_llm_client
        self.llm_client = get_llm_client()
```

### Option 2: Configuration Toggle

Keep both clients, switch via config:

```python
class RequirementsToFeatureAgent:
    def __init__(self):
        from config import Config
        
        if Config.is_local_llm():
            from llm.local_llm_client import LocalLLMClient
            self.llm_client = LocalLLMClient()
        else:
            from groq_client import GroqClient
            self.llm_client = GroqClient()
```

### Option 3: Dependency Injection

Pass client as parameter:

```python
class RequirementsToFeatureAgent:
    def __init__(self, llm_client=None):
        if llm_client is None:
            from llm import get_llm_client
            llm_client = get_llm_client()
        
        self.llm_client = llm_client
```

## Step-by-Step Integration

### Step 1: Update Import

```python
# Before
from groq_client import GroqClient

# After
from llm import get_llm_client
```

### Step 2: Update __init__

```python
# Before
def __init__(self):
    self.groq_client = GroqClient()

# After
def __init__(self):
    self.llm_client = get_llm_client()
```

### Step 3: Update Method Calls

```python
# Before
response = self.groq_client.generate_response(prompt, system_prompt)

# After (same interface)
response = self.llm_client.generate_response(prompt, system_prompt)
```

## Validation Checklist

After integration, validate:

### 1. Deterministic Output

Run same requirements 3 times:

```python
agent = RequirementsToFeatureAgent()

for i in range(3):
    result = agent.convert_requirements_to_feature(
        "Navigate to example.com and click Login"
    )
    print(f"Run {i+1}: {result[:100]}")
```

All outputs should be identical.

### 2. Proper Refusal Behavior

Test with impossible request:

```python
result = agent.convert_requirements_to_feature(
    "Click the NonExistentMagicButton"
)

# Should refuse or not hallucinate
assert "NonExistentMagicButton" not in result or "ERROR" in result
```

### 3. Correct Feature Generation

Test with valid requirements:

```python
result = agent.convert_requirements_to_feature("""
Navigate to https://example.com
Enter "user@test.com" into email field
Enter "password123" into password field
Click Login button
Verify "Welcome" text is shown
""")

# Validate structure
assert "Feature:" in result
assert "the user navigates to" in result
assert "the user enters" in result
assert "the user clicks" in result
```

### 4. No Hallucinations

Check output doesn't invent elements:

```python
result = agent.convert_requirements_to_feature("""
Navigate to https://example.com
Click Login button
""")

# Should only reference Login button, not invent others
mentioned_buttons = re.findall(r'clicks the "([^"]+)" button', result)
assert all(btn in ["Login"] for btn in mentioned_buttons)
```

## Comparison Testing

Run both backends and compare:

```python
def compare_backends(requirements):
    from config import Config, LLMBackend
    
    # Test with cloud
    Config.set_llm_backend(LLMBackend.CLOUD)
    agent_cloud = RequirementsToFeatureAgent()
    result_cloud = agent_cloud.convert_requirements_to_feature(requirements)
    
    # Test with local
    Config.set_llm_backend(LLMBackend.LOCAL)
    agent_local = RequirementsToFeatureAgent()
    result_local = agent_local.convert_requirements_to_feature(requirements)
    
    print("=== CLOUD ===")
    print(result_cloud)
    print("\n=== LOCAL ===")
    print(result_local)
    
    # Compare key elements
    cloud_steps = len(re.findall(r'(Given|When|Then)', result_cloud))
    local_steps = len(re.findall(r'(Given|When|Then)', result_local))
    
    print(f"\nCloud steps: {cloud_steps}, Local steps: {local_steps}")
```

## Integration Test

```python
# tests/test_agent_integration.py

def test_requirements_agent_with_local_llm():
    """Test RequirementsToFeatureAgent with local LLM."""
    import os
    os.environ["USE_LOCAL_LLM"] = "true"
    
    from agents.requirements_to_feature_agent import RequirementsToFeatureAgent
    
    agent = RequirementsToFeatureAgent()
    
    requirements = """
    Navigate to https://example.com
    Enter "testuser" into username field
    Enter "password" into password field
    Click Login button
    """
    
    result = agent.convert_requirements_to_feature(requirements)
    
    # Basic validation
    assert result is not None
    assert len(result) > 50
    
    # Structure validation
    assert "Feature:" in result or "Scenario:" in result
    
    # Step validation
    assert "the user" in result.lower()
```

## Rollback Plan

If issues occur, rollback to cloud:

```python
# Quick rollback
os.environ["USE_LOCAL_LLM"] = "false"

# Or in config
Config.set_llm_backend(LLMBackend.CLOUD)
```

## Gradual Rollout

### Phase 1: Shadow Mode

Run both, compare results, log differences:

```python
def convert_with_shadow(self, requirements):
    # Primary: Cloud
    result_primary = self.cloud_client.generate_response(...)
    
    # Shadow: Local (don't use result, just log)
    try:
        result_shadow = self.local_client.generate_response(...)
        self._log_comparison(result_primary, result_shadow)
    except Exception as e:
        self._log_shadow_failure(e)
    
    return result_primary
```

### Phase 2: Percentage Rollout

Route percentage of requests to local:

```python
import random

def get_client(self):
    if random.random() < 0.1:  # 10% to local
        return self.local_client
    return self.cloud_client
```

### Phase 3: Full Migration

Switch all traffic to local:

```python
USE_LOCAL_LLM=true
```

## Monitoring

Track key metrics after integration:

```python
class AgentMetrics:
    def __init__(self):
        self.generation_times = []
        self.success_count = 0
        self.failure_count = 0
        self.refusal_count = 0
    
    def record(self, result, duration):
        self.generation_times.append(duration)
        
        if "ERROR:" in result:
            self.refusal_count += 1
        elif self._is_valid_gherkin(result):
            self.success_count += 1
        else:
            self.failure_count += 1
    
    def summary(self):
        return {
            "avg_time": sum(self.generation_times) / len(self.generation_times),
            "success_rate": self.success_count / (self.success_count + self.failure_count),
            "refusal_rate": self.refusal_count / len(self.generation_times)
        }
```
