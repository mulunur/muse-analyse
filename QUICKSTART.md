# Quick Start: Muse Analyse

# tl;dr
```
cd /path/to/muse-analyse
cp .env.example .env
docker compose up --build
```
Then open http://localhost:8000

Prefer to run it without Docker? You need Redis running, and the worker in a second terminal:
```
cd /path/to/muse-analyse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning --no-access-log

# in another terminal (with the same environment activated):
celery -A app.tasks worker --loglevel=info
```

### 1. Clone / open the project

```bash
cd /path/to/muse-analyse
```

### 2. Configuration

```bash
cp .env.example .env
```

Add the API key of your chosen LLM provider to `.env`. Without a key, the app uses the template fallback.

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

### 3. Start the containers

```bash
docker compose up --build
```

If you have the older standalone Compose, use `docker-compose` instead of `docker compose`.

Open: **http://localhost:8000**

### 4. Check it works

```bash
curl http://localhost:8000/api/health
```

Logs:

```bash
docker compose logs -f muse-analyse
```

---

## Usage

### Web interface

1. Drag an MP3/WAV/FLAC/OGG/M4A onto the main page
2. Wait for the analysis (up to a minute or two, depending on the track and your machine)
3. Get the parameters + an AI review

### API

```bash
# Check which providers are available
curl http://localhost:8000/api/providers

# Upload a track (returns a task_id)
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze

# Fetch the result
curl http://localhost:8000/api/tasks/<task_id>
```

---

## Documentation

- **[README.md](README.md)**: the main information
- **[LLM_PROVIDERS.md](LLM_PROVIDERS.md)**: every provider in detail
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: for developers
- **[CHANGELOG.md](CHANGELOG.md)**: what's new in v1.1.0
- **[MCP_INTEGRATION.md](MCP_INTEGRATION.md)**: integration with Claude Desktop

---

## The RAG profile

The base container starts without the heavy RAG dependencies. For RAG:

```bash
docker compose down
docker compose --profile rag up --build muse-analyse-rag worker-rag
docker compose --profile rag run --rm muse-analyse-rag python scripts/index_knowledge.py
```

The index is stored in a Docker volume.

## Troubleshooting

### Essentia did not install

```bash
docker compose logs muse-analyse
docker compose build --no-cache muse-analyse
```

### The API key does not work

```bash
# Check the config
curl http://localhost:8000/api/health

# The provider should show up as true under llm_providers
```

### Ollama is not reachable

Make sure Ollama is reachable from inside the container, and set a correct `OLLAMA_BASE_URL`.

### The analysis is slow

That is normal! Essentia processes the whole audio file:
- the time grows with the length of the track (a few seconds on a fast machine, a minute or two on a small server)
- plus 5-45 s for the LLM's answer

---

## Switching the provider while running

All you need to do:
1. Edit `.env` (change `LLM_PROVIDER`)
2. Re-create the containers: `docker compose up -d --force-recreate`

No reinstalling is needed.

---

## Recommendations

| Situation | Setting |
|-----------|---------|
| First run | `LLM_PROVIDER=openai` |
| I want to save money | `LLM_PROVIDER=ollama` |
| I want the best result | `LLM_PROVIDER=claude` |
| I am working locally | `LLM_PROVIDER=ollama` |
| Production | `LLM_PROVIDER=openai` or `nemotron` |

---

## MCP support (optional)

If you want to use the analysis inside Claude Desktop:

1. Install the MCP SDK: `pip install mcp httpx`
2. Copy `mcp_server.py` into the project (see MCP_INTEGRATION.md)
3. Add it to the Claude Desktop config
4. Use the tools right inside Claude

---

## Python example

```python
import time
import requests

BASE = "http://localhost:8000"

# Check the status
print(requests.get(f"{BASE}/api/health").json())

# Upload a track; this returns a task_id right away
with open("track.mp3", "rb") as f:
    task_id = requests.post(f"{BASE}/api/analyze", files={"file": f}).json()["task_id"]

# Poll until the analysis is finished
while True:
    status = requests.get(f"{BASE}/api/tasks/{task_id}").json()
    if status["status"] != "pending":
        break
    time.sleep(2)

if status["status"] == "done":
    review = status["result"]["review"]
    print(f"Score: {review['score']}/10")
    print(f"Review: {review['full_text']}")
else:
    print("Error:", status["error"])
```

---

## API documentation

Full interactive documentation: **http://localhost:8000/docs**

---

## Need help?

1. Read [ARCHITECTURE.md](ARCHITECTURE.md)
2. Check the server logs
3. Run the tests: `pytest tests/ -v`
4. Check the config: `curl http://localhost:8000/api/health`

---

**You are ready to go!** 🎵
