# Muse Analyse architecture

## Overview

```
                    ┌─────────────────────┐
                    │       Web UI        │
                    │   (index.html +     │
                    │    app.js / css)    │
                    └──────────┬──────────┘
                               │ HTTP
                               ▼
                    ┌─────────────────────┐
                    │   FastAPI server    │
                    │   (main.py)         │
                    └───┬─────────────┬───┘
                        │             │ queues a task, then reads its result
                        │             ▼
                        │       ┌───────────┐         ┌────────────────────┐
                        │       │   Redis   │ ◄─────► │   Celery worker    │
                        │       │  (queue)  │         │    (tasks.py)      │
                        │       └───────────┘         └─────────┬──────────┘
                        │                                       │
                        ▼                 ┌─────────────────────┼─────────────────┐
                  Config (.env)           ▼                     ▼                 ▼
                                    Essentia audio         LLM providers      RAG index
                                       analysis            (OpenAI, Claude,   (ChromaDB)
                                                            Ollama, Nemotron,
                                                            or the template
                                                            fallback)
```

The web server never does the heavy work itself. It saves the upload, queues a task and answers right away; the worker does the analysis and the LLM calls.

## Components

### 1. **Frontend** (`static/`)

- **index.html**: the main page with the upload interface
- **app.js**: the logic that talks to the API (drag & drop, sending files, polling for the result, showing it)
- **style.css**: styling (dark theme, responsive layout)

### 2. **Backend** (`app/`)

#### `main.py`: the FastAPI application

Main endpoints:
- `GET /`: returns index.html
- `GET /healthz`: a lightweight "is the process alive?" check for Kubernetes probes
- `GET /api/health`: system status (Essentia, LLM providers, RAG)
- `GET /api/providers`: the list of available LLM providers
- `POST /api/analyze`: uploads audio and queues its analysis; returns a `task_id`
- `GET /api/tasks/{task_id}`: the status and result of a background task
- `POST /api/growth/start`, `POST /api/growth/select`, `GET /api/growth/status/{thread_id}`: Growth Copilot

```python
# How a request is handled:
# 1. Validate the file (extension, size)
# 2. Save it to the shared uploads directory
# 3. Queue a Celery task and return its task_id
# The worker then runs, in the background:
# 4. analyze_audio()   -> Essentia features
# 5. generate_review() -> a review from the LLM
# 6. Delete the temporary file
# The browser polls GET /api/tasks/{task_id} until the result is ready.
```

#### `tasks.py`: the Celery app and background tasks

Holds the three tasks (`analyze_track`, `growth_start`, `growth_select`). Redis is the broker and result store. The Growth Copilot graph state is kept in a SQLite file on a volume shared by the web process and the worker.

#### `agents/`: Growth Copilot

A LangGraph graph made of several LLM agents (voice, trend, ideation, draft, critique). It runs until the artist has to pick ideas, then resumes with that choice.

#### `audio_analysis.py`: Essentia analysis

The function `analyze_audio(file_path)` returns a dict of parameters:

```python
{
    "file": "track.mp3",
    "duration_sec": 180.5,
    "rhythm": {
        "bpm": 128.0,
        "beat_confidence": 0.95,
        "beats_count": 245,
        "onset_rate": 0.123
    },
    "tonal": {
        "key": "C",
        "scale": "minor",
        "key_strength": 0.88,
        "danceability": 0.72,
        "top_chords": [{"chord": "Cm", "count": 45}]
    },
    "dynamics": {
        "loudness_ebu128_lufs": -9.5,
        "loudness_stevens_power": 10448.87,
        "dynamic_complexity": 0.38,
        "rms": 0.156
    },
    "spectral": {
        "spectral_centroid_hz": 2340.5,
        "spectral_brightness": 0.45,
        "spectral_rolloff_hz": 5600.0,
        "mfcc_coefficients": [...]
    },
    "energy": 0.64,
    "essentia_version": "2.1b6"
}
```

#### `llm_providers.py`: the LLM provider factory

How the providers are organised:

```python
LLMProvider (ABC)
├── OpenAIProvider
├── ClaudeProvider
├── OllamaProvider
└── NemotronProvider

LLMProviderFactory
├── get_provider(name) → a provider instance
└── list_available_providers() → dict[str, bool]
```

Every provider:
- implements `is_available()`, which checks that the keys exist or the service is reachable
- implements `build_chat_model()`, which creates a LangChain chat model (`ChatOpenAI`, `ChatAnthropic`, `ChatOllama`)
- inherits `structured_model(schema)`, a model that returns a Pydantic object instead of text

LangChain (`with_structured_output`) does the actual API call, parses the answer and validates the schema.

#### `review_generator.py`: review generation

The function `generate_review(features)`:

```
1. Try to get a provider from LLMProviderFactory
2. If that works → run the chain `ChatPromptTemplate | provider.structured_model(TrackReview)`
3. If there is no provider, or the call fails → fall back to _build_template_review()
4. Always return a structured review
```

A review contains:
- `source`: where it came from ("openai", "claude", "ollama", "nemotron" or "template")
- `model`: the model name
- `language`: "ru" (Russian)
- `score`: 1 to 10
- `sections`: the structured parts (summary, rhythm, tonality, production, verdict)
- `full_text`: the full text of the review

#### `config.py`: configuration

Loads from .env:
- LLM_PROVIDER: the chosen provider
- The API keys for each provider
- The URL and model for each provider
- LLM parameters (temperature, max_tokens)
- Server parameters (HOST, PORT)
- Redis and Celery settings

## Data flow for analysing a track

```
The user uploads an MP3
    │
    ▼
Validation (format, size)
    │
    ▼
The file is saved to the shared /uploads volume
    │
    ▼
A Celery task is queued; the server answers with a task_id
(the browser polls GET /api/tasks/{task_id})
    │
    ▼
The worker picks the task up
    │
    ▼
Essentia analysis (seconds to a minute or two, depending on track length and machine)
    │
    ├─→ Spectral analysis
    ├─→ Rhythm analysis
    ├─→ Tonal analysis
    ├─→ Dynamics analysis
    └─→ Energy and the rest
    │
    ▼
We now have a dict of features
    │
    ▼
LLMProviderFactory.get_provider()
    │
    ├─→ If the chosen provider is available → use it
    │   ├─→ OpenAI: a request to api.openai.com
    │   ├─→ Claude: a request to api.anthropic.com
    │   ├─→ Ollama: a request to localhost:11434
    │   └─→ Nemotron: a request to the NVIDIA API
    │
    └─→ If it is not available → fall back to the template
    │
    ▼
We get a structured review (JSON)
    │
    ▼
The temporary file is deleted
    │
    ▼
The result (features + review) is stored for the polling request
    │
    ▼
The frontend shows it
```

## Choosing the provider

```python
# In config.py:
LLM_PROVIDER = "openai"  # can be changed to claude, ollama or nemotron

# When a review is generated:
def generate_review(features):
    try:
        provider = LLMProviderFactory.get_provider()  # reads LLM_PROVIDER
    except ValueError:
        # The provider is not available, or its keys are not set
        return _build_template_review(features)
    # ... the LLM chain; if it fails, a template review with an llm_error field
```

## Extending the architecture

### Adding a new LLM provider

1. **Create a class in `llm_providers.py`:**
```python
class MyLLMProvider(LLMProvider):
    name = "my_llm"

    def __init__(self):
        self.api_key = get_runtime_llm_setting("MY_API_KEY", "")
        self.model = get_runtime_llm_setting("MY_MODEL", "default-model")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def build_chat_model(self):
        from langchain_openai import ChatOpenAI  # or any other LangChain class
        return ChatOpenAI(model=self.model, api_key=self.api_key, base_url="https://...")
```

2. **Register it in the factory:**
```python
class LLMProviderFactory:
    _providers = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
        "nemotron": NemotronProvider,
        "my_llm": MyLLMProvider,  # ← add it here
    }
```

3. **Add its settings to `config.py`:**
```python
MY_API_KEY = os.getenv("MY_API_KEY", "").strip()
MY_MODEL = os.getenv("MY_MODEL", "default-model")
```

4. **Update `.env.example`**

### Adding a new Essentia feature

1. **Add it to `audio_analysis.py`:**
```python
def _new_feature(audio):
    # compute the parameter
    return value

result = analyze_audio(path)
result["new_feature"] = _new_feature(audio)
```

2. **Update `_compact_features` and the prompt in `review_generator.py`** so the new feature is taken into account

---

## Testing

### Check the status
```bash
curl http://localhost:8000/api/health
```

### Check the providers
```bash
curl http://localhost:8000/api/providers
```

### Analyse a track
```bash
# Returns {"task_id": "..."}
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze

# Then ask for the result (repeat until "status" is "done"):
curl http://localhost:8000/api/tasks/<task_id> | jq .
```

### Test script
```bash
python examples/test_providers.py track.mp3
```

---

## Performance

| Operation | Time |
|-----------|------|
| Essentia analysis (3-4 minute track) | a few seconds on a recent laptop (we measured ~5 s); expect more on a small VPS |
| OpenAI API response | 5-15 s |
| Claude API response | 10-20 s |
| Ollama response (mistral) | 15-45 s |
| Nemotron API response | 10-30 s |

The LLM call is usually the slowest part now, and with a local Ollama model it dominates the total time. The API figures are rough, typical values; measure your own setup.

---

## Security

- Every uploaded file is deleted after analysis
- File size is limited (50 MB by default)
- File extensions are validated
- The server keeps no history of analyses
- With Ollama, your data never leaves your local network
