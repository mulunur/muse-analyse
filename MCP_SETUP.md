# Muse Analyse MCP server

A minimal integration for use with Claude Desktop and other MCP-compatible tools.

## Installation

Muse Analyse runs in a Docker container, while the MCP server runs separately, on the machine of whoever uses Claude Desktop.

```bash
cp .env.example .env
docker compose up --build -d
```

## Configuring Claude Desktop

### macOS
1. Edit:
```bash
~/Library/Application\ Support/Claude/claude_desktop_config.json
```

2. Add:
```json
{
  "mcpServers": {
    "muse-analyse": {
      "command": "/path/to/muse-analyse/.venv/bin/python",
      "args": ["/path/to/muse-analyse/mcp_server.py"],
      "env": {
        "MUSE_API": "http://localhost:8000",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Windows
`%APPDATA%\Claude\claude_desktop_config.json`

### Linux
`~/.config/Claude/claude_desktop_config.json`

## Usage

### 1. Start the Muse Analyse container
```bash
docker compose up -d
```

### 2. Restart Claude Desktop

### 3. Use it in Claude

```
Analyse the track ~/Music/song.mp3 and give me a detailed review
```

Claude automatically uses the `analyze_audio` tool and gets:
- All the Essentia parameters
- An AI review from the chosen LLM provider
- A score from 1 to 10

## Available tools

| Tool | What it does |
|------|--------------|
| `analyze_audio` | Upload an MP3/WAV/FLAC and get an analysis |
| `check_providers` | The list of available LLM providers |
| `get_status` | System status (Essentia, providers) |

### How `analyze_audio` waits for the result

The server analyses tracks in the background: the upload is queued, and a separate worker does the work. So `analyze_audio` uploads the file, then asks the server every couple of seconds whether the analysis is ready, and hands the finished result to Claude. That means:

- the **worker must be running** (`docker compose up` starts it for you), otherwise the tool waits until it times out;
- it waits up to **5 minutes** by default. To change that, add `MUSE_ANALYSIS_TIMEOUT` (in seconds) to the `env` block of the Claude Desktop config shown above;
- if the analysis fails or times out, Claude gets an `error` message instead of the analysis.

## Example requests

```
"Which providers are available for the analysis?"
→ Uses check_providers

"Analyse track.mp3 and tell me whether it is a danceable track"
→ Uses analyze_audio, then the LLM interprets the results

"Check the status of the analysis service"
→ Uses get_status
```

## Testing

Start the API container:
```bash
docker compose up -d
```

Claude Desktop starts the MCP server automatically. For a manual check:
```bash
python mcp_server.py
```

Then look at the MCP server's logs.
