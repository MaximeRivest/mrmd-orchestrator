"""
Main orchestrator for mrmd services.

Coordinates starting/stopping of sync server, monitors, and runtimes.
Supports per-document dedicated Python runtimes for true process isolation.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import OrchestratorConfig
from .processes import ProcessManager

logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    """Information about an active session (document + its resources)."""
    doc: str
    monitor_process: Optional[str] = None
    runtime_process: Optional[str] = None
    runtime_url: Optional[str] = None
    runtime_port: Optional[int] = None
    dedicated_runtime: bool = False


class PortAllocator:
    """Allocates ports for dedicated runtimes."""

    def __init__(self, base_port: int = 8001, max_ports: int = 100):
        self.base_port = base_port
        self.max_ports = max_ports
        self._allocated: set[int] = set()

    def allocate(self) -> int:
        """Allocate the next available port."""
        for offset in range(self.max_ports):
            port = self.base_port + offset
            if port not in self._allocated:
                self._allocated.add(port)
                return port
        raise RuntimeError(f"No available ports in range {self.base_port}-{self.base_port + self.max_ports}")

    def release(self, port: int):
        """Release a previously allocated port."""
        self._allocated.discard(port)

    def is_allocated(self, port: int) -> bool:
        """Check if a port is allocated."""
        return port in self._allocated


class Orchestrator:
    """
    Orchestrates mrmd services.

    Can run in two modes:
    - Local/development: Starts all services as subprocesses
    - Distributed: Connects to existing remote services
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig.for_development()
        self.processes = ProcessManager()
        self._monitors: dict[str, str] = {}  # doc_name -> process_name
        self._sessions: dict[str, SessionInfo] = {}  # doc_name -> SessionInfo
        self._port_allocator = PortAllocator(base_port=8001)
        self._started = False

    async def start(self):
        """Start all managed services."""
        if self._started:
            return

        logger.info("Starting mrmd orchestrator...")

        # Start sync server if managed
        if self.config.sync.managed:
            await self._start_sync()

        # Start runtimes if managed
        for lang, runtime_config in self.config.runtimes.items():
            if runtime_config.managed:
                await self._start_runtime(lang, runtime_config)

        self._started = True
        logger.info("Orchestrator ready")

    async def stop(self):
        """Stop all managed services."""
        if not self._started:
            return

        logger.info("Stopping mrmd orchestrator...")

        # Stop all monitors first
        for doc_name in list(self._monitors.keys()):
            await self.stop_monitor(doc_name)

        # Stop all processes
        await self.processes.stop_all()

        self._started = False
        logger.info("Orchestrator stopped")

    async def _start_sync(self):
        """Start mrmd-sync server."""
        config = self.config.sync
        package_path = Path(config.package_path)

        if not package_path.exists():
            logger.error(f"mrmd-sync not found at {package_path}")
            return

        # Ensure docs directory exists
        docs_dir = Path(config.docs_dir)
        docs_dir.mkdir(parents=True, exist_ok=True)

        command = [
            "node",
            str(package_path / "bin" / "cli.js"),
            "--port", str(config.port),
            str(docs_dir.absolute()),
        ]

        await self.processes.start(
            name="mrmd-sync",
            command=command,
            cwd=str(package_path),
            wait_for="Server started",  # JSON output contains this
            timeout=10.0,
        )

    async def _start_runtime(self, language: str, runtime_config):
        """Start a runtime server."""
        if language == "python":
            await self._start_python_runtime(runtime_config)
        else:
            logger.warning(f"Unknown runtime language: {language}")

    async def _start_python_runtime(self, runtime_config):
        """Start mrmd-python runtime."""
        package_path = Path(runtime_config.package_path)

        if not package_path.exists():
            logger.error(f"mrmd-python not found at {package_path}")
            return

        # Use uv run to execute in the package's virtual environment
        command = [
            "uv", "run", "python", "-m", "mrmd_python.cli",
            "--port", str(runtime_config.port),
        ]

        await self.processes.start(
            name="mrmd-python",
            command=command,
            cwd=str(package_path),
            wait_for="Uvicorn running",
            timeout=15.0,
        )

    async def start_monitor(self, doc_name: str) -> bool:
        """
        Start a monitor for a specific document.

        Args:
            doc_name: Document name (Yjs room name)

        Returns:
            True if monitor started successfully
        """
        if not self.config.monitor.managed:
            logger.warning("Monitors not managed by orchestrator")
            return False

        if doc_name in self._monitors:
            logger.info(f"Monitor for {doc_name} already running")
            return True

        package_path = Path(self.config.monitor.package_path)

        if not package_path.exists():
            logger.error(f"mrmd-monitor not found at {package_path}")
            return False

        process_name = f"monitor:{doc_name}"

        command = [
            "node",
            str(package_path / "bin" / "cli.js"),
            "--doc", doc_name,
            self.config.sync.url,
        ]

        info = await self.processes.start(
            name=process_name,
            command=command,
            cwd=str(package_path),
            wait_for="Monitor ready",
            timeout=10.0,
        )

        if info.status == "running":
            self._monitors[doc_name] = process_name
            logger.info(f"Started monitor for {doc_name}")
            return True
        else:
            logger.error(f"Failed to start monitor for {doc_name}")
            return False

    async def stop_monitor(self, doc_name: str) -> bool:
        """
        Stop the monitor for a specific document.

        Args:
            doc_name: Document name

        Returns:
            True if monitor stopped successfully
        """
        process_name = self._monitors.get(doc_name)
        if not process_name:
            return True

        success = await self.processes.stop(process_name)
        if success:
            del self._monitors[doc_name]
            logger.info(f"Stopped monitor for {doc_name}")
        return success

    def get_monitor_docs(self) -> list[str]:
        """Get list of documents with active monitors."""
        return list(self._monitors.keys())

    def is_monitor_running(self, doc_name: str) -> bool:
        """Check if monitor is running for a document."""
        process_name = self._monitors.get(doc_name)
        return process_name is not None and self.processes.is_running(process_name)

    def get_status(self) -> dict:
        """Get status of all services."""
        return {
            "started": self._started,
            "sync": {
                "managed": self.config.sync.managed,
                "url": self.config.sync.url,
                "running": self.processes.is_running("mrmd-sync"),
            },
            "runtimes": {
                lang: {
                    "managed": cfg.managed,
                    "url": cfg.url,
                    "running": self.processes.is_running(f"mrmd-{lang}"),
                }
                for lang, cfg in self.config.runtimes.items()
            },
            "monitors": {
                doc: {
                    "running": self.is_monitor_running(doc),
                }
                for doc in self._monitors
            },
            "processes": self.processes.get_status(),
        }

    def get_urls(self) -> dict:
        """Get URLs for all services."""
        return {
            "sync": self.config.sync.url,
            "runtimes": {
                lang: cfg.url
                for lang, cfg in self.config.runtimes.items()
            },
            "editor": f"http://localhost:{self.config.editor.port}" if self.config.editor.enabled else None,
        }

    # =========================================================================
    # Session Management (per-document resources)
    # =========================================================================

    async def create_session(
        self,
        doc_name: str,
        python: str = "shared",
    ) -> SessionInfo:
        """
        Create a session for a document with optional dedicated runtime.

        Args:
            doc_name: Document name (Yjs room name)
            python: "shared" to use the shared runtime, "dedicated" for isolated runtime

        Returns:
            SessionInfo with URLs and process info
        """
        # Check if session already exists
        if doc_name in self._sessions:
            session = self._sessions[doc_name]
            # If requesting dedicated but have shared (or vice versa), recreate
            if (python == "dedicated") != session.dedicated_runtime:
                await self.destroy_session(doc_name)
            else:
                return session

        session = SessionInfo(doc=doc_name)

        # Start monitor for this document
        if self.config.monitor.managed:
            await self.start_monitor(doc_name)
            session.monitor_process = self._monitors.get(doc_name)

        # Handle Python runtime
        if python == "dedicated":
            # Start dedicated Python runtime on new port
            port = self._port_allocator.allocate()
            runtime_url = f"http://localhost:{port}/mrp/v1"

            process_name = f"python:{doc_name}"
            package_path = Path(self.config.runtimes.get("python", {}).package_path
                              if self.config.runtimes.get("python")
                              else self.config._find_packages_dir() + "/mrmd-python")

            # Use the same package path as the shared runtime
            python_config = self.config.runtimes.get("python")
            if python_config and python_config.package_path:
                package_path = Path(python_config.package_path)

            if package_path.exists():
                command = [
                    "uv", "run", "python", "-m", "mrmd_python.cli",
                    "--port", str(port),
                ]

                await self.processes.start(
                    name=process_name,
                    command=command,
                    cwd=str(package_path),
                    wait_for="Uvicorn running",
                    timeout=15.0,
                )

                session.runtime_process = process_name
                session.runtime_url = runtime_url
                session.runtime_port = port
                session.dedicated_runtime = True
                logger.info(f"Started dedicated Python runtime for {doc_name} on port {port}")
            else:
                logger.error(f"mrmd-python not found at {package_path}")
                self._port_allocator.release(port)
        else:
            # Use shared runtime
            python_config = self.config.runtimes.get("python")
            if python_config:
                session.runtime_url = python_config.url
                session.dedicated_runtime = False

        self._sessions[doc_name] = session
        logger.info(f"Created session for {doc_name} (dedicated={session.dedicated_runtime})")
        return session

    async def destroy_session(self, doc_name: str) -> bool:
        """
        Destroy a session and clean up its resources.

        Args:
            doc_name: Document name

        Returns:
            True if session was destroyed
        """
        session = self._sessions.get(doc_name)
        if not session:
            return True

        # Stop dedicated runtime if any
        if session.runtime_process:
            await self.processes.stop(session.runtime_process)
            if session.runtime_port:
                self._port_allocator.release(session.runtime_port)
            logger.info(f"Stopped dedicated runtime for {doc_name}")

        # Stop monitor
        if session.monitor_process:
            await self.stop_monitor(doc_name)

        del self._sessions[doc_name]
        logger.info(f"Destroyed session for {doc_name}")
        return True

    def get_session(self, doc_name: str) -> Optional[SessionInfo]:
        """Get session info for a document."""
        return self._sessions.get(doc_name)

    def get_sessions(self) -> dict[str, SessionInfo]:
        """Get all active sessions."""
        return dict(self._sessions)

    def get_session_info(self, doc_name: str) -> Optional[dict]:
        """Get session info as a dict for API responses."""
        session = self._sessions.get(doc_name)
        if not session:
            return None

        return {
            "doc": session.doc,
            "sync": self.config.sync.url,
            "monitor": {
                "status": "running" if self.is_monitor_running(doc_name) else "stopped",
                "name": session.monitor_process,
            },
            "runtimes": {
                "python": {
                    "url": session.runtime_url,
                    "dedicated": session.dedicated_runtime,
                    "port": session.runtime_port,
                    "process": session.runtime_process,
                }
            } if session.runtime_url else {},
        }
