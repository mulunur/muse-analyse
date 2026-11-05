# 📚 Muse Analyse documentation

A full index of the project's documentation.

## 🚀 Getting started

### For beginners
1. **[FIRST_RUN_CHECKLIST.md](FIRST_RUN_CHECKLIST.md)** ← Start here!
   - ✓ Step-by-step setup
   - ✓ A checklist of every step
   - ✓ Troubleshooting

2. **[QUICKSTART.md](QUICKSTART.md)** (5 minutes)
   - ✓ A 5-minute start
   - ✓ Configuration examples
   - ✓ Quick testing

### For experienced users
3. **[README.md](README.md)** (the main one)
   - ✓ Features
   - ✓ Installation (in more detail)
   - ✓ API (examples)
   - ✓ The extracted parameters

4. **[LLM_PROVIDERS.md](LLM_PROVIDERS.md)** (providers)
   - ✓ OpenAI GPT
   - ✓ Anthropic Claude
   - ✓ Ollama (local)
   - ✓ NVIDIA Nemotron
   - ✓ Usage recommendations

## 🔧 For developers

5. **[ARCHITECTURE.md](ARCHITECTURE.md)** (architecture)
   - ✓ The big picture
   - ✓ Components (frontend, backend)
   - ✓ Data flow
   - ✓ Extending the project

6. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** (what was done)
   - ✓ Architecture
   - ✓ The 4 providers
   - ✓ New files
   - ✓ Provider comparison

7. **[CHANGELOG.md](CHANGELOG.md)** (version 1.1.0)
   - ✓ Main changes
   - ✓ New API endpoints
   - ✓ Migrating from an older version
   - ✓ Backward compatibility

8. **[k8s/README.md](k8s/README.md)** (Kubernetes)
   - ✓ Manifests for kind, minikube and k3s
   - ✓ Probes, volumes, resources

9. **[evals/README.md](evals/README.md)** (evals)
   - ✓ A simple eval for the LLM features
   - ✓ How to run it and read the results

## 🔌 Integrations

10. **[MCP_INTEGRATION.md](MCP_INTEGRATION.md)** (Model Context Protocol)
    - ✓ An MCP server for Claude Desktop
    - ✓ Configuration
    - ✓ Usage examples

## 📖 Project structure

```
muse-analyse/
├── app/
│   ├── __init__.py              # Package version
│   ├── config.py                # Configuration (20+ variables)
│   ├── audio_analysis.py        # Essentia analysis
│   ├── llm_providers.py         # The 4 providers
│   ├── review_generator.py      # Review generation, uses the factory
│   ├── tasks.py                 # Celery app and background tasks
│   ├── agents/                  # Growth Copilot (LangGraph)
│   ├── rag/                     # RAG: indexing and search
│   └── main.py                  # FastAPI application
├── static/
│   ├── index.html               # Web interface
│   ├── app.js                   # Frontend logic
│   └── style.css                # Styles
├── tests/                       # pytest tests
├── evals/                       # Evals for the LLM features
├── k8s/                         # Kubernetes manifests
├── examples/
│   └── test_providers.py        # Examples of calling the API
├── run.py                       # Starts the server
├── requirements.txt
├── .env.example
└── *.md                         # Documentation (this index and the files above)
```

## 📋 API endpoints

### Health & status
```
GET /healthz             A lightweight "is the process alive?" check
GET /api/health          System status + providers
GET /api/providers       The list of available LLM providers
```

### Analysis
```
POST /api/analyze        Upload a track; returns a task_id
GET  /api/tasks/{id}     The status and result of a background task
```

See **[README.md](README.md#api)** for details.

## 🎯 Quick navigation

| I need to... | Read... |
|--------------|---------|
| Get started | [FIRST_RUN_CHECKLIST.md](FIRST_RUN_CHECKLIST.md) |
| Run it quickly | [QUICKSTART.md](QUICKSTART.md) |
| Set up a provider | [LLM_PROVIDERS.md](LLM_PROVIDERS.md) |
| Understand the architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| See what's new in v1.1.0 | [CHANGELOG.md](CHANGELOG.md) |
| Use it in Claude | [MCP_INTEGRATION.md](MCP_INTEGRATION.md) |
| Run it on Kubernetes | [k8s/README.md](k8s/README.md) |
| Get the main info | [README.md](README.md) |
| Extend the functionality | [ARCHITECTURE.md](ARCHITECTURE.md#extending-the-architecture) |

## 🔑 Key concepts

### LLM providers (v1.1.0)
```python
# Pick a provider in .env
LLM_PROVIDER=openai

# If the provider is unavailable, the app falls back automatically.
# The template review is always there as a fallback.
```

### Configuration
```python
# All parameters are loaded from .env
from app.config import LLM_PROVIDER, OPENAI_API_KEY, ...
```

### The provider factory
```python
from app.llm_providers import LLMProviderFactory

# Get the current provider and its LangChain model
provider = LLMProviderFactory.get_provider()
chat_model = provider.build_chat_model()

# A track review (LLM + RAG, with a template fallback)
from app.review_generator import generate_review
review = generate_review(features)

# The list of available providers
providers = LLMProviderFactory.list_available_providers()
```

## 🧪 Testing

```bash
# Run all the tests
pytest tests/ -v

# Check the configuration
curl http://localhost:8000/api/health | jq

# Analyse a track
python examples/test_providers.py /path/to/track.mp3
```

## 🌍 Supported formats

- MP3
- WAV
- FLAC
- OGG
- M4A
- AAC
- WMA

## 📊 Performance

| Operation | Time |
|-----------|------|
| Essentia analysis (3-4 minute track) | a few seconds on a recent laptop (we measured ~5 s); more on a small VPS |
| OpenAI review | 5-15 s |
| Claude review | 10-20 s |
| Ollama review | 15-45 s |
| Nemotron review | 10-30 s |

The LLM call is usually the slowest step. The API figures are rough, typical values, so measure your own setup.

## 💡 Recommendations

| Scenario | Provider | Why |
|----------|----------|-----|
| The first time | OpenAI | Reliable and fast |
| Best quality | Claude | Strong reasoning |
| Private analysis | Ollama | Local and free |
| Production | OpenAI/Nemotron | Scales well |

## 🔗 External resources

- **Essentia**: https://essentia.upf.edu/
- **OpenAI API**: https://platform.openai.com/
- **Claude API**: https://console.anthropic.com/
- **Ollama**: https://ollama.ai/
- **NVIDIA API**: https://developer.nvidia.com/

## 📞 Getting help

1. Check [FIRST_RUN_CHECKLIST.md](FIRST_RUN_CHECKLIST.md) #7-10
2. Run: `curl http://localhost:8000/api/health | jq`
3. Read the server logs
4. See [ARCHITECTURE.md](ARCHITECTURE.md#testing)

## 🚀 What's next?

### Optional improvements
- [ ] Caching of analysis results
- [ ] A history of uploaded tracks
- [ ] Comparing several providers
- [ ] Recommendations for improving the sound
- [ ] Batch analysis of folders
- [ ] Choosing the provider in the web interface

### Documentation for improvements
- See [ARCHITECTURE.md](ARCHITECTURE.md#extending-the-architecture)
- Examples in [examples/test_providers.py](examples/test_providers.py)
- Tests in [tests/test_llm_providers.py](tests/test_llm_providers.py)

## ✨ Thanks for using Muse Analyse!

Start with **[FIRST_RUN_CHECKLIST.md](FIRST_RUN_CHECKLIST.md)** 🎵

---

**Version**: 1.1.0  
**Date**: 2024  
**Status**: ✅ Fully functional
