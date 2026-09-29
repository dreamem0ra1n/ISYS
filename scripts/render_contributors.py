#!/usr/bin/env python3
"""Render human Git authors in the home page's historical contributors section."""

import html
import json
import subprocess
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "content" / "Welcome to ISYS.md"
USERS = ROOT / "scripts" / "contributors.json"
START = "<!-- contributors:start -->"
END = "<!-- contributors:end -->"


def collect_contributors() -> list[str]:
    history = subprocess.check_output(
        ["git", "log", "--format=%an"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    names = []
    seen = set()
    for line in history.splitlines():
        name = line.strip()
        key = name.lower()
        if not name or key == "root" or key.endswith("[bot]") or key in seen:
            continue
        names.append(name)
        seen.add(key)
    return names


def render_contributors(names: list[str]) -> str:
    users = json.loads(USERS.read_text(encoding="utf-8"))
    entries = []
    for name in names:
        escaped_name = html.escape(name, quote=True)
        login = users.get(name.lower())
        if login:
            encoded_login = urllib.parse.quote(login, safe="")
            avatar = (
                f'<img src="https://github.com/{encoded_login}.png?size=96" '
                f'alt="{escaped_name}" width="32" height="32" loading="lazy">'
            )
            entries.append(
                f'<a class="historical-contributor" href="https://github.com/{encoded_login}">'
                f'{avatar}<span>{escaped_name}</span></a>'
            )
        else:
            initial = html.escape(name[0].upper())
            entries.append(
                '<span class="historical-contributor">'
                f'<span class="historical-contributor-initial">{initial}</span>'
                f'<span>{escaped_name}</span></span>'
            )
    return "\n".join(['<div class="historical-contributors">', *entries, "</div>"])


def main() -> None:
    text = PAGE.read_text(encoding="utf-8")
    before, start, remainder = text.partition(START)
    _, end, after = remainder.partition(END)
    if not start or not end:
        raise ValueError(f"首页缺少历史贡献者标记：{PAGE}")
    updated = (
        before + START + "\n" + render_contributors(collect_contributors()) + "\n" + END + after
    )
    if updated != text:
        PAGE.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
