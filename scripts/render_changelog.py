#!/usr/bin/env python3
"""Render the commit log placeholder used by the updates page for Quartz."""

from pathlib import Path

from git_changelog import build_git_changelog


ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "content" / "更新记录和计划.md"
HEADING = "## 更新记录\n"


class BuildEnvironment:
    conf = {"repo_url": "https://github.com/dreamem0ra1n/ISYS"}


def main() -> None:
    text = PAGE.read_text(encoding="utf-8")
    rendered = build_git_changelog(BuildEnvironment(), 50)
    prefix, separator, _ = text.partition(HEADING)
    if not separator:
        raise ValueError(f"找不到更新记录标题：{PAGE}")
    updated = prefix + HEADING + "> 更新记录由 Git commit log 自动生成。\n\n" + rendered + "\n"
    if updated != text:
        PAGE.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
