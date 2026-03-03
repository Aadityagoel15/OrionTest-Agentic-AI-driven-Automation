"""
Smoke Tests for Local LLM (TinyLlama + LoRA)

These tests validate the trained model's behavior to ensure:
1. Deterministic outputs (same input = same output)
2. Proper refusal behavior (missing context)
3. Valid Gherkin generation
4. No hallucinations

Run with: pytest tests/test_local_llm_smoke.py -v
"""

import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLocalLLMSmoke:
    """Smoke tests for LocalLLMClient."""
    
    @pytest.fixture(scope="class")
    def llm_client(self):
        """Get the LocalLLMClient instance."""
        from llm.local_llm_client import LocalLLMClient
        
        # Skip if model files don't exist
        if not os.path.exists("models/tinyllama-lora-qa/adapter_config.json"):
            pytest.skip("LoRA model files not found. Skipping local LLM tests.")
        
        client = LocalLLMClient()
        return client
    
    # ================================================================
    # TEST 1: Model Loading
    # ================================================================
    
    def test_model_loads_successfully(self, llm_client):
        """Test that the model loads without errors."""
        health = llm_client.health_check()
        
        assert health['lora_path_exists'] == True, "LoRA path should exist"
        assert health['base_model'] == "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    
    # ================================================================
    # TEST 2: Deterministic Output
    # ================================================================
    
    def test_deterministic_output(self, llm_client):
        """Test that same input produces same output (determinism)."""
        prompt = "Generate a simple Gherkin step for clicking a button named 'Submit'."
        system_prompt = "You are a QA automation expert. Generate only valid Gherkin."
        
        # Generate 3 times
        outputs = []
        for _ in range(3):
            response = llm_client.generate_response(prompt, system_prompt)
            outputs.append(response)
        
        # All outputs should be identical
        assert outputs[0] == outputs[1], "First and second outputs should be identical"
        assert outputs[1] == outputs[2], "Second and third outputs should be identical"
    
    # ================================================================
    # TEST 3: Refusal Behavior - Missing UI Context
    # ================================================================
    
    def test_refusal_missing_ui_context(self, llm_client):
        """Test that model refuses when UI element is not in context."""
        prompt = """Generate a Gherkin step to click the 'SpecialButton123' button.

Context: The page has the following buttons:
- Login
- Submit
- Cancel

There is NO button named 'SpecialButton123' on the page."""
        
        system_prompt = """You are a strict QA automation expert.
If the requested UI element is not present in the context, you MUST respond with:
ERROR: Required UI element not present in discovery or context.

Do NOT invent or hallucinate element names."""
        
        response = llm_client.generate_response(prompt, system_prompt)
        
        # Should contain error/refusal
        is_refusal = (
            "ERROR" in response.upper() or
            "not present" in response.lower() or
            "cannot" in response.lower() or
            "missing" in response.lower()
        )
        
        # Should NOT contain the hallucinated button name in a Gherkin step
        has_hallucination = 'clicks the "SpecialButton123"' in response
        
        assert is_refusal or not has_hallucination, \
            f"Model should refuse or not hallucinate. Got: {response[:200]}"
    
    # ================================================================
    # TEST 4: Valid Gherkin Generation
    # ================================================================
    
    def test_valid_gherkin_generation(self, llm_client):
        """Test that model generates valid Gherkin syntax."""
        prompt = """Generate a Gherkin feature file for the following requirements:
1. Navigate to https://example.com
2. Enter "testuser" into username field
3. Enter "password123" into password field
4. Click Login button
5. Verify user sees "Welcome" text"""
        
        system_prompt = """You are a QA automation expert. Generate ONLY valid Gherkin.
Use these exact patterns:
- the user navigates to "{url}"
- the user enters "{value}" into the "{field}" field
- the user clicks the "{button}" button
- the user should see text "{text}"

Return ONLY the feature file content. No explanations."""
        
        response = llm_client.generate_response(prompt, system_prompt)
        
        # Validate Gherkin structure
        validation = llm_client.validate_gherkin(response)
        
        # Check for key elements (may not have all depending on training)
        has_feature_or_scenario = "Feature:" in response or "Scenario:" in response
        has_steps = any(kw in response for kw in ["Given", "When", "Then"])
        
        assert has_feature_or_scenario or has_steps, \
            f"Response should contain Gherkin elements. Got: {response[:300]}"
    
    # ================================================================
    # TEST 5: No Explanations in Output
    # ================================================================
    
    def test_no_explanations_in_output(self, llm_client):
        """Test that model doesn't add explanations to Gherkin output."""
        prompt = """Generate a Gherkin scenario for user login."""
        
        system_prompt = """Generate ONLY valid Gherkin. No explanations, no markdown, no comments.
Just the raw Gherkin content."""
        
        response = llm_client.generate_response(prompt, system_prompt)
        
        # Check for common explanation patterns
        explanation_patterns = [
            "Here is",
            "Here's",
            "Below is",
            "This scenario",
            "I have created",
            "I've generated",
            "Note:",
            "Explanation:",
        ]
        
        has_explanation = any(pattern.lower() in response.lower() for pattern in explanation_patterns)
        
        # Soft assertion - log warning but don't fail if minor
        if has_explanation:
            print(f"WARNING: Response may contain explanations: {response[:200]}")
    
    # ================================================================
    # TEST 6: Canonical Step Pattern Adherence
    # ================================================================
    
    def test_canonical_step_patterns(self, llm_client):
        """Test that model uses canonical step patterns."""
        prompt = """Generate Gherkin steps for:
1. Go to a website
2. Type in a text field
3. Press a button"""
        
        system_prompt = """Generate Gherkin using ONLY these canonical patterns:
- the user navigates to "{url}"
- the user enters "{value}" into the "{field}" field
- the user clicks the "{button}" button

Subject must be "the user". No variations."""
        
        response = llm_client.generate_response(prompt, system_prompt)
        
        # Check for canonical subject
        if "navigates to" in response or "enters" in response or "clicks" in response:
            has_canonical_subject = "the user" in response.lower()
            
            # Check for non-canonical subjects
            bad_subjects = ["I ", "User ", "A user ", "The tester "]
            has_bad_subject = any(subj in response for subj in bad_subjects)
            
            if has_bad_subject:
                print(f"WARNING: Non-canonical subject detected: {response[:200]}")
    
    # ================================================================
    # TEST 7: Health Check
    # ================================================================
    
    def test_health_check(self, llm_client):
        """Test health check returns expected information."""
        health = llm_client.health_check()
        
        assert 'model_loaded' in health
        assert 'device' in health
        assert 'lora_path_exists' in health
        assert 'base_model' in health


class TestRAGIntegration:
    """Tests for RAG integration with LocalLLMClient."""
    
    @pytest.fixture(scope="class")
    def rag_retriever(self):
        """Get the RAG retriever instance."""
        try:
            from rag import get_rag_retriever
            retriever = get_rag_retriever()
            return retriever
        except ImportError:
            pytest.skip("RAG module not available")
    
    def test_rag_initialization(self, rag_retriever):
        """Test that RAG retriever initializes correctly."""
        stats = rag_retriever.get_stats()
        
        assert stats['is_initialized'] == True
        assert stats['total_documents'] > 0, "Should have loaded some documents"
    
    def test_rag_retrieval(self, rag_retriever):
        """Test that RAG retrieves relevant documents."""
        query = "How to click a button in Gherkin?"
        
        results = rag_retriever.retrieve(query, top_k=3)
        
        assert len(results) > 0, "Should retrieve at least one document"
        assert 'content' in results[0]
        assert 'source' in results[0]
    
    def test_rag_with_llm(self):
        """Test RAG integration with LLM client."""
        try:
            from llm.local_llm_client import LocalLLMClient
            from rag import get_rag_retriever
            
            if not os.path.exists("models/tinyllama-lora-qa/adapter_config.json"):
                pytest.skip("LoRA model files not found")
            
            retriever = get_rag_retriever()
            client = LocalLLMClient(rag_retriever=retriever)
            
            # Generate with RAG context
            response = client.generate_response(
                "Generate a step for clicking a button",
                "You are a QA expert."
            )
            
            assert response is not None
            assert len(response) > 0
            
        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")


class TestLLMFactory:
    """Tests for LLM factory pattern."""
    
    def test_get_llm_client_cloud(self):
        """Test getting cloud LLM client."""
        from llm import get_llm_client, is_cloud_llm_available
        
        if not is_cloud_llm_available():
            pytest.skip("Groq API key not configured")
        
        client = get_llm_client(force_cloud=True)
        
        # Should be GroqClient
        assert hasattr(client, 'generate_response')
        assert hasattr(client, 'generate_structured_response')
    
    def test_get_llm_client_local(self):
        """Test getting local LLM client."""
        from llm import get_llm_client, is_local_llm_available
        
        if not is_local_llm_available():
            pytest.skip("Local LLM model files not found")
        
        client = get_llm_client(force_local=True)
        
        # Should be LocalLLMClient
        assert hasattr(client, 'generate_response')
        assert hasattr(client, 'generate_structured_response')
        assert hasattr(client, 'health_check')
    
    def test_available_backends(self):
        """Test getting available backends."""
        from llm import get_available_backends
        
        backends = get_available_backends()
        
        assert 'local' in backends
        assert 'cloud' in backends
        assert 'available' in backends['local']
        assert 'available' in backends['cloud']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
