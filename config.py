"""
config.py
=========
Central configuration module for the PaperBrain AI Chatbot.
All settings are loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Load .env file ──────────────────────────────────────────────────────────
load_dotenv()

# ─── Base Paths ──────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
UPLOADS_DIR: Path = BASE_DIR / "uploads"
CHROMA_DIR: Path = BASE_DIR / "chroma_db"
LOGS_DIR: Path = BASE_DIR / "logs"

# Create directories if they don't exist
for _dir in [DATA_DIR, UPLOADS_DIR, CHROMA_DIR, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─── API Settings ─────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_BASE_URL: str = f"http://{API_HOST}:{API_PORT}"

# ─── LLM Settings ─────────────────────────────────────────────────────────────
# Provider: "ollama" | "openai" | "gemini"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

# Ollama settings
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# OpenAI settings (optional)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Gemini settings (optional)
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# LLM Generation parameters
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# ─── Embedding Settings ───────────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
)
EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")  # "cpu" | "cuda"
EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

# ─── ChromaDB Settings ────────────────────────────────────────────────────────
CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "pdf_rag_store")
CHROMA_DISTANCE_FUNCTION: str = "cosine"  # cosine | l2 | ip

# ─── Chunking Settings ────────────────────────────────────────────────────────
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
CHUNK_MIN_LENGTH: int = int(os.getenv("CHUNK_MIN_LENGTH", "50"))  # discard tiny chunks

# ─── Retrieval Settings ───────────────────────────────────────────────────────
TOP_K: int = int(os.getenv("TOP_K", "5"))
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.40"))
MMR_LAMBDA: float = float(os.getenv("MMR_LAMBDA", "0.5"))  # diversity weight
RERANK_ENABLED: bool = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANK_MODEL: str = os.getenv(
    "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)
HYBRID_SEARCH_ALPHA: float = float(
    os.getenv("HYBRID_SEARCH_ALPHA", "0.7")
)  # 1.0 = pure vector, 0.0 = pure keyword

# ─── Memory Settings ──────────────────────────────────────────────────────────
MEMORY_WINDOW_SIZE: int = int(os.getenv("MEMORY_WINDOW_SIZE", "10"))

# ─── File Upload Settings ─────────────────────────────────────────────────────
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS: set = {".pdf"}
MAX_FILES_PER_SESSION: int = int(os.getenv("MAX_FILES_PER_SESSION", "20"))

# ─── Cache Settings ───────────────────────────────────────────────────────────
CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_MAX_SIZE: int = int(os.getenv("CACHE_MAX_SIZE", "256"))
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

# ─── Logging Settings ─────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path = LOGS_DIR / "rag_chatbot.log"

# ─── Streamlit Settings ───────────────────────────────────────────────────────
APP_TITLE: str = "🧠 PaperBrain"
APP_ICON: str = "📄"
APP_DESCRIPTION: str = (
    "PaperBrain — Upload PDFs and get instant AI-powered answers from your documents."
)

# ─── Validation ───────────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """Return list of configuration warnings."""
    warnings: list[str] = []
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY is not set but LLM_PROVIDER=openai")
    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY is not set but LLM_PROVIDER=gemini")
    return warnings
