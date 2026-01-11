#!/usr/bin/env python3
"""
mrmd-orchestrator CLI

Starts all mrmd services and provides HTTP API for management.

Usage:
    mrmd                           # Start with defaults
    mrmd --docs ./notebooks        # Custom docs directory
    mrmd --port 3000               # Custom HTTP port
    mrmd --no-editor               # Don't serve editor
    mrmd --sync-url ws://remote    # Connect to remote sync (don't start local)
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config import OrchestratorConfig, SyncConfig, RuntimeConfig, MonitorConfig, EditorConfig
from .orchestrator import Orchestrator
from .server import run_server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mrmd")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="mrmd",
        description="Orchestrator for mrmd services - sync, monitors, and runtimes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mrmd                              Start all services with defaults
  mrmd --docs ./notebooks           Use custom docs directory
  mrmd --port 3000                  Serve editor on port 3000
  mrmd --no-sync                    Don't start mrmd-sync (connect to existing)
  mrmd --sync-url ws://remote:4444  Connect to remote sync server

The orchestrator starts:
  - mrmd-sync (Yjs sync server) on ws://localhost:4444
  - mrmd-python (Python runtime) on http://localhost:8000
  - HTTP server for editor and API on http://localhost:8080

Monitors are started on-demand via the API:
  POST /api/monitors {"doc": "my-notebook"}
        """,
    )

    # Paths
    parser.add_argument(
        "--docs", "-d",
        default="./docs",
        help="Directory for synced documents (default: ./docs)",
    )
    parser.add_argument(
        "--packages",
        help="Path to mrmd-packages directory (auto-detected by default)",
    )

    # Ports
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="HTTP server port for editor and API (default: 8080)",
    )
    parser.add_argument(
        "--sync-port",
        type=int,
        default=4444,
        help="WebSocket port for mrmd-sync (default: 4444)",
    )
    parser.add_argument(
        "--runtime-port",
        type=int,
        default=8000,
        help="HTTP port for Python runtime (default: 8000)",
    )

    # Remote services
    parser.add_argument(
        "--sync-url",
        help="Connect to existing sync server instead of starting one",
    )
    parser.add_argument(
        "--runtime-url",
        help="Connect to existing Python runtime instead of starting one",
    )

    # Disable services
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Don't start mrmd-sync",
    )
    parser.add_argument(
        "--no-runtime",
        action="store_true",
        help="Don't start mrmd-python",
    )
    parser.add_argument(
        "--no-editor",
        action="store_true",
        help="Don't serve editor files",
    )
    parser.add_argument(
        "--no-monitors",
        action="store_true",
        help="Don't allow starting monitors",
    )

    # Auto-start monitors
    parser.add_argument(
        "--monitor",
        action="append",
        dest="monitors",
        metavar="DOC",
        help="Auto-start monitor for document (can be repeated)",
    )

    # Misc
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level (default: info)",
    )

    return parser.parse_args()


def build_config(args) -> OrchestratorConfig:
    """Build configuration from arguments."""
    config = OrchestratorConfig()

    # Package path
    if args.packages:
        config.packages_dir = args.packages

    # Sync config
    if args.sync_url:
        config.sync = SyncConfig(
            managed=False,
            url=args.sync_url,
        )
    elif args.no_sync:
        config.sync = SyncConfig(
            managed=False,
            url=f"ws://localhost:{args.sync_port}",
        )
    else:
        config.sync = SyncConfig(
            managed=True,
            url=f"ws://localhost:{args.sync_port}",
            port=args.sync_port,
            docs_dir=args.docs,
        )

    # Runtime config
    if args.runtime_url:
        config.runtimes = {
            "python": RuntimeConfig(
                managed=False,
                url=args.runtime_url,
                language="python",
            )
        }
    elif args.no_runtime:
        config.runtimes = {
            "python": RuntimeConfig(
                managed=False,
                url=f"http://localhost:{args.runtime_port}/mrp/v1",
                language="python",
            )
        }
    else:
        config.runtimes = {
            "python": RuntimeConfig(
                managed=True,
                url=f"http://localhost:{args.runtime_port}/mrp/v1",
                port=args.runtime_port,
                language="python",
            )
        }

    # Monitor config
    config.monitor = MonitorConfig(
        managed=not args.no_monitors,
    )

    # Editor config
    config.editor = EditorConfig(
        enabled=not args.no_editor,
        port=args.port,
    )

    # Log level
    config.log_level = args.log_level

    # Resolve package paths
    config.resolve_paths()

    return config


async def async_main(args):
    """Async main entry point."""

    # Build config
    config = build_config(args)

    # Set log level
    logging.getLogger().setLevel(getattr(logging, config.log_level.upper()))

    # Create orchestrator
    orchestrator = Orchestrator(config)

    # Setup shutdown handler
    shutdown_event = asyncio.Event()

    def handle_signal():
        logger.info("Shutdown requested...")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        # Start orchestrator
        await orchestrator.start()

        # Auto-start monitors if specified
        if args.monitors:
            for doc in args.monitors:
                await orchestrator.start_monitor(doc)

        # Print status
        urls = orchestrator.get_urls()
        print()
        print("\033[36m  mrmd orchestrator\033[0m")
        print("  " + "─" * 40)
        print(f"  Editor:   http://localhost:{config.editor.port}")
        print(f"  Sync:     {urls['sync']}")
        print(f"  Runtime:  {urls['runtimes'].get('python', 'not running')}")
        print(f"  API:      http://localhost:{config.editor.port}/api/status")
        print()
        print("  Monitors can be started via API:")
        print(f"    curl -X POST http://localhost:{config.editor.port}/api/monitors -H 'Content-Type: application/json' -d '{{\"doc\": \"my-notebook\"}}'")
        print()

        # Run server (blocks until shutdown)
        server_task = asyncio.create_task(
            run_server(orchestrator, port=config.editor.port)
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

        # Cancel server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    finally:
        # Stop orchestrator
        await orchestrator.stop()


def main():
    """Main entry point."""
    args = parse_args()

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
