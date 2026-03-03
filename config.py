"""
Configuration settings for BDD Automation AI Agents
(SINGLE SOURCE OF TRUTH – RUNTIME + SUBPROCESS SAFE)
"""

import os
from dotenv import load_dotenv

# Load base environment first (general settings)
load_dotenv()

# Load LLM-specific environment file if provided (non-hidden support)
llm_env_file = os.getenv("LLM_ENV_FILE", "llm.env.example")
if os.path.exists(llm_env_file):
    load_dotenv(dotenv_path=llm_env_file, override=True)

# ------------------------------------------------------------------
# Project Type
# ------------------------------------------------------------------
class ProjectType:
    API = "api"
    WEB = "web"
    MOBILE = "mobile"
    DATA = "data"
    BACKEND = "backend"
    UNKNOWN = "unknown"


# ------------------------------------------------------------------
# Execution Mode
# ------------------------------------------------------------------
class ExecutionMode:
    """
    FRAMEWORK → generation, analysis, discovery (NO REAL EXECUTION)
    PROJECT   → real execution (browser / API)
    """
    FRAMEWORK = "framework"
    PROJECT = "project"


# ------------------------------------------------------------------
# LLM Backend Selection
# ------------------------------------------------------------------
class LLMBackend:
    """
    LLM backend selection.
    LOCAL  → TinyLlama + LoRA (deterministic, no API costs)
    CLOUD  → Groq API (faster, requires API key)
    """
    LOCAL = "local"
    CLOUD = "cloud"


class Config:
    """Runtime-safe + subprocess-safe configuration"""

    # ------------------------------------------------------------------
    # LLM Configuration
    # ------------------------------------------------------------------
    # Backend selection: "local" or "cloud"
    USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "false").lower() in ("true", "1", "yes", "on")
    LLM_BACKEND = os.getenv("LLM_BACKEND", LLMBackend.CLOUD if not os.getenv("USE_LOCAL_LLM", "false").lower() in ("true", "1", "yes", "on") else LLMBackend.LOCAL)
    
    # ------------------------------------------------------------------
    # Cloud LLM (Groq) Settings
    # ------------------------------------------------------------------
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    
    # ------------------------------------------------------------------
    # Local LLM (TinyLlama + LoRA) Settings
    # ------------------------------------------------------------------
    LOCAL_LLM_BASE_MODEL = os.getenv("LOCAL_LLM_BASE_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    LOCAL_LLM_LORA_PATH = os.getenv("LOCAL_LLM_LORA_PATH", "models/tinyllama-lora-qa")
    LOCAL_LLM_DEVICE = os.getenv("LOCAL_LLM_DEVICE", "auto")  # "auto", "cuda", "cpu"
    
    # ------------------------------------------------------------------
    # Shared LLM Settings (apply to both backends)
    # ------------------------------------------------------------------
    # For local LLM: temperature=0, do_sample=False (deterministic)
    # For cloud LLM: temperature can be configured
    TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.0 if os.getenv("USE_LOCAL_LLM", "false").lower() in ("true", "1", "yes", "on") else 0.7))
    MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 4096))
    
    # ------------------------------------------------------------------
    # RAG Configuration
    # ------------------------------------------------------------------
    RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in ("true", "1", "yes", "on")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", 5))
    RAG_MAX_CONTEXT_TOKENS = int(os.getenv("RAG_MAX_CONTEXT_TOKENS", 1000))

    # ------------------------------------------------------------------
    # 🔒 RUNTIME STATE (IN-MEMORY CACHE)
    # ------------------------------------------------------------------
    _PROJECT_TYPE = ProjectType.UNKNOWN
    _EXECUTION_MODE = ExecutionMode.PROJECT

    BASE_URL = os.getenv("BASE_URL", "")

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FEATURES_DIR = os.path.join(BASE_DIR, "features")
    STEP_DEFINITIONS_DIR = os.path.join(BASE_DIR, "features", "steps")
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")
    REQUIREMENTS_DIR = os.path.join(BASE_DIR, "requirements")

    # ------------------------------------------------------------------
    # Directory bootstrap
    # ------------------------------------------------------------------
    @classmethod
    def ensure_directories(cls):
        for directory in (
            cls.FEATURES_DIR,
            cls.STEP_DEFINITIONS_DIR,
            cls.REPORTS_DIR,
            cls.REQUIREMENTS_DIR,
        ):
            os.makedirs(directory, exist_ok=True)

    # ------------------------------------------------------------------
    # ✅ PROJECT TYPE (RUNTIME + SUBPROCESS SAFE)
    # ------------------------------------------------------------------
    @classmethod
    def set_project_type(cls, project_type: str):
        project_type = (project_type or "").lower()

        resolved = (
            project_type
            if project_type in {
                ProjectType.API,
                ProjectType.WEB,
                ProjectType.MOBILE,
                ProjectType.DATA,
                ProjectType.BACKEND,
            }
            else ProjectType.UNKNOWN
        )

        cls._PROJECT_TYPE = resolved

        # 🔥 Persist for Behave subprocess
        os.environ["BDD_PROJECT_TYPE"] = resolved

    @classmethod
    def get_project_type(cls) -> str:
        """
        Priority:
        1. In-memory runtime state
        2. Environment variable (subprocess-safe)
        3. UNKNOWN fallback
        """

        if cls._PROJECT_TYPE != ProjectType.UNKNOWN:
            return cls._PROJECT_TYPE

        env_type = os.getenv("BDD_PROJECT_TYPE", "").lower()
        if env_type in {
            ProjectType.API,
            ProjectType.WEB,
            ProjectType.MOBILE,
            ProjectType.DATA,
            ProjectType.BACKEND,
        }:
            cls._PROJECT_TYPE = env_type
            return env_type

        return ProjectType.UNKNOWN

    # ------------------------------------------------------------------
    # ✅ EXECUTION MODE (RUNTIME + SUBPROCESS SAFE)
    # ------------------------------------------------------------------
    @classmethod
    def set_execution_mode(cls, mode: str):
        resolved = (
            mode
            if mode in (ExecutionMode.FRAMEWORK, ExecutionMode.PROJECT)
            else ExecutionMode.FRAMEWORK
        )

        cls._EXECUTION_MODE = resolved

        # Optional persistence (useful for debugging / CI)
        os.environ["BDD_EXECUTION_MODE"] = resolved

    @classmethod
    def get_execution_mode(cls) -> str:
        if cls._EXECUTION_MODE:
            return cls._EXECUTION_MODE

        return os.getenv(
            "BDD_EXECUTION_MODE", ExecutionMode.FRAMEWORK
        )

    @classmethod
    def is_framework_mode(cls) -> bool:
        return cls.get_execution_mode() == ExecutionMode.FRAMEWORK

    @classmethod
    def is_project_mode(cls) -> bool:
        return cls.get_execution_mode() == ExecutionMode.PROJECT

    # ------------------------------------------------------------------
    # LLM Backend Helpers
    # ------------------------------------------------------------------
    @classmethod
    def get_llm_backend(cls) -> str:
        """Get the current LLM backend setting."""
        if cls.USE_LOCAL_LLM:
            return LLMBackend.LOCAL
        return cls.LLM_BACKEND
    
    @classmethod
    def is_local_llm(cls) -> bool:
        """Check if using local LLM backend."""
        return cls.get_llm_backend() == LLMBackend.LOCAL
    
    @classmethod
    def is_cloud_llm(cls) -> bool:
        """Check if using cloud LLM backend."""
        return cls.get_llm_backend() == LLMBackend.CLOUD
    
    @classmethod
    def set_llm_backend(cls, backend: str):
        """
        Set the LLM backend at runtime.
        
        Args:
            backend: "local" or "cloud"
        """
        if backend == LLMBackend.LOCAL:
            cls.USE_LOCAL_LLM = True
            cls.LLM_BACKEND = LLMBackend.LOCAL
            os.environ["USE_LOCAL_LLM"] = "true"
        else:
            cls.USE_LOCAL_LLM = False
            cls.LLM_BACKEND = LLMBackend.CLOUD
            os.environ["USE_LOCAL_LLM"] = "false"
    
    @classmethod
    def get_llm_client(cls):
        """
        Get the appropriate LLM client based on configuration.
        
        Returns:
            LLM client instance (LocalLLMClient or GroqClient)
        """
        from llm import get_llm_client
        return get_llm_client(
            force_local=cls.is_local_llm(),
            force_cloud=cls.is_cloud_llm()
        )

    # ------------------------------------------------------------------
    # Import utility constants for backward compatibility
    # ------------------------------------------------------------------
    @staticmethod
    def get_timeouts():
        """Get timeout constants - delegates to utils.constants"""
        from utils.constants import Timeouts
        return Timeouts