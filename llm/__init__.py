"""
LLM Module - Unified LLM Client Interface

This module provides a factory pattern for LLM clients, allowing seamless
switching between cloud (Groq) and local (TinyLlama + LoRA) inference.

Usage:
    from llm import get_llm_client
    
    client = get_llm_client()  # Returns appropriate client based on config
    response = client.generate_response(prompt, system_prompt)

Configuration:
    Set USE_LOCAL_LLM=true in .env or environment to use local model.
    Default is to use Groq (cloud) for backward compatibility.
"""

import os
from typing import Union

# Type alias for LLM clients
LLMClient = Union['GroqClient', 'LocalLLMClient']


def get_llm_client(force_local: bool = None, force_cloud: bool = None) -> LLMClient:
    """
    Factory function to get the appropriate LLM client.
    
    Priority:
    1. force_local/force_cloud parameters (explicit override)
    2. USE_LOCAL_LLM environment variable
    3. Default to cloud (Groq) for backward compatibility
    
    Args:
        force_local: If True, always use local model
        force_cloud: If True, always use cloud (Groq)
    
    Returns:
        LLM client instance (either GroqClient or LocalLLMClient)
    
    Raises:
        ValueError: If both force_local and force_cloud are True
    """
    if force_local and force_cloud:
        raise ValueError("Cannot force both local and cloud LLM")
    
    # Determine which client to use
    use_local = False
    
    if force_local:
        use_local = True
    elif force_cloud:
        use_local = False
    else:
        # Check environment variable
        env_value = os.getenv("USE_LOCAL_LLM", "").lower()
        use_local = env_value in ("true", "1", "yes", "on")
    
    if use_local:
        return _get_local_client()
    else:
        return _get_cloud_client()


def _get_local_client() -> 'LocalLLMClient':
    """Get the local LLM client (TinyLlama + LoRA)."""
    from llm.local_llm_client import LocalLLMClient
    
    # Check if RAG retriever should be attached
    rag_retriever = None
    try:
        from rag import get_rag_retriever
        rag_retriever = get_rag_retriever()
    except ImportError:
        print("[LLM] RAG module not found, proceeding without RAG")
    except Exception as e:
        print(f"[LLM] Failed to initialize RAG: {e}")
    
    client = LocalLLMClient(rag_retriever=rag_retriever)
    return client


def _get_cloud_client() -> 'GroqClient':
    """Get the cloud LLM client (Groq)."""
    # Import from project root
    import sys
    import os
    
    # Add parent directory to path if needed
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from groq_client import GroqClient
    return GroqClient()


# ================================================================
# CLIENT TYPE DETECTION
# ================================================================

def is_local_llm_available() -> bool:
    """Check if local LLM is available (model files exist)."""
    from llm.local_llm_client import LocalLLMClient
    
    possible_paths = [
        LocalLLMClient.DEFAULT_LORA_PATH,
        os.path.join(os.path.dirname(os.path.dirname(__file__)), LocalLLMClient.DEFAULT_LORA_PATH),
    ]
    
    for path in possible_paths:
        adapter_config = os.path.join(path, "adapter_config.json")
        adapter_model = os.path.join(path, "adapter_model.safetensors")
        if os.path.exists(adapter_config) and os.path.exists(adapter_model):
            return True
    
    return False


def is_cloud_llm_available() -> bool:
    """Check if cloud LLM (Groq) is available (API key configured)."""
    api_key = os.getenv("GROQ_API_KEY", "")
    return bool(api_key and len(api_key) > 10)


def get_available_backends() -> dict:
    """Get status of available LLM backends."""
    return {
        "local": {
            "available": is_local_llm_available(),
            "name": "TinyLlama + LoRA",
            "description": "Local inference with fine-tuned model"
        },
        "cloud": {
            "available": is_cloud_llm_available(),
            "name": "Groq",
            "description": "Cloud inference via Groq API"
        }
    }


# ================================================================
# EXPORTS
# ================================================================

__all__ = [
    'get_llm_client',
    'is_local_llm_available',
    'is_cloud_llm_available',
    'get_available_backends',
    'LLMClient',
]
