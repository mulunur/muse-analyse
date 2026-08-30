import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"

_RUNTIME_OVERRIDES: dict[str, str] = {}


def get_runtime_llm_setting(name: str, default: str = "") -> str:
    """Возвращает live-значение настройки LLM, приоритет у runtime-перезаписи."""
    key = name.upper()
    if key in _RUNTIME_OVERRIDES:
        value = _RUNTIME_OVERRIDES[key]
        return value if value is not None else default
    return os.getenv(key, default).strip()


def set_runtime_llm_setting(name: str, value: str | None) -> str:
    """Обновляет runtime-настройку и возвращает итоговое значение."""
    key = name.upper()
    if value is None or str(value).strip() == "":
        _RUNTIME_OVERRIDES.pop(key, None)
        os.environ.pop(key, None)
        return ""

    clean_value = str(value).strip()
    _RUNTIME_OVERRIDES[key] = clean_value
    os.environ[key] = clean_value
    return clean_value


def save_runtime_llm_settings(settings: dict[str, str]) -> None:
    """Сохраняет настройки в .env, если файл существует или может быть создан."""
    env_path = BASE_DIR / ".env"
    existing: dict[str, str] = {}

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()

    for key, value in settings.items():
        if value is None or str(value).strip() == "":
            existing.pop(key.upper(), None)
            os.environ.pop(key.upper(), None)
            _RUNTIME_OVERRIDES.pop(key.upper(), None)
        else:
            clean_value = str(value).strip()
            existing[key.upper()] = clean_value
            set_runtime_llm_setting(key, clean_value)

    lines = [f"{key}={value}" for key, value in existing.items()]
    env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


# LLM Provider Selection
LLM_PROVIDER = get_runtime_llm_setting("LLM_PROVIDER", "openai").lower()

# OpenAI Configuration
OPENAI_API_KEY = get_runtime_llm_setting("OPENAI_API_KEY", "")
OPENAI_MODEL = get_runtime_llm_setting("OPENAI_MODEL", "gpt-4o-mini")

# Anthropic Claude Configuration
ANTHROPIC_API_KEY = get_runtime_llm_setting("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = get_runtime_llm_setting("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# Ollama Configuration (локальный запуск)
OLLAMA_BASE_URL = get_runtime_llm_setting("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = get_runtime_llm_setting("OLLAMA_MODEL", "mistral")

# Nemotron Configuration (NVIDIA API)
NEMOTRON_API_KEY = get_runtime_llm_setting("NEMOTRON_API_KEY", "")
NEMOTRON_MODEL = get_runtime_llm_setting("NEMOTRON_MODEL", "meta/llama-2-70b-chat")
NEMOTRON_BASE_URL = get_runtime_llm_setting("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")

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
