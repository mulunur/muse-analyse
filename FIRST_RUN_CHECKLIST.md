# ✅ Checklist: first run

## Prerequisites ✓

- [ ] Docker Desktop (macOS/Windows) or Docker Engine (a Linux VPS)
- [ ] The Docker Compose plugin
- [ ] Git (optional)

## 1. Environment

```bash
cd /path/to/muse-analyse
cp .env.example .env
```

- [ ] `.env` is created

## 2. Configuration

**Pick one option (edit `.env`):**

### Option A: OpenAI (recommended for a first run)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```
- [ ] You have an API key (https://platform.openai.com/api-keys)
- [ ] The key is added to `.env`

### Option B: Claude
```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
CLAUDE_MODEL=claude-sonnet-5
```
- [ ] You have an API key (https://console.anthropic.com/)
- [ ] The key is added to `.env`

### Option C: Ollama (local, free)
```bash
# Install Ollama: https://ollama.ai/download
# Start it in another terminal:
ollama serve

# Download a model in a third terminal:
ollama pull mistral
```

`.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

- [ ] Ollama is installed
- [ ] `ollama serve` is running in a separate terminal
- [ ] `ollama pull mistral` has finished
- [ ] `.env` is updated

### Option D: Nemotron
```env
LLM_PROVIDER=nemotron
NEMOTRON_API_KEY=nvapi_your_api_key_here
NEMOTRON_MODEL=meta/llama-2-70b-chat
```
- [ ] You have an API key (https://developer.nvidia.com/)
- [ ] The key is added to `.env`

## 3. Start the containers

```bash
docker compose up --build -d
```

This starts three services: the app, `redis` (the task queue) and `worker` (the process that does the analysis).

- [ ] The image is built
- [ ] The containers are running

## 4. Health check

```bash
curl http://localhost:8000/api/health
```

- [ ] Essentia is available
- [ ] The container is reported as healthy

## 5. Check the providers

```bash
curl http://localhost:8000/api/providers | jq
```

- [ ] A list of providers comes back

## 6. First test in the browser

Open **http://localhost:8000**

- [ ] The web interface loads
- [ ] You can see the file drop zone

## 7. First analysis

Find an MP3/WAV file and then do either of these:

### Option A: Web interface
1. Drag the file onto the page
2. Wait for the analysis (up to a minute or two)
3. Look at the results

- [ ] The file is uploaded
- [ ] The analysis starts
- [ ] The results are shown

### Option B: Command line

Analysis runs in the background, so this takes two steps. First upload the track and get a `task_id`:

```bash
curl -X POST -F "file=@/path/to/track.mp3" http://localhost:8000/api/analyze
# {"task_id": "..."}
```

Then ask for the result (repeat until `status` is `done`):

```bash
curl http://localhost:8000/api/tasks/<task_id> | jq
```

- [ ] You got a `task_id`
- [ ] The result contains a `review` with a score and text

## 8. Check the results

When the task is done, the response should look like this:
```json
{
  "status": "done",
  "result": {
    "success": true,
    "filename": "track.mp3",
    "features": {
      "duration_sec": ...,
      "rhythm": { "bpm": ... },
      "tonal": { "key": ... },
      ...
    },
    "review": {
      "source": "openai",  // or claude/ollama/nemotron
      "model": "gpt-4o-mini",
      "score": 7.5,
      "sections": { ... },
      "full_text": "..."
    }
  }
}
```

- [ ] `features` holds the analysis parameters
- [ ] `review.source` shows which provider was used
- [ ] `review.score` is a number from 1 to 10
- [ ] `review.full_text` holds the review in Russian

## ✨ Done!

If everything above is ticked, the system is working correctly!

## 🐛 Troubleshooting

### Essentia did not install
→ Check the architecture: the production image is built for `linux/amd64`.
→ Look at the logs: `docker compose logs muse-analyse`

### An LLM provider shows as false
→ Check the API key in `.env`

### Ollama will not connect
→ Make sure `ollama serve` is running
→ Check `OLLAMA_BASE_URL` in `.env`

### The task stays "pending" forever
→ The worker is probably not running. Check `docker compose ps` and `docker compose logs worker`

### The first analysis is slow
→ That is normal: Essentia processes the whole file
→ A 3-minute track takes anywhere from a few seconds to a minute or two, depending on your machine

### API error 503
→ Essentia did not load inside the container
→ Rebuild the image: `docker compose build --no-cache muse-analyse`

## 📚 Next

- Read [QUICKSTART.md](QUICKSTART.md)
- Study [LLM_PROVIDERS.md](LLM_PROVIDERS.md)
- See the examples in [examples/test_providers.py](examples/test_providers.py)

## 🚀 Ready to start?

```bash
docker compose up --build -d
```

Open **http://localhost:8000** in your browser and upload some tracks! 🎵
