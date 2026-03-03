"""
LocalLLMClient - Local TinyLlama + LoRA Model Client for QA Automation

This module provides a drop-in replacement for GroqClient using a locally
hosted TinyLlama model with a LoRA adapter trained for QA automation tasks.

CRITICAL DESIGN DECISIONS:
1. Tokenizer ALWAYS loaded from BASE model (not LoRA)
2. Deterministic generation (temperature=0, do_sample=False)
3. Interface matches GroqClient exactly for seamless swapping
4. RAG context injection happens BEFORE model generation
5. Guardrails validate output before returning
"""

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
import json
import re
import os
from typing import Optional, Dict, Any

# Reproducibility seed
RANDOM_SEED = 42


class LocalLLMClient:
    """
    Local LLM Client using TinyLlama + LoRA for QA Automation.
    
    This client mirrors the GroqClient interface exactly, allowing
    seamless swapping between cloud and local inference.
    
    Features:
    - Deterministic generation (no sampling)
    - RAG context injection
    - Output guardrails and validation
    - Refusal detection for missing context
    """
    
    # ================================================================
    # CONFIGURATION
    # ================================================================
    DEFAULT_BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    DEFAULT_LORA_PATH = "models/tinyllama-lora-qa"
    
    # Generation parameters (DETERMINISTIC)
    DEFAULT_MAX_TOKENS = 4096
    TEMPERATURE = 0.0  # No randomness
    DO_SAMPLE = False  # Greedy decoding
    TOP_P = 1.0
    TOP_K = 1
    REPETITION_PENALTY = 1.0
    
    # Guardrail patterns
    REFUSAL_PATTERNS = [
        r"ERROR:\s*Required UI element not present",
        r"ERROR:\s*Missing required context",
        r"ERROR:\s*Cannot generate without",
        r"REFUSE:\s*",
        r"I cannot generate .* without",
    ]
    
    def __init__(
        self,
        base_model_name: str = None,
        lora_path: str = None,
        max_tokens: int = None,
        rag_retriever: Optional[Any] = None,
        device: str = None
    ):
        """
        Initialize the Local LLM Client.
        
        Args:
            base_model_name: HuggingFace model name for base model
            lora_path: Path to LoRA adapter files
            max_tokens: Maximum tokens to generate
            rag_retriever: Optional RAG retriever for context injection
            device: Device to run on ('cuda', 'cpu', or 'auto')
        """
        # Set reproducibility
        torch.manual_seed(RANDOM_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(RANDOM_SEED)
        
        # Configuration
        self.base_model_name = base_model_name or self.DEFAULT_BASE_MODEL
        self.lora_path = lora_path or self._resolve_lora_path()
        if max_tokens is None:
            env_max_tokens = os.getenv("LLM_MAX_TOKENS")
            if env_max_tokens:
                try:
                    max_tokens = int(env_max_tokens)
                except ValueError:
                    pass
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.rag_retriever = rag_retriever
        
        # Determine device
        if device:
            self.device = device
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        
        # Model loading state
        self._model = None
        self._tokenizer = None
        self._is_loaded = False
        
        # Lazy loading - don't load until first use
        # This allows configuration before heavy model loading
    
    def _resolve_lora_path(self) -> str:
        """Resolve the LoRA path relative to project root."""
        # Try multiple possible locations
        possible_paths = [
            self.DEFAULT_LORA_PATH,
            os.path.join(os.path.dirname(os.path.dirname(__file__)), self.DEFAULT_LORA_PATH),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), self.DEFAULT_LORA_PATH),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Return default, will fail at load time if not found
        return self.DEFAULT_LORA_PATH
    
    def _ensure_loaded(self):
        """Lazy load model and tokenizer on first use."""
        if self._is_loaded:
            return
        
        print(f"[LocalLLM] Loading tokenizer from: {self.base_model_name}")
        
        # 1. Tokenizer from BASE model (CRITICAL - never from LoRA)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_name,
            trust_remote_code=True
        )
        
        # Ensure pad token exists
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        
        print(f"[LocalLLM] Loading base model: {self.base_model_name}")
        
        # 2. Load base model
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            torch_dtype=dtype,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True
        )
        
        if self.device == "cpu":
            base_model = base_model.to("cpu")
        
        print(f"[LocalLLM] Attaching LoRA adapter from: {self.lora_path}")
        
        # 3. Attach LoRA adapter
        if os.path.exists(self.lora_path):
            self._model = PeftModel.from_pretrained(base_model, self.lora_path)
        else:
            print(f"[LocalLLM] WARNING: LoRA path not found, using base model only")
            self._model = base_model
        
        # 4. Set to evaluation mode (CRITICAL for determinism)
        self._model.eval()
        
        self._is_loaded = True
        print(f"[LocalLLM] Model loaded successfully on {self.device}")
    
    @property
    def model(self):
        """Get the model, loading if necessary."""
        self._ensure_loaded()
        return self._model
    
    @property
    def tokenizer(self):
        """Get the tokenizer, loading if necessary."""
        self._ensure_loaded()
        return self._tokenizer
    
    # ================================================================
    # PUBLIC API (Matches GroqClient interface)
    # ================================================================
    
    def generate_response(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate response from the local LLM.
        
        This method matches GroqClient.generate_response() exactly.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Generated response text
        """
        # 1. Inject RAG context if retriever is available
        enriched_prompt = self._inject_rag_context(prompt, system_prompt)
        
        # 2. Format prompt for TinyLlama chat format
        formatted_prompt = self._format_chat_prompt(enriched_prompt, system_prompt)
        
        # 3. Generate with deterministic settings
        response = self._generate_deterministic(formatted_prompt)
        
        # 4. Apply guardrails
        validated_response = self._apply_guardrails(response, prompt)
        
        return validated_response
    
    def generate_structured_response(self, prompt: str, system_prompt: str = None) -> dict:
        """
        Generate structured JSON response.
        
        This method matches GroqClient.generate_structured_response() exactly.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Parsed JSON response
        """
        response_text = self.generate_response(prompt, system_prompt)
        
        try:
            # Try to extract JSON from response if wrapped in markdown
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If not valid JSON, return as text
            return {"response": response_text}
    
    # ================================================================
    # RAG INTEGRATION
    # ================================================================
    
    def set_rag_retriever(self, retriever):
        """Set the RAG retriever for context injection."""
        self.rag_retriever = retriever
    
    def _inject_rag_context(self, prompt: str, system_prompt: str = None) -> str:
        """
        Inject RAG-retrieved context into the prompt.
        
        RAG is applied at INFERENCE time, not training time.
        Retrieved context is prepended to provide grounding.
        """
        if self.rag_retriever is None:
            return prompt
        
        try:
            # Retrieve relevant context
            retrieved_docs = self.rag_retriever.retrieve(prompt, top_k=5)
            
            if not retrieved_docs:
                return prompt
            
            # Build context block
            context_block = "=== RETRIEVED CONTEXT ===\n"
            for i, doc in enumerate(retrieved_docs, 1):
                context_block += f"\n[Source {i}]: {doc.get('source', 'unknown')}\n"
                context_block += doc.get('content', '') + "\n"
            context_block += "\n=== END CONTEXT ===\n\n"
            
            # Prepend context to prompt
            return context_block + prompt
            
        except Exception as e:
            print(f"[LocalLLM] RAG retrieval failed: {e}")
            return prompt
    
    # ================================================================
    # PROMPT FORMATTING
    # ================================================================
    
    def _format_chat_prompt(self, prompt: str, system_prompt: str = None) -> str:
        """
        Format prompt for TinyLlama chat format.
        
        TinyLlama uses the ChatML format:
        <|system|>
        {system_message}</s>
        <|user|>
        {user_message}</s>
        <|assistant|>
        """
        formatted = ""
        
        if system_prompt:
            formatted += f"<|system|>\n{system_prompt}</s>\n"
        
        formatted += f"<|user|>\n{prompt}</s>\n<|assistant|>\n"
        
        return formatted
    
    # ================================================================
    # DETERMINISTIC GENERATION
    # ================================================================
    
    def _generate_deterministic(self, formatted_prompt: str) -> str:
        """
        Generate response with deterministic settings.
        
        CRITICAL: These settings ensure reproducible outputs:
        - do_sample=False: Greedy decoding (always pick highest probability)
        - temperature=0: No randomness in probability distribution
        - top_k=1: Only consider the top token
        - top_p=1.0: No nucleus sampling
        """
        self._ensure_loaded()
        
        # Tokenize input
        max_input_length = max(1, 2048 - min(self.max_tokens, 2048))
        inputs = self._tokenizer(
            formatted_prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_input_length  # Reserve space for generation
        ).to(self._model.device)
        
        # Generate with deterministic settings
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=min(self.max_tokens, 2048),
                do_sample=self.DO_SAMPLE,
                temperature=self.TEMPERATURE,
                top_p=self.TOP_P,
                top_k=self.TOP_K,
                repetition_penalty=self.REPETITION_PENALTY,
                pad_token_id=self._tokenizer.pad_token_id,
                eos_token_id=self._tokenizer.eos_token_id,
            )
        
        # Decode response (skip input tokens)
        input_length = inputs['input_ids'].shape[1]
        generated_tokens = outputs[0][input_length:]
        response = self._tokenizer.decode(generated_tokens, skip_special_tokens=True)
        
        return response.strip()
    
    # ================================================================
    # GUARDRAILS
    # ================================================================
    
    def _apply_guardrails(self, response: str, original_prompt: str) -> str:
        """
        Apply guardrails to validate and clean response.
        
        Guardrails:
        1. Check for refusal patterns (proper behavior for missing context)
        2. Validate output length
        3. Check for hallucination indicators
        4. Clean formatting artifacts
        """
        # Check for refusal (this is EXPECTED behavior for missing context)
        if self._is_refusal(response):
            return response  # Return refusal as-is
        
        # Validate minimum length
        if len(response.strip()) < 10:
            return "ERROR: Generated output too short. Missing required context."
        
        # Check for common hallucination indicators
        hallucination_indicators = [
            "I think",
            "I believe",
            "probably",
            "maybe",
            "I'm not sure",
            "I don't have access",
        ]
        
        for indicator in hallucination_indicators:
            if indicator.lower() in response.lower():
                print(f"[LocalLLM] WARNING: Possible hallucination detected: '{indicator}'")
        
        # Clean formatting artifacts
        response = self._clean_response(response)
        
        return response
    
    def _is_refusal(self, response: str) -> bool:
        """Check if response is a proper refusal."""
        for pattern in self.REFUSAL_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                return True
        return False
    
    def _clean_response(self, response: str) -> str:
        """Clean formatting artifacts from response."""
        # Remove any trailing special tokens that leaked through
        response = re.sub(r'</s>.*$', '', response, flags=re.DOTALL)
        response = re.sub(r'<\|.*?\|>', '', response)
        
        # Remove excessive whitespace
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        return response.strip()
    
    # ================================================================
    # VALIDATION UTILITIES
    # ================================================================
    
    def validate_gherkin(self, content: str) -> Dict[str, Any]:
        """
        Validate generated Gherkin content.
        
        Returns:
            Dict with 'valid' boolean and 'errors' list
        """
        errors = []
        
        # Check for Feature keyword
        if not re.search(r'^Feature:', content, re.MULTILINE):
            errors.append("Missing 'Feature:' keyword")
        
        # Check for at least one Scenario
        if not re.search(r'^\s*Scenario:', content, re.MULTILINE):
            errors.append("Missing 'Scenario:' keyword")
        
        # Check for proper step keywords
        step_pattern = r'^\s*(Given|When|Then|And|But)\s+'
        if not re.search(step_pattern, content, re.MULTILINE):
            errors.append("No valid step keywords found")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def validate_step_definitions(self, content: str) -> Dict[str, Any]:
        """
        Validate generated step definition content.
        
        Returns:
            Dict with 'valid' boolean and 'errors' list
        """
        errors = []
        
        # Check for behave imports
        if '@given' not in content.lower() and '@when' not in content.lower():
            errors.append("Missing step decorators (@given, @when, @then)")
        
        # Check for function definitions
        if 'def ' not in content:
            errors.append("No function definitions found")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    # ================================================================
    # HEALTH CHECK
    # ================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the model.
        
        Returns:
            Dict with health status information
        """
        status = {
            'model_loaded': self._is_loaded,
            'device': self.device,
            'lora_path_exists': os.path.exists(self.lora_path),
            'base_model': self.base_model_name,
        }
        
        if self._is_loaded:
            status['memory_allocated'] = f"{torch.cuda.memory_allocated() / 1e9:.2f} GB" if self.device == "cuda" else "N/A"
        
        return status
