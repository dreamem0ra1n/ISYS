#!/usr/bin/env python3
"""Delete generated course pages from the Quartz content directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from build_course_md import (
    DEFAULT_DOCS_DIR,
    BuildError,
    relative_docs_path,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="删除 Quartz content 目录中的课程 Markdown 页面。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="+",
        type=Path,
        help="需要删除的课程 Markdown 路径",
    )
    parser.add_argument(
        "--content-dir", "--docs-dir", dest="docs_dir", type=Path, default=DEFAULT_DOCS_DIR
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只显示将删除的页面，不修改文件",
    )
    parser.add_argument(
        "--missing-ok",
        action="store_true",
        help="页面不存在时仍继续",
    )
    return parser.parse_args(argv)


def markdown_target(target: Path, docs_dir: Path) -> Path:
    if target.is_absolute():
        destination = target
    else:
        parts = target.parts
        if parts and parts[0] == docs_dir.name:
            target = Path(*parts[1:])
        destination = docs_dir / target
    relative_docs_path(destination, docs_dir)
    return destination


def collect_targets(targets: list[Path], docs_dir: Path) -> list[Path]:
    pages = []
    for target in targets:
        if target.suffix.lower() != ".md":
            raise BuildError(f"只支持 .md 目标：{target}")
        pages.append(markdown_target(target, docs_dir))

    unique = []
    seen = set()
    for page in pages:
        resolved = page.resolve()
        if resolved not in seen:
            unique.append(page)
            seen.add(resolved)
    return unique


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pages = collect_targets(args.targets, args.docs_dir)
    missing = [page for page in pages if not page.is_file()]
    if missing and not args.missing_ok:
        paths = "、".join(str(page) for page in missing)
        raise BuildError(f"课程页面不存在：{paths}；需要忽略缺失页面时使用 --missing-ok")

    for page in pages:
        relative = relative_docs_path(page, args.docs_dir)
        state = "将删除" if page.exists() else "页面不存在"
        print(f"PAGE {state}：{page}")
    if args.check:
        return 0

    for page in pages:
        if page.exists():
            page.unlink()
            print(f"删除 {page}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
