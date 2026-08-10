"""CLI entry: python main.py SSIS-001 [--provider javbus]

Provider 本體在 backend/app/clients/。"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.clients import get_provider, list_providers, NotFoundError, ProviderError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


async def run(code: str, provider_name: str) -> int:
    provider = get_provider(provider_name)
    try:
        movie = await provider.search(code)
    except NotFoundError as e:
        print(f"[not found] {e}", file=sys.stderr)
        return 1
    except ProviderError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    print(json.dumps(movie.to_dict(), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="jav-metadata-syncer provider tester")
    parser.add_argument("code", help="movie code, e.g. SSIS-001")
    parser.add_argument(
        "--provider",
        default="javbus",
        choices=list_providers(),
        help="provider to query",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.code, args.provider)))


if __name__ == "__main__":
    main()
