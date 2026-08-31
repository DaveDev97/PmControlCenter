"""Standalone entry point for the FastAPI backend.

Used both in development and as the target for the PyInstaller build that ships
inside the Electron app (so end users don't need Python installed). Importing
``app`` directly (rather than the "app.main:app" string) ensures PyInstaller
bundles the whole application graph.
"""
import argparse

import uvicorn

from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="PM Control Center backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
