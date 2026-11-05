# Changelog: support for multiple LLM providers

## v1.1.0: multiple LLM providers (2024)

### 🎯 Main changes

#### ✨ New LLM providers

Support for four LLM providers was added:

1. **OpenAI GPT** (`openai`)
   - Models: gpt-4o-mini, gpt-4, gpt-4-turbo
   - Cost: paid
   - Docs: https://platform.openai.com/api-keys

2. **Anthropic Claude** (`claude`)
   - Models: claude-3-5-sonnet, claude-3-opus
   - Cost: paid
   - Docs: https://console.anthropic.com/

3. **Ollama, run locally** (`ollama`)
   - Models: mistral, llama2, neural-chat, orca-mini and others
   - Cost: free (runs on your own machine)
   - Docs: https://ollama.ai/

4. **NVIDIA Nemotron** (`nemotron`)
   - Models: meta/llama-2-70b-chat and others
   - Cost: paid / free tier
   - Docs: https://docs.nvidia.com/

### 📁 New files

- **`app/llm_providers.py`**: the module with every provider's implementation
  - `LLMProvider`: the abstract base class
  - `OpenAIProvider`, `ClaudeProvider`, `OllamaProvider`, `NemotronProvider`: the concrete implementations
  - `LLMProviderFactory`: a factory that creates providers

- **`LLM_PROVIDERS.md`**: detailed documentation on configuring each provider

- **`ARCHITECTURE.md`**: a description of the project's architecture

- **`MCP_INTEGRATION.md`**: a guide to using the project as an MCP server

- **`examples_test_providers.py`**: examples of using the API

- **`tests_test_llm_providers.py`**: tests for the providers and the API

### 🔄 Changes to existing files

#### `app/config.py`
- New configuration variables for each provider:
  - `LLM_PROVIDER`: which provider to use ("openai" by default)
  - `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
  - `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
  - `NEMOTRON_API_KEY`, `NEMOTRON_MODEL`, `NEMOTRON_BASE_URL`
  - `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`
- Added the `SUPPORTED_PROVIDERS` constant

#### `app/review_generator.py`
- The `generate_review()` function was rewritten from scratch
- It now uses `LLMProviderFactory.get_provider()` instead of calling OpenAI directly
- It falls back to a template review automatically if any provider fails

#### `app/main.py`
- Added the `LLMProviderFactory` import
- Updated the `GET /api/health` endpoint with an `llm_providers` field
- Added a new `GET /api/providers` endpoint that returns the available providers

#### `.env.example`
- Fully rewritten, with a configuration example for every provider

#### `requirements.txt`
- Added: `anthropic>=0.30.0`, `requests>=2.31.0`
- Added for testing: `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`

#### `README.md`
- The features section was rewritten
- Added a table of providers with recommendations
- Updated the API examples
- Added links to the new documentation

### 🏗️ Architecture improvements

1. **Factory pattern**: providers are managed in one place
2. **Abstract `LLMProvider` interface**: new providers are easy to add
3. **Automatic availability check**: every provider knows whether it is available
4. **Graceful fallback**: it always works with templates, even with no API

### 🔌 API changes

#### New endpoint: `GET /api/providers`

**Request:**
```bash
curl http://localhost:8000/api/providers
```

**Response:**
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

(The descriptions are the app's own Russian strings; they mean "requires OPENAI_API_KEY", "requires ANTHROPIC_API_KEY", "local Ollama (requires ollama serve)" and "requires NEMOTRON_API_KEY".)

#### Updated endpoint: `GET /api/health`

It now returns the status of every provider:
```json
{
  "status": "ok",
  "version": "1.1.0",
  "essentia_available": true,
  "essentia_error": null,
  "llm_providers": {
    "openai": true,
    "claude": false,
    "ollama": true,
    "nemotron": false
  }
}
```

#### `POST /api/analyze` response

The `review` field now says which provider produced it:
```json
{
  "review": {
    "source": "openai",
    "model": "gpt-4o-mini",
    "language": "ru",
    "score": 7.5,
    "sections": { ... },
    "full_text": "..."
  }
}
```

### 📚 Documentation

New files:
- **LLM_PROVIDERS.md**: a full guide to every provider, with configuration examples
- **ARCHITECTURE.md**: a technical document for developers
- **MCP_INTEGRATION.md**: how to use the project as an MCP server in Claude Desktop

### ✅ Testing

Tests were added for:
- Loading the configuration
- Initialising the provider factory
- Each provider's availability
- Error handling
- Building prompts
- Generating the template review
- The API endpoints

**Running the tests:**
```bash
pytest tests/ -v
```

### 🔒 Security

- API keys are not logged
- Temporary audio files are deleted after analysis
- Ollama runs locally, so no data is sent to the internet

### 📊 Usage recommendations

| Scenario | Recommended provider |
|----------|----------------------|
| A quick start | OpenAI (gpt-4o-mini) |
| High-quality analysis | Claude (claude-3-5-sonnet) |
| Private analysis | Ollama (mistral) |
| A budget option | Ollama (free) |
| Production on a GPU | Nemotron |

### 🚀 Usage examples

#### Switching providers
```bash
# Edit .env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxx

# Restart the server
python run.py
```

#### Checking availability
```bash
curl http://localhost:8000/api/providers | jq
```

#### Analysing with the current provider
```bash
curl -X POST -F "file=@track.mp3" http://localhost:8000/api/analyze
```

### 🔄 Backward compatibility

Every change is 100% backward compatible:
- If `OPENAI_API_KEY` is set, OpenAI is used (as before)
- If `LLM_PROVIDER` is not set, "openai" is the default
- If a provider is not available, it falls back to the template automatically

### ⚡ Performance

There is no change in performance. Analysis time stays the same:
- Essentia: 45-120 s (unchanged)
- LLM response: 5-45 s depending on the provider

### 🐛 Fixes

- More reliable error handling when a provider is unavailable
- Better logging for debugging

### 📝 Migrating from an older version

If you are upgrading from v1.0.0:

1. **Install the new dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Update .env:**
   ```bash
   cp .env.example .env
   # Edit .env
   ```

3. **That's it!** Your existing `OPENAI_API_KEY` keeps working as before.

Nothing else needs to change; the system recognises the old configuration on its own.

---

## Acknowledgements

- Essentia, for the powerful audio analysis
- OpenAI, Anthropic, NVIDIA and Ollama, for access to their models
