#!/usr/bin/env python3
"""
mrmd-orchestrator CLI

Starts all mrmd services and provides HTTP API for management.

Usage:
    mrmd                                     # Start with defaults
    mrmd --docs ./notebooks                  # Custom docs directory
    mrmd --port 3000                         # Custom HTTP port
    mrmd --no-editor                         # Don't serve editor
    mrmd --sync-url ws://remote              # Connect to remote sync (don't start local)
    mrmd --session my-notebook               # Auto-start session (shared Python)
    mrmd --session my-notebook:dedicated     # Auto-start session with dedicated Python runtime
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config import OrchestratorConfig, SyncConfig, RuntimeConfig, MonitorConfig, EditorConfig, AiConfig
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
    parser.add_argument(
        "--ai-port",
        type=int,
        default=51790,
        help="HTTP port for AI server (default: 51790)",
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
    parser.add_argument(
        "--ai-url",
        help="Connect to existing AI server instead of starting one",
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
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Don't start AI server",
    )

    # AI options
    parser.add_argument(
        "--juice-level", "-j",
        type=int,
        default=0,
        choices=[0, 1, 2, 3, 4],
        help="Default AI juice level: 0=Quick, 1=Balanced, 2=Deep, 3=Maximum, 4=Ultimate (default: 0)",
    )

    # Auto-start monitors
    parser.add_argument(
        "--monitor",
        action="append",
        dest="monitors",
        metavar="DOC",
        help="Auto-start monitor for document (can be repeated)",
    )

    # Auto-start sessions (with optional dedicated runtime)
    parser.add_argument(
        "--session",
        action="append",
        dest="sessions",
        metavar="DOC[:MODE]",
        help="Auto-start session for document. MODE is 'shared' (default) or 'dedicated'. "
             "Examples: --session notebook, --session notebook:dedicated (can be repeated)",
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

    # AI config
    if args.ai_url:
        config.ai = AiConfig(
            managed=False,
            url=args.ai_url,
            default_juice_level=args.juice_level,
        )
    elif args.no_ai:
        config.ai = AiConfig(
            managed=False,
            url=f"http://localhost:{args.ai_port}",
            default_juice_level=args.juice_level,
        )
    else:
        config.ai = AiConfig(
            managed=True,
            url=f"http://localhost:{args.ai_port}",
            port=args.ai_port,
            default_juice_level=args.juice_level,
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

        # Auto-start monitors if specified (legacy flag, creates session with shared runtime)
        if args.monitors:
            for doc in args.monitors:
                await orchestrator.create_session(doc, python="shared")

        # Auto-start sessions if specified
        if args.sessions:
            for session_spec in args.sessions:
                # Parse doc:mode format
                if ":" in session_spec:
                    parts = session_spec.rsplit(":", 1)
                    doc = parts[0]
                    mode = parts[1].lower()
                    if mode not in ("shared", "dedicated"):
                        logger.warning(f"Invalid session mode '{mode}' for {doc}, using 'shared'")
                        mode = "shared"
                else:
                    doc = session_spec
                    mode = "shared"

                await orchestrator.create_session(doc, python=mode)
                logger.info(f"Started session for {doc} (python={mode})")

        # Print status
        urls = orchestrator.get_urls()
        sessions = orchestrator.get_sessions()
        juice_names = ["Quick", "Balanced", "Deep", "Maximum", "Ultimate"]
        print()
        print("\033[36m  mrmd orchestrator\033[0m")
        print("  " + "─" * 40)
        print(f"  Editor:   http://localhost:{config.editor.port}")
        print(f"  Sync:     {urls['sync']}")
        print(f"  Runtime:  {urls['runtimes'].get('python', 'not running')} (shared)")
        if urls.get('ai'):
            print(f"  AI:       {urls['ai']} (juice={juice_names[config.ai.default_juice_level]})")
        print(f"  API:      http://localhost:{config.editor.port}/api/status")

        # Show active sessions
        if sessions:
            print()
            print("  \033[36mActive Sessions:\033[0m")
            for doc, session in sessions.items():
                runtime_info = "dedicated" if session.dedicated_runtime else "shared"
                port_info = f" (port {session.runtime_port})" if session.runtime_port else ""
                print(f"    {doc}: python={runtime_info}{port_info}")

        print()
        print("  Sessions can be started via API:")
        print(f"    curl -X POST http://localhost:{config.editor.port}/api/sessions \\")
        print(f"      -H 'Content-Type: application/json' \\")
        print(f"      -d '{{\"doc\": \"my-notebook\", \"python\": \"dedicated\"}}'")
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
