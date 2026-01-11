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


class SessionRequest(BaseModel):
    """Request to create a session."""
    doc: str
    python: str = "shared"  # "shared" or "dedicated"


class SessionResponse(BaseModel):
    """Response for session operations."""
    doc: str
    sync: str
    monitor: dict
    runtimes: dict


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

    # --- File Management ---

    @app.get("/api/files")
    async def list_files():
        """List markdown files in the docs directory."""
        docs_dir = Path(orchestrator.config.sync.docs_dir)
        if not docs_dir.exists():
            return {"files": []}

        files = []
        for f in sorted(docs_dir.glob("*.md")):
            if f.is_file():
                stat = f.stat()
                files.append({
                    "name": f.stem,  # filename without .md
                    "path": f.name,  # filename with .md
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
        return {"files": files}

    @app.post("/api/files")
    async def create_file(request: dict):
        """Create a new markdown file."""
        name = request.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")

        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_").strip()
        if not safe_name:
            raise HTTPException(status_code=400, detail="Invalid filename")

        docs_dir = Path(orchestrator.config.sync.docs_dir)
        docs_dir.mkdir(parents=True, exist_ok=True)

        file_path = docs_dir / f"{safe_name}.md"
        if file_path.exists():
            raise HTTPException(status_code=409, detail=f"File '{safe_name}' already exists")

        # Create with default content
        content = request.get("content", f"# {name}\n\nStart writing...\n")
        file_path.write_text(content)

        return {"name": safe_name, "path": f"{safe_name}.md"}

    @app.delete("/api/files/{name}")
    async def delete_file(name: str):
        """Delete a markdown file."""
        docs_dir = Path(orchestrator.config.sync.docs_dir)
        file_path = docs_dir / f"{name}.md"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File '{name}' not found")

        # Also destroy session if exists
        await orchestrator.destroy_session(name)

        file_path.unlink()
        return {"status": "deleted", "name": name}

    # --- Session Management ---

    @app.get("/api/sessions")
    async def list_sessions():
        """List all active sessions."""
        sessions = orchestrator.get_sessions()
        return {
            "sessions": [
                orchestrator.get_session_info(doc) for doc in sessions.keys()
            ]
        }

    @app.post("/api/sessions")
    async def create_session(request: SessionRequest):
        """
        Create a session for a document.

        This starts a monitor and optionally a dedicated Python runtime.

        Request body:
            doc: Document name (Yjs room name)
            python: "shared" (default) or "dedicated"

        Returns session info with URLs for sync, monitor, and runtime.
        """
        doc = request.doc
        python = request.python

        if python not in ("shared", "dedicated"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid python option: {python}. Must be 'shared' or 'dedicated'"
            )

        try:
            await orchestrator.create_session(doc, python=python)
            info = orchestrator.get_session_info(doc)

            if not info:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create session for '{doc}'"
                )

            return info
        except Exception as e:
            logger.error(f"Failed to create session for {doc}: {e}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )

    @app.get("/api/sessions/{doc}")
    async def get_session(doc: str):
        """Get session info for a document."""
        info = orchestrator.get_session_info(doc)
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"No session for '{doc}'"
            )
        return info

    @app.delete("/api/sessions/{doc}")
    async def delete_session(doc: str):
        """
        Destroy a session and clean up its resources.

        This stops the monitor and any dedicated runtime for the document.
        """
        success = await orchestrator.destroy_session(doc)
        if success:
            return {"doc": doc, "status": "destroyed"}
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to destroy session for '{doc}'"
            )

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
