# MCP server for Muse Analyse

To plug Muse Analyse into Claude Desktop (or another app) as an MCP server, you need an MCP server wrapper.

## A minimal MCP server implementation

Create a file called `mcp_server.py` in the project root:

```python
"""MCP server for Muse Analyse: analysis of musical compositions."""

import asyncio
import json
from pathlib import Path

from mcp.server import Server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
    ToolUseBlock,
)
from pydantic import BaseModel

import httpx

SERVER_URL = "http://localhost:8000"

server = Server("muse-analyse")


class AudioFeatures(BaseModel):
    duration_sec: float
    bpm: float
    key: str
    scale: str
    energy: float
    danceability: float | None
    loudness_ebu128_lufs: float
    dynamic_complexity: float
    spectral_brightness: float


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Returns the list of available tools."""
    return [
        Tool(
            name="check_providers",
            description="Check which LLM providers are available for the analysis",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="analyze_audio",
            description="Upload an audio file and get a music analysis with an AI review",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the audio file (MP3, WAV, FLAC, OGG, M4A)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="get_health",
            description="Get the service status and which components are available",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Runs the tool that was called."""
    
    if name == "check_providers":
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVER_URL}/api/providers")
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
    
    elif name == "analyze_audio":
        file_path = arguments.get("file_path")
        if not Path(file_path).exists():
            return json.dumps({"error": f"File not found: {file_path}"})
        
        async with httpx.AsyncClient(timeout=60) as client:
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f)}
                response = await client.post(f"{SERVER_URL}/api/analyze", files=files)
            if response.status_code != 200:
                return json.dumps({"error": response.text})

            # /api/analyze only queues the analysis and returns a task_id,
            # so we have to wait for the result ourselves
            task_id = response.json()["task_id"]
            for _ in range(150):  # up to about 5 minutes
                state = (await client.get(f"{SERVER_URL}/api/tasks/{task_id}")).json()
                if state["status"] == "done":
                    return json.dumps(state["result"], ensure_ascii=False, indent=2)
                if state["status"] == "error":
                    return json.dumps({"error": state["error"]})
                await asyncio.sleep(2)
            return json.dumps({"error": "The analysis took too long"})
    
    elif name == "get_health":
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{SERVER_URL}/api/health")
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
    
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


if __name__ == "__main__":
    import asyncio
    
    # Run the MCP server over stdio
    async def main():
        async with server:
            await server.wait_for_shutdown()
    
    asyncio.run(main())
```

## Integrating with Claude Desktop

### 1. Prepare the MCP client

```bash
source .venv/bin/activate
pip install mcp httpx
```

The app itself runs in a Docker container. The MCP client does not need to go inside Claude Desktop's container.

### 2. Add the configuration

**On macOS:**
Edit `~/Library/Application\ Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "muse-analyse": {
      "command": "python",
      "args": [
        "/path/to/muse-analyse/mcp_server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**On Windows:**
`%APPDATA%\Claude\claude_desktop_config.json`

**On Linux:**
`~/.config/Claude/claude_desktop_config.json`

### 3. Start the Muse Analyse container

```bash
cd /path/to/muse-analyse
docker compose up -d --build
```

Check the API:

```bash
curl http://localhost:8000/api/health
```

If you have the standalone Compose, use `docker-compose` instead of `docker compose`.

### 4. Restart Claude Desktop

Claude Desktop will now offer these tools:
- **check_providers**: check which LLMs are available
- **analyze_audio**: upload and analyse a track
- **get_health**: the system status

## Usage examples in Claude

### Analysing a track
```
Analyse the track "~/Music/song.mp3" and give me a detailed review
```

Claude uses the `analyze_audio` tool and gets the parameters and the review from Essentia + the LLM.

### Checking the setup
```
Which LLM providers are available for analysing music?
```

Claude uses `check_providers` and shows the status.

---

## An alternative: FastAPI + nginx

If you want to use Muse Analyse through the plain HTTP API, without MCP:

```bash
# Start the container
docker compose up -d

# Use the API directly with curl or Python requests
curl http://localhost:8000/api/providers
```

On a VPS, replace `localhost:8000` with the app's domain once you have set up a reverse proxy and HTTPS. The MCP configuration should point at the MCP process running on the user's own machine; that process reaches the API through the `MUSE_API` value.

---

## Documentation

- [MCP Protocol](https://modelcontextprotocol.io/)
- [Claude Desktop Configuration](https://claude.ai/desktop)
- [Muse Analyse API](./README.md)
- [LLM providers](./LLM_PROVIDERS.md)
