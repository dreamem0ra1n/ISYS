#!/usr/bin/env python3
"""Update the home page statistics from published Markdown content."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
INDEX = CONTENT / "Welcome to ISYS.md"
EXCLUDED = {"template.md"}


def strip_markdown_noise(text: str) -> str:
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    return re.sub(r"\[.*?\]\(.*?\)", "", text)


def collect_site_stats(content_dir: Path = CONTENT) -> tuple[int, int]:
    pages = [path for path in content_dir.rglob("*.md") if path.name not in EXCLUDED]
    chinese_chars = sum(
        len(re.findall(r"[\u4e00-\u9fff]", strip_markdown_noise(path.read_text(encoding="utf-8"))))
        for path in pages
    )
    return len(pages), chinese_chars


def main() -> None:
    pages, chinese_chars = collect_site_stats()
    text = INDEX.read_text(encoding="utf-8")
    updated, words_count = re.subn(
        r"(?m)^(> - \*\*全站字数\*\*：).*$",
        rf"\g<1>{chinese_chars:,} 个汉字",
        text,
    )
    updated, pages_count = re.subn(
        r"(?m)^(> - \*\*页面数\*\*：).*$",
        rf"\g<1>{pages} 页",
        updated,
    )
    if words_count != 1 or pages_count != 1:
        raise ValueError(f"首页统计项不存在或重复：{INDEX}")
    if updated != text:
        INDEX.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
