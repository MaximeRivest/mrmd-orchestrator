"""
Main orchestrator for mrmd services.

Coordinates starting/stopping of sync server, monitors, and runtimes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .config import OrchestratorConfig
from .processes import ProcessManager

logger = logging.getLogger(__name__)


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
