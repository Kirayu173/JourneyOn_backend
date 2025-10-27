"""运行JourneyOn外部服务的连接性检查。

用法：
    python scripts/check_dependencies.py

该脚本会为Redis、Qdrant、嵌入后端和配置的LLM提供程序打印简洁的状态行。
使用``--json``参数可以输出结构化数据，供CI流水线使用。
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
    parser = argparse.ArgumentParser(description="验证外部服务连接性")
    parser.add_argument("--json", action="store_true", help="输出机器可读的JSON格式")
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


if __name__ == "__main__":  # pragma: no cover - 手动脚本入口点
    raise SystemExit(main())
