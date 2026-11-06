# Muse Analyse

**Music analysis with AI reasoning.** A web app that pulls musical features out of audio files with [Essentia](https://essentia.upf.edu/) and turns them into a structured review written in Russian.

Beyond creating a pet-project, my goal was to explore the potential of AI in dealing with music. By considering each step of development, I’ve arrived at a solution that has the capacity to deliver results based on isolated facts from music track. But question about holistic understanding of music remains open, see this article about it: https://www.lacuna.fm/blog/can-ai-understand-music


---

## Features

- Upload audio in the browser (drag & drop)
- Supported formats: **MP3, WAV, FLAC, OGG, M4A**
- Essentia features: tempo, key, loudness, spectrum, rhythm, danceability, energy
- Reviews written in **Russian**, with a choice of **LLM providers**:
  - **OpenAI**: GPT-4o-mini and other models (paid)
  - **Anthropic Claude**: Claude Sonnet 5 by default (paid)
  - **Ollama**: runs locally, free and private
  - **NVIDIA Nemotron**: a powerful API (paid, or a free tier)
  - **Template fallback**: needs no API keys, so it always works
- **RAG (Retrieval Augmented Generation)**: reviews are enriched with passages from the textbook *Теория современной композиции* ("Theory of Contemporary Composition"), so the assessments are backed by music theory
- Returns both the raw parameters (JSON) and the review text

---

## Project structure

```
muse-analyse/
├── app/
│   ├── __init__.py              # Package version
│   ├── config.py                # Settings from .env
│   ├── audio_analysis.py        # Essentia feature extraction
│   ├── llm_providers.py         # OpenAI, Claude, Ollama and Nemotron support
│   ├── review_generator.py      # Review generation, with a template fallback
│   ├── tasks.py                 # Celery app and background tasks
│   ├── agents/                  # Growth Copilot: LangGraph graph and its agents
│   ├── rag/                     # RAG: PDF indexing and semantic search
│   └── main.py                  # FastAPI application
├── data/
│   ├── knowledge/               # PDF textbooks (tracked in git)
│   └── rag_index/               # ChromaDB index (gitignored, can be rebuilt)
├── evals/                       # A simple eval for the LLM features (see evals/README.md)
├── examples/
│   └── test_providers.py        # Examples of calling the API
├── k8s/                         # Kubernetes manifests (see k8s/README.md)
├── scripts/
│   ├── index_knowledge.py       # CLI that builds the RAG index
│   └── check_mcp_server.py      # Manual check of the MCP server
├── static/
│   ├── index.html               # Web interface
│   ├── style.css
│   └── app.js
├── tests/                       # Automated tests (pytest)
├── mcp_server.py                # MCP server for Claude Desktop
├── run.py                       # Starts the server
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── LLM_PROVIDERS.md             # Provider documentation
└── README.md
```

---

## Quick start

### Recommended: Docker Compose

Use the same container setup on your laptop and on a VPS. Docker Desktop is only needed on your own machine; a VPS needs just Docker Engine and the Compose plugin.

### Running with Docker Compose

Docker Compose brings up a production-style container with one command and installs the system dependencies for you, ffmpeg included:

```bash
cp .env.example .env
docker compose up --build
```

Open **http://localhost:8000**

Besides the app itself, this starts `redis` (the task queue) and `worker` (a separate process that runs the analysis and Growth Copilot). Without the worker, tasks get queued but never finish.

This variant runs the base `linux/amd64` image, which has a ready-made Linux wheel of Essentia TensorFlow but none of the heavy RAG dependencies. To turn RAG on, stop the base service and start the profile (with `worker-rag` instead of `worker`):

```bash
docker compose down
docker compose --profile rag up --build muse-analyse-rag worker-rag
```

After you add PDFs to `data/knowledge/`, build the RAG index in the same profile:

```bash
docker compose --profile rag run --rm muse-analyse-rag python scripts/index_knowledge.py
```

The index lives in the named Docker volume `muse-analyse_rag_index`, so it survives container re-creation. To stop everything:

```bash
docker compose down
```

To delete the index along with the volume, use `docker compose down -v`.

### Local setup without Docker

This mode is meant for development, and you may have to install Essentia and ffmpeg yourself. For production, use the Compose setup above.

#### System dependencies (macOS)

```bash
brew install ffmpeg
```

#### Python environment

```bash
cd /path/to/muse-analyse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Installing Essentia on macOS

#### Recommended: Conda

```bash
conda create -n muse-analyse python=3.10
conda activate muse-analyse
conda install -c conda-forge essentia
pip install -r requirements.txt
```

#### Or: pip (if it works for your Python version)

```bash
pip install essentia
```

**Check that it works:**
```bash
python -c "import essentia; print(essentia.__version__)"
```

#### Configuration

```bash
cp .env.example .env
# Edit .env: pick a provider and add keys (optional)
```

#### Running

Analysis and Growth Copilot run in a separate worker process. Without it, requests are queued and never finish. You need Redis (`brew install redis && redis-server` on macOS, or `docker run -p 6379:6379 redis:7-alpine`) and two processes, the server and the worker:

```bash
source .venv/bin/activate

# Terminal 1: the server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info

# Terminal 2: the worker
celery -A app.tasks worker --loglevel=info
```

Open **http://localhost:8000**

#### RAG: indexing the textbook

The textbook *Теория современной композиции* is already in `data/knowledge/`. On the first run, build the vector index:

```bash
pip install chromadb pymupdf sentence-transformers
python scripts/index_knowledge.py
```

Check the status:

```bash
python scripts/index_knowledge.py --status
```

The first run downloads a multilingual embedding model (~470 MB). The index is saved to `data/rag_index/`.

To add other textbooks, put the PDFs in `data/knowledge/` and run:

```bash
python scripts/index_knowledge.py --force
```

To switch RAG off, set `RAG_ENABLED=false` in `.env`.

---

## LLM providers

**OpenAI** is used by default, but you can pick any of the four:

| Provider | Config | Cost | Best for |
|----------|--------|------|----------|
| **OpenAI** | `LLM_PROVIDER=openai` | Paid | A quick start, high quality |
| **Claude** | `LLM_PROVIDER=claude` | Paid | Deep analysis, well-structured answers |
| **Ollama** | `LLM_PROVIDER=ollama` | Free | Privacy, running locally |
| **Nemotron** | `LLM_PROVIDER=nemotron` | Paid / free tier | GPU optimisation |

**Detailed setup:** see [LLM_PROVIDERS.md](LLM_PROVIDERS.md)

---

## API

### `GET /api/health`

Reports the app's status, whether Essentia is available, and which LLM providers are ready.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "essentia_available": true,
  "llm_providers": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  }
}
```

### `GET /healthz`

A lightweight "is the process alive?" check, meant for Kubernetes probes. It asks nothing outside the process (no Ollama, RAG or Redis), so it answers right away. Returns `{"status": "ok"}`.

### `GET /api/providers`

The list of available LLM providers.

```json
{
  "available": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  },
  "description": { ... }
}
```

### `POST /api/analyze`

Uploads an audio file and queues its analysis in Celery. Essentia analysis and review generation can take tens of seconds, so they run in a separate worker process instead of inside the request.

**Request:**
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

**Response (immediate):**
```json
{"task_id": "d8805c13-27b5-4be0-83f6-35996314c93a"}
```

### `GET /api/tasks/{task_id}`

The status and result of a background task. Poll it until `status` becomes `done` or `error`.

```bash
curl http://localhost:8000/api/tasks/d8805c13-27b5-4be0-83f6-35996314c93a
```

While the task is still running:

```json
{"status": "pending"}
```

**Response when it is finished (`status: "done"`):**

```json
{
  "status": "done",
  "result": {
    "success": true,
    "filename": "track.mp3",
    "features": { ... },
    "review": {
      "source": "openai",
      "model": "gpt-4o-mini",
      "language": "ru",
      "score": 7.5,
      "sections": {
        "summary": "...",
        "rhythm": "...",
        "tonality": "...",
        "production": "...",
        "verdict": "..."
      },
      "full_text": "..."
    }
  }
}
```

Growth Copilot (`POST /api/growth/start`, `POST /api/growth/select`) works the same way: the request returns a `task_id` right away, and the result comes from the same `GET /api/tasks/{task_id}`.

### Calling the MCP tools (locally, an example)

If you want to call the `mcp_server.py` wrapper directly (this does not need the FastMCP transport). The `analyze_audio` tool waits for the background analysis to finish (up to 5 minutes by default; change it with `MUSE_ANALYSIS_TIMEOUT`), so the worker has to be running too:

```bash
# In one terminal, start the API (see above):
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000

# In another terminal, analyse a file through the tool:
python -c "from mcp_server import analyze_audio; print(analyze_audio('/absolute/path/to/track.mp3'))"
```

To run the interactive FastMCP transport (stdin/stdout) for use with external MCP clients:

```bash
# Start FastMCP (example):
python mcp_server.py
```

---

## What gets extracted

| Category | Features |
|----------|----------|
| **Rhythm** | BPM, beat confidence, number of beats, onset rate, beat loudness |
| **Tonality** | Tonic, mode (major/minor), key strength, tuning (Hz), chords |
| **Dynamics** | LUFS (EBU R128), Stevens loudness (not dB), dynamic complexity, RMS, replay gain |
| **Spectrum** | Spectral centroid, brightness, rolloff, flux, zero-crossing rate, MFCC |
| **Other** | Danceability, energy (a composite score from 0 to 1) |

---

## OpenAI (optional)

If `OPENAI_API_KEY` is set in `.env`, reviews are generated with ChatGPT (`OPENAI_MODEL`, `gpt-4o-mini` by default).

Without a key the app still works fully: it falls back to the built-in template review generator (in Russian).

---

## Limitations

- When you run **Essentia on macOS** locally, you may have to install it separately. The container setup for a VPS uses a ready-made Linux x86_64 wheel instead.
- Docker only solves the system-dependency problem inside the Linux container. Docker Desktop still needs enough memory and disk.
- The images are deliberately built for `linux/amd64`, which matches most VPSes. On an ARM Mac, Docker Desktop uses emulation and builds can be slower.
- The image is big: Essentia, ffmpeg and the RAG embedding model make the build and the first start slow.
- A VPS uses the pinned `essentia-tensorflow` wheel for Linux x86_64 and Python 3.11. Other architectures need a separate build or a different package version.
- On first use, RAG may download the embedding model from the network. Without network access, RAG indexing will not finish.
- Docker Compose does not start Ollama for you. Ollama needs its own service or host and a correct `OLLAMA_BASE_URL`.
- Uploaded audio files go to a temporary volume shared by the web container and the worker, and are **deleted right after analysis**. This is not storage for your source files.
- For a public deployment you still have to set up a reverse proxy, TLS, authentication, rate limits and secret management yourself.
- **Long tracks** (over 5 minutes) can take a noticeable amount of time to analyse.
- When running locally, **MP3/M4A** need ffmpeg installed. The Docker image already includes it.
- The "energy" score is a **proxy metric** built from RMS, BPM, brightness and danceability (Essentia has no direct "energy" algorithm the way Spotify does).
- Without an API, the AI review is a **template**. It is no substitute for a human critic.

---

## Troubleshooting

The app's own messages are in Russian, so they are quoted as-is below.

| Problem | Solution |
|---------|----------|
| `Essentia не установлена` ("Essentia is not installed") | Check `docker compose logs muse-analyse`; for a local run, see the Essentia installation section above |
| `Не удалось загрузить аудио` ("Could not load the audio") | ffmpeg is already in the Docker image; for a local run, install it with `brew install ffmpeg` |
| `Пустой файл` / `повреждён` ("Empty file" / "damaged") | Check that the audio file is intact |
| OpenAI error | Check the key; the app falls back to the template review automatically |

---

## License

MIT.

Essentia is distributed under the Affero GPL v3 license.
