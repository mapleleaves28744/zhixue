"""Local backend entry point with the event loop required by async psycopg."""
from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Zhixue API locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
