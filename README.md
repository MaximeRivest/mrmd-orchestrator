# mrmd-orchestrator

Python orchestrator for mrmd services. Starts and manages sync server, monitors, and runtimes.

## Quick Start

```bash
# From mrmd-packages directory
cd mrmd-orchestrator

# Create virtual environment and install dependencies with uv
uv venv
uv pip install -e .

# Start everything
uv run mrmd

# Or with options
uv run mrmd --docs ./notebooks --port 3000
```

Then open http://localhost:8080/examples/minimal.html

## What It Does

The orchestrator:

1. **Starts mrmd-sync** - Yjs sync server on ws://localhost:4444
2. **Starts mrmd-python** - Python runtime on http://localhost:8000
3. **Serves mrmd-editor** - Static files on http://localhost:8080
4. **Manages monitors** - Start/stop via HTTP API

```
┌─────────────────────────────────────────────────────────────────┐
│  mrmd-orchestrator (Python)                                     │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ mrmd-sync   │  │ mrmd-python │  │ HTTP Server │            │
│  │ (Node.js)   │  │ (Python)    │  │ + API       │            │
│  │ port 4444   │  │ port 8000   │  │ port 8080   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│         │                                   │                   │
│         └──── monitors (per document) ──────┘                   │
│               ┌─────────┐ ┌─────────┐                          │
│               │monitor:a│ │monitor:b│ ...                      │
│               └─────────┘ └─────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## CLI Options

```bash
mrmd [options]

Paths:
  --docs, -d PATH        Document directory (default: ./docs)
  --packages PATH        Path to mrmd-packages (auto-detected)

Ports:
  --port, -p PORT        HTTP/API port (default: 8080)
  --sync-port PORT       Sync server port (default: 4444)
  --runtime-port PORT    Python runtime port (default: 8000)

Remote Services (distributed mode):
  --sync-url URL         Connect to existing sync server
  --runtime-url URL      Connect to existing runtime

Disable Services:
  --no-sync              Don't start mrmd-sync
  --no-runtime           Don't start mrmd-python
  --no-editor            Don't serve editor files
  --no-monitors          Don't allow starting monitors

Auto-start:
  --monitor DOC          Auto-start monitor for document (repeatable)

Examples:
  mrmd                                    # Start everything
  mrmd --docs ./notebooks                 # Custom docs directory
  mrmd --monitor my-notebook              # Auto-start monitor
  mrmd --sync-url ws://remote:4444        # Use remote sync
```

## HTTP API

### Status

```bash
# Health check
GET /health

# Full status
GET /api/status

# Service URLs
GET /api/urls
```

### Monitors

```bash
# List active monitors
GET /api/monitors

# Start monitor for document
POST /api/monitors
Content-Type: application/json
{"doc": "my-notebook"}

# Stop monitor
DELETE /api/monitors/my-notebook

# Check monitor status
GET /api/monitors/my-notebook
```

### Logs

```bash
# Get recent output from a process
GET /api/logs/mrmd-sync?lines=100
GET /api/logs/mrmd-python?lines=50
GET /api/logs/monitor:my-notebook?lines=50
```

## Distributed Mode

For users who want services on different machines:

```bash
# Machine 1: Sync server only
cd mrmd-sync && node bin/cli.js ./docs

# Machine 2: Python runtime only
cd mrmd-python && python -m mrmd_python.cli --port 8000

# Machine 3: Orchestrator connecting to remote services
mrmd \
  --sync-url ws://machine1:4444 \
  --runtime-url http://machine2:8000/mrp/v1 \
  --no-sync \
  --no-runtime
```

Or use the Python API:

```python
from mrmd_orchestrator import Orchestrator, OrchestratorConfig

config = OrchestratorConfig.for_distributed(
    sync_url="ws://remote-sync:4444",
    runtime_urls={"python": "http://remote-python:8000/mrp/v1"},
)

orchestrator = Orchestrator(config)
await orchestrator.start()
```

## Programmatic Usage

```python
import asyncio
from mrmd_orchestrator import Orchestrator, OrchestratorConfig

async def main():
    # Default config (start everything locally)
    config = OrchestratorConfig.for_development()

    # Create orchestrator
    orchestrator = Orchestrator(config)

    # Start services
    await orchestrator.start()

    # Start a monitor
    await orchestrator.start_monitor("my-notebook")

    # Check status
    status = orchestrator.get_status()
    print(status)

    # Stop monitor
    await orchestrator.stop_monitor("my-notebook")

    # Stop everything
    await orchestrator.stop()

asyncio.run(main())
```

## Architecture: 1 Monitor Per Document

Each document gets its own monitor process:

```
Document A ──→ monitor:document-a ──→ mrmd-python (session: document-a)
Document B ──→ monitor:document-b ──→ mrmd-python (session: document-b)
```

**Why?**
- Isolation: Killing notebook A doesn't affect B
- Matches mental model: "Restart" means this notebook
- Security: Different permissions per notebook
- Matches Jupyter: 1 kernel per notebook

**Trade-offs:**
- More processes (10 notebooks = 10 monitors)
- Startup latency when opening new documents

## Development

```bash
# Create venv and install with dev dependencies
cd mrmd-orchestrator
uv venv
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with debug logging
uv run mrmd --log-level debug
```

## License

MIT
