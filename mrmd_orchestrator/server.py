"""
HTTP API server for mrmd-orchestrator.

Provides:
- API for starting/stopping monitors
- Status endpoints
- Static file serving for mrmd-editor
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .orchestrator import Orchestrator
from .config import OrchestratorConfig

logger = logging.getLogger(__name__)


class MonitorRequest(BaseModel):
    """Request to start a monitor."""
    doc: str


class MonitorResponse(BaseModel):
    """Response for monitor operations."""
    doc: str
    running: bool
    message: str


def create_app(orchestrator: Orchestrator) -> FastAPI:
    """Create FastAPI application with orchestrator endpoints."""

    app = FastAPI(
        title="mrmd-orchestrator",
        description="Orchestrator for mrmd services",
        version="0.1.0",
    )

    # Store orchestrator reference
    app.state.orchestrator = orchestrator

    # --- Health & Status ---

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/api/status")
    async def status():
        """Get status of all services."""
        return orchestrator.get_status()

    @app.get("/api/urls")
    async def urls():
        """Get URLs for all services."""
        return orchestrator.get_urls()

    # --- Monitor Management ---

    @app.get("/api/monitors")
    async def list_monitors():
        """List all active monitors."""
        docs = orchestrator.get_monitor_docs()
        return {
            "monitors": [
                {"doc": doc, "running": orchestrator.is_monitor_running(doc)}
                for doc in docs
            ]
        }

    @app.post("/api/monitors")
    async def start_monitor(request: MonitorRequest):
        """Start a monitor for a document."""
        doc = request.doc

        if orchestrator.is_monitor_running(doc):
            return MonitorResponse(
                doc=doc,
                running=True,
                message=f"Monitor for '{doc}' already running"
            )

        success = await orchestrator.start_monitor(doc)

        if success:
            return MonitorResponse(
                doc=doc,
                running=True,
                message=f"Started monitor for '{doc}'"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start monitor for '{doc}'"
            )

    @app.delete("/api/monitors/{doc}")
    async def stop_monitor(doc: str):
        """Stop the monitor for a document."""
        if not orchestrator.is_monitor_running(doc):
            return MonitorResponse(
                doc=doc,
                running=False,
                message=f"Monitor for '{doc}' not running"
            )

        success = await orchestrator.stop_monitor(doc)

        if success:
            return MonitorResponse(
                doc=doc,
                running=False,
                message=f"Stopped monitor for '{doc}'"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop monitor for '{doc}'"
            )

    @app.get("/api/monitors/{doc}")
    async def get_monitor(doc: str):
        """Get monitor status for a document."""
        running = orchestrator.is_monitor_running(doc)
        return MonitorResponse(
            doc=doc,
            running=running,
            message=f"Monitor {'running' if running else 'not running'}"
        )

    # --- Process Output ---

    @app.get("/api/logs/{process_name}")
    async def get_logs(process_name: str, lines: int = 50):
        """Get recent log output from a process."""
        output = orchestrator.processes.get_output(process_name, lines)
        return {"process": process_name, "lines": output}

    return app


def mount_editor(app: FastAPI, editor_path: Path):
    """Mount mrmd-editor static files."""

    if not editor_path.exists():
        logger.warning(f"Editor path not found: {editor_path}")
        return

    # Mount dist directory for built assets
    dist_path = editor_path / "dist"
    if dist_path.exists():
        app.mount("/dist", StaticFiles(directory=str(dist_path)), name="dist")

    # Mount examples directory
    examples_path = editor_path / "examples"
    if examples_path.exists():
        app.mount("/examples", StaticFiles(directory=str(examples_path), html=True), name="examples")

    # Root redirect to examples
    @app.get("/")
    async def root():
        """Redirect to examples."""
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta http-equiv="refresh" content="0; url=/examples/">
                <title>mrmd</title>
            </head>
            <body>
                <p>Redirecting to <a href="/examples/">examples</a>...</p>
            </body>
            </html>
            """,
            status_code=200,
        )

    logger.info(f"Mounted editor from {editor_path}")


async def run_server(
    orchestrator: Orchestrator,
    host: str = "0.0.0.0",
    port: int = 8080,
):
    """Run the orchestrator HTTP server."""
    import uvicorn

    app = create_app(orchestrator)

    # Mount editor if configured
    if orchestrator.config.editor.enabled:
        editor_path = Path(orchestrator.config.editor.package_path)
        mount_editor(app, editor_path)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
