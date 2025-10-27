"""Run connectivity checks for external JourneyOn services.

Usage:
    python scripts/check_dependencies.py

The script prints a concise status line for Redis, Qdrant, the embedding
backend, and the configured LLM provider.  Use ``--json`` to emit structured
output that can be consumed by CI pipelines.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.utils.dependency_check import (  # noqa: E402  (import after sys.path)
    DependencyCheckResult,
    run_dependency_checks,
)


def _format_line(result: DependencyCheckResult) -> str:
    icons = {"ok": "✅", "failed": "❌", "skipped": "⚠️"}
    icon = icons.get(result.status, "?")
    return f"{icon} {result.name:<10} {result.detail}"


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify external service connectivity")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON output")
    return parser.parse_args(list(argv) if argv is not None else None)


async def _run(json_mode: bool) -> int:
    results = await run_dependency_checks()
    if json_mode:
        payload = [result.as_dict() for result in results]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(_format_line(result))

    failures = [r for r in results if r.status == "failed"]
    return 0 if not failures else 1


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return asyncio.run(_run(args.json))


if __name__ == "__main__":  # pragma: no cover - manual script entrypoint
    raise SystemExit(main())
