import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"

# LLM Provider Selection
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Anthropic Claude Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# Ollama Configuration (локальный запуск)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Nemotron Configuration (NVIDIA API)
NEMOTRON_API_KEY = os.getenv("NEMOTRON_API_KEY", "").strip()
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "meta/llama-2-70b-chat")
NEMOTRON_BASE_URL = os.getenv("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Upload Configuration
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Audio Configuration
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}

# LLM Response Configuration
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

# Supported providers
SUPPORTED_PROVIDERS = {"openai", "claude", "ollama", "nemotron"}

# RAG Configuration
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", str(BASE_DIR / "data" / "knowledge")))
RAG_INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", str(BASE_DIR / "data" / "rag_index")))
RAG_EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)
