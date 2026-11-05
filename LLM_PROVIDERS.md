# Using different LLM providers in Muse Analyse

Now that several LLM providers are supported, you can pick whichever one suits your needs.

## Quick start

### 1. Copy the config
```bash
cp .env.example .env
```

### 2. Pick a provider
Edit `.env` and set `LLM_PROVIDER` to one of:
- `openai` (the default)
- `claude`
- `ollama`
- `nemotron`

### 3. Run it
```bash
pip install -r requirements.txt
python run.py
```

---

## Configuring each provider

### OpenAI GPT
**Best for:** general use and high-quality reviews

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini  # or gpt-4, gpt-4-turbo and so on
```

**Installation:**
```bash
pip install langchain-openai>=0.3.0  # already in requirements.txt
```

**Get an API key:** https://platform.openai.com/api-keys

**Cost:** paid, about $0.15 per 1M input tokens (GPT-4o-mini)

---

### Anthropic Claude
**Best for:** deep music analysis and complex structured answers

```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
CLAUDE_MODEL=claude-sonnet-5  # or claude-opus-5 (more capable), claude-haiku-4-5 (cheaper)
```

> **Note:** `LLM_TEMPERATURE` does not apply to Claude. The current models
> (Sonnet 5, Opus 5) reject sampling parameters with a 400 error.

**Installation:**
```bash
pip install langchain-anthropic>=0.3.0  # already in requirements.txt
```

**Get an API key:** https://console.anthropic.com/

**Cost:** paid, about $2 per 1M input tokens and $10 per 1M output tokens (Claude Sonnet 5)

---

### Ollama (local)
**Best for:** privacy, no commercial restrictions, and free local use

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral  # or llama2, neural-chat, etc.
```

**Installing Ollama:**
1. Download it from https://ollama.ai/download
2. Start it: `ollama serve`
3. In another terminal, download a model: `ollama pull mistral`

**Available models:**
- `mistral`: 7B, fast, good quality
- `llama2`: 7B, a general-purpose model
- `neural-chat`: 7B, tuned for dialogue
- `orca-mini`: 3B, lightweight
- Full list: https://ollama.ai/library

**Cost:** free (it runs on your machine)

---

### NVIDIA Nemotron API
**Best for:** a balance of quality and speed on NVIDIA infrastructure

```env
LLM_PROVIDER=nemotron
NEMOTRON_API_KEY=nvapi_your_api_key_here
NEMOTRON_MODEL=meta/llama-2-70b-chat
NEMOTRON_BASE_URL=https://integrate.api.nvidia.com/v1
```

**Installation:**
```bash
pip install langchain-openai>=0.3.0  # already in requirements.txt (the NVIDIA API is OpenAI-compatible)
```

**Get an API key:**
1. Sign up at https://developer.nvidia.com/
2. Create an API key following https://docs.nvidia.com/cloud/cloud-docs/getting-started/quickstart.html

**Available models:**
- `meta/llama-2-70b-chat`: powerful, high quality
- `mistralai/mixtral-8x7b-instruct-v0.1`: fast
- Full list: https://docs.nvidia.com/cloud/cloud-docs/getting-started/quickstart.html

**Cost:** often free for new users, paid afterwards

---

## API endpoints

### Check the available providers
```bash
curl http://localhost:8000/api/providers
```

Response:
```json
{
  "available": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  },
  "description": {
    "openai": "OpenAI GPT (требует OPENAI_API_KEY)",
    "claude": "Anthropic Claude (требует ANTHROPIC_API_KEY)",
    "ollama": "Локальный Ollama (требует ollama serve)",
    "nemotron": "NVIDIA Nemotron API (требует NEMOTRON_API_KEY)"
  }
}
```

(The descriptions are the app's own Russian strings; they say which key or service each provider needs.)

### Upload audio and get a review
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

The analysis runs in the background, so this returns a `task_id` straight away. Fetch the result with `GET /api/tasks/<task_id>` (see the README for the details).

When the task is done, the result includes:
- `features`: all the Essentia parameters
- `review`: a review from the chosen LLM provider
  - `source`: the provider's name
  - `model`: the model that was used
  - `score`: a score from 1 to 10
  - `sections`: the structured review
  - `full_text`: the full text of the review

---

## Recommendations

| Scenario | Provider | Why |
|----------|----------|-----|
| A quick start | OpenAI | The most stable, with good quality |
| Private analysis | Ollama | It runs locally and sends no data out |
| Best quality | Claude | The strongest reasoning |
| A budget option | Ollama (mistral) | Free, and local |
| Production on a GPU | Nemotron | Optimised for NVIDIA hardware |

---

## The fallback mechanism

If the chosen provider is unavailable or something goes wrong, the system automatically returns a **template review** built from the Essentia parameters.

This guarantees that audio analysis always works, even without internet access or API keys.

---

## .env examples

### For local use (Ollama)
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

### For production with OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
```

### For production with Claude
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxx
CLAUDE_MODEL=claude-sonnet-5
LLM_MAX_TOKENS=2000
```
