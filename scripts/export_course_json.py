#!/usr/bin/env python3
"""Export existing course Markdown pages to one JSON file per course."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

if __package__:
    from .build_course_md import (
        DEFAULT_DOCS_DIR,
        DEFAULT_MKDOCS_CONFIG,
        PROJECT_DIR,
        BuildError,
        atomic_write,
        nav_bounds,
        output_path,
        parse_nav_item,
        parse_yaml_scalar,
        read_text,
    )
else:
    from build_course_md import (
        DEFAULT_DOCS_DIR,
        DEFAULT_MKDOCS_CONFIG,
        PROJECT_DIR,
        BuildError,
        atomic_write,
        nav_bounds,
        output_path,
        parse_nav_item,
        parse_yaml_scalar,
        read_text,
    )


DEFAULT_OUTPUT_DIR = PROJECT_DIR / "data"

CATEGORY_BY_CLASS = {
    "basic": "专业基础",
    "required": "专业必修",
    "advanced": "专业进阶",
    "practice": "实践教学",
    "elective-basic": "专业选修-应用基础",
    "elective-practice": "专业选修-实践拓展",
}

TAG_PATTERN = re.compile(
    r'<span\s+class="tag\s+tag-([^"\s]+)"\s*>(.*?)</span>',
    flags=re.DOTALL,
)
TAB_PATTERN = re.compile(r'^===\s+"(.*?)"\s*$', flags=re.MULTILINE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 docs 中的课程 Markdown 导出为保持相同层级的 JSON 文件。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="课程 Markdown；不指定时扫描 docs 下所有课程页面",
    )
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--mkdocs-config",
        type=Path,
        default=DEFAULT_MKDOCS_CONFIG,
        help="用于保留自定义导航标题",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只解析并显示输出路径，不写文件",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已经存在的 JSON 文件",
    )
    return parser.parse_args(argv)


def parse_front_matter(markdown: str, path: Path) -> dict[str, Any]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", markdown, re.DOTALL)
    if not match:
        raise BuildError(f"{path}: 缺少 YAML front matter")
    result: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = parse_yaml_scalar(value)
        if key == "comments":
            result[key] = value.lower() == "true"
        elif key in {"title", "en_title"} and value:
            result[key] = value
    if not result.get("title"):
        raise BuildError(f"{path}: front matter 缺少 title")
    return result


def plain_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def parse_credit(value: str) -> str | int | float:
    value = value.removesuffix("学分").strip()
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() else number


def parse_tags(markdown: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for css_class, raw_label in TAG_PATTERN.findall(markdown):
        label = plain_text(raw_label)
        if css_class in CATEGORY_BY_CLASS:
            result["category"] = CATEGORY_BY_CLASS[css_class]
        elif css_class == "credit":
            result["credits"] = parse_credit(label)
        elif css_class.startswith("location-"):
            result["location"] = label
        elif css_class == "number":
            result["course_number"] = label
    return result


def parse_sections(markdown: str) -> dict[str, str]:
    matches = list(re.finditer(r"^### (.+?)\s*$", markdown, re.MULTILINE))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group(1)] = markdown[match.end() : end].strip()
    return sections


def parse_header_notes(markdown: str) -> tuple[str | None, list[Any]]:
    first_section = re.search(r"^### ", markdown, re.MULTILINE)
    header = markdown[: first_section.start()] if first_section else markdown
    recommended = None
    notes: list[Any] = []
    pattern = re.compile(
        r'^!!!\s+([A-Za-z][A-Za-z0-9_-]*)\s+"(.*?)"\s*$',
        re.MULTILINE,
    )
    matches = list(pattern.finditer(header))
    for match in matches:
        admonition_type = match.group(1)
        title = html.unescape(match.group(2))
        recommended_match = re.fullmatch(
            r"培养方案推荐修读学期：\*\*(.+?)\*\*",
            title,
        )
        if admonition_type == "note" and recommended_match:
            recommended = html.unescape(recommended_match.group(1))
            continue

        content_lines = []
        for line in header[match.end() :].splitlines()[1:]:
            if line.startswith("    "):
                content_lines.append(line[4:])
            elif line.startswith("\t"):
                content_lines.append(line[1:])
            elif line.strip():
                break
            elif content_lines:
                content_lines.append("")
        content = "\n".join(content_lines).rstrip()
        if admonition_type == "note" and not content:
            notes.append(title)
            continue
        note: dict[str, Any] = {
            "type": admonition_type,
            "title": title,
        }
        if content:
            note["content"] = content
        notes.append(note)
    return recommended, notes


def dedent_tab_body(value: str) -> str:
    return textwrap.dedent(value.expandtabs(4)).strip()


def parse_tabs(value: str) -> list[tuple[str, str]] | None:
    matches = list(TAB_PATTERN.finditer(value))
    if not matches or value[: matches[0].start()].strip():
        return None
    tabs = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        tabs.append((html.unescape(match.group(1)), dedent_tab_body(value[match.end() : end])))
    return tabs


def parse_markdown_list(value: str) -> list[Any] | None:
    nodes: list[dict[str, Any]] = []
    stack: list[tuple[int, dict[str, Any]]] = []
    for line in value.expandtabs(4).splitlines():
        if not line.strip():
            continue
        match = re.match(r"^(\s*)-\s+(.*?)\s*$", line)
        if not match:
            return None
        indent = len(match.group(1))
        node: dict[str, Any] = {"text": match.group(2), "items": []}
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if stack:
            stack[-1][1]["items"].append(node)
        else:
            nodes.append(node)
        stack.append((indent, node))

    def simplify(node: dict[str, Any]) -> Any:
        if not node["items"]:
            return node["text"]
        return {
            "text": node["text"],
            "items": [simplify(child) for child in node["items"]],
        }

    return [simplify(node) for node in nodes] if nodes else None


def parse_resource_link(value: str) -> str | dict[str, Any]:
    match = re.fullmatch(r"\[([^]]+)]\(([^)]+)\)(.*)", value.strip())
    if not match:
        return value.strip()
    result: dict[str, Any] = {
        "title": match.group(1),
        "url": match.group(2),
    }
    description = match.group(3).strip()
    if description:
        if (
            description.startswith("（")
            and description.endswith("）")
        ) or (
            description.startswith("(")
            and description.endswith(")")
        ):
            description = description[1:-1].strip()
        result["description"] = description
    return result


def normalize_resource_list(value: str) -> str:
    lines = []
    for line in value.expandtabs(4).splitlines():
        if not line.strip() or re.match(r"^\s*-\s+", line):
            lines.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        lines.append(f"{' ' * indent}- {line.strip()}")
    return "\n".join(lines)


def resource_items(value: str) -> list[Any]:
    parsed = parse_markdown_list(normalize_resource_list(value))
    if parsed is None:
        return [line.strip() for line in value.splitlines() if line.strip()]
    return convert_resource_items(parsed)


def convert_resource_items(items: list[Any]) -> list[Any]:
    converted = []
    for item in items:
        if isinstance(item, str):
            converted.append(parse_resource_link(item))
            continue
        value = parse_resource_link(item["text"])
        children = convert_resource_items(item.get("items", []))
        if isinstance(value, dict):
            value["items"] = children
            converted.append(value)
        else:
            converted.append({"text": value, "items": children})
    return converted


def add_resource_group(
    result: dict[str, Any],
    title: str,
    items: list[Any],
    tabs: list[dict[str, Any]] | None = None,
) -> None:
    if title in {"外链索引", "外联索引"}:
        result.setdefault("links", []).extend(items)
        return
    term_match = re.fullmatch(r"(?:回忆卷|历年卷)（(.+?)）", title)
    if term_match:
        result.setdefault("exams", []).append(
            {"term": term_match.group(1), "items": items}
        )
        return
    if title == "回忆卷" and tabs:
        result.setdefault("exams", []).extend(tabs)
        return
    section: dict[str, Any] = {"title": title}
    if tabs:
        section["tabs"] = tabs
    else:
        section["items"] = items
    result.setdefault("sections", []).append(section)


def parse_heading_resources(value: str) -> dict[str, Any] | None:
    matches = list(re.finditer(r"^#### (.+?)\s*$", value, re.MULTILINE))
    if not matches or value[: matches[0].start()].strip():
        return None
    result: dict[str, Any] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        title = match.group(1)
        content = value[match.end() : end].strip()
        tab_values = parse_tabs(content)
        tabs = None
        if tab_values:
            tabs = [
                {"term": term, "items": resource_items(body)}
                for term, body in tab_values
            ]
        add_resource_group(result, title, resource_items(content) if not tabs else [], tabs)
    return result


def ordered_resources(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result[key]
        for key in ("links", "exams", "sections")
        if key in result
    }


def parse_resources(value: str) -> dict[str, Any]:
    heading_result = parse_heading_resources(value)
    if heading_result is not None:
        return ordered_resources(heading_result)

    parsed = parse_markdown_list(normalize_resource_list(value)) or []
    result: dict[str, Any] = {}
    direct_links = []
    for item in parsed:
        if isinstance(item, str):
            term_match = re.fullmatch(r"(?:回忆卷|历年卷)（(.+?)）", item)
            if term_match:
                result.setdefault("exams", []).append(
                    {"term": term_match.group(1), "items": []}
                )
            elif item in {"外链索引", "外联索引"}:
                result.setdefault("links", [])
            else:
                direct_links.append(parse_resource_link(item))
            continue
        title = item["text"]
        items = convert_resource_items(item.get("items", []))
        add_resource_group(result, title, items)
    if direct_links:
        result.setdefault("links", []).extend(direct_links)
    return ordered_resources(result)


def parse_grading(value: str) -> str | list[dict[str, Any]]:
    tabs = parse_tabs(value)
    if tabs is None:
        return value
    result = []
    for term, content in tabs:
        items = parse_markdown_list(content)
        entry: dict[str, Any] = {"term": term}
        if items is not None:
            entry["items"] = items
        else:
            entry["content"] = content
        result.append(entry)
    return result


def grading_term(value: str) -> str:
    tabs = parse_tabs(value)
    if not tabs:
        return "未注明学期"
    return re.split(r"[，,]", tabs[0][0], maxsplit=1)[0].strip()


def teacher_items(value: str) -> list[str]:
    items = []
    for line in value.splitlines():
        line = re.sub(r"^\s*-\s+", "", line).strip()
        if line:
            items.extend(part.strip() for part in line.split("/") if part.strip())
    return items or ["（暂未填充）"]


def parse_teachers(value: str, grading: str) -> list[dict[str, Any]]:
    tabs = parse_tabs(value)
    if tabs is None:
        return [{"term": grading_term(grading), "items": teacher_items(value)}]
    return [
        {"term": term, "items": teacher_items(content)} for term, content in tabs
    ]


def nav_titles(config: str) -> dict[str, str]:
    lines = config.splitlines()
    start, end = nav_bounds(lines)
    result = {}
    for line in lines[start + 1 : end]:
        item = parse_nav_item(line)
        if item and item[2]:
            result[item[2]] = item[1]
    return result


def parse_course(
    path: Path,
    docs_dir: Path,
    navigation: dict[str, str],
) -> dict[str, Any]:
    markdown = read_text(path, "课程 Markdown")
    if '<div class="course-tags">' not in markdown:
        raise BuildError(f"{path}: 不是课程页面")

    data = parse_front_matter(markdown, path)
    data.update(parse_tags(markdown))
    relative_page = path.resolve().relative_to(docs_dir.resolve()).as_posix()
    nav_title = navigation.get(relative_page)
    if nav_title and nav_title != data["title"]:
        data["nav_title"] = nav_title

    recommended, notes = parse_header_notes(markdown)
    if recommended:
        data["recommended_semester"] = recommended
    if notes:
        data["notes"] = notes

    sections = parse_sections(markdown)
    field_names = {
        "课程简介": "description",
        "教材信息": "textbooks",
    }
    for heading, field in field_names.items():
        if sections.get(heading):
            content = sections[heading]
            if field == "textbooks":
                data[field] = parse_markdown_list(content) or content
            else:
                data[field] = content

    resources = sections.get("相关资源", "")
    if resources:
        data["resources"] = parse_resources(resources)

    grading = sections.get("成绩构成", "")
    teachers = sections.get("任课教师", "")
    if teachers:
        data["teachers"] = parse_teachers(teachers, grading)
    if grading:
        data["grading"] = parse_grading(grading)

    expected = output_path(data, docs_dir)
    if expected.resolve() != path.resolve():
        data["output"] = str(Path(relative_page).with_suffix(""))
    return data


def find_inputs(paths: list[Path], docs_dir: Path) -> list[Path]:
    if paths:
        return paths
    return sorted(
        path
        for path in docs_dir.rglob("*.md")
        if "杂项" not in path.relative_to(docs_dir).parts
        and '<div class="course-tags">' in path.read_text(encoding="utf-8")
    )


def json_path(markdown: Path, docs_dir: Path, data_dir: Path) -> Path:
    relative = markdown.resolve().relative_to(docs_dir.resolve())
    return (data_dir / relative).with_suffix(".json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = find_inputs(args.inputs, args.docs_dir)
    if not inputs:
        raise BuildError("没有找到课程 Markdown")

    navigation = nav_titles(read_text(args.mkdocs_config, "MkDocs 配置"))
    jobs = []
    for source in inputs:
        try:
            data = parse_course(source, args.docs_dir, navigation)
            destination = json_path(source, args.docs_dir, args.data_dir)
        except (BuildError, ValueError) as exc:
            raise BuildError(f"{source}: {exc}") from exc
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        jobs.append((source, destination, content))

    if not (args.force or args.check):
        existing = [destination for _, destination, _ in jobs if destination.exists()]
        if existing:
            raise BuildError(f"目标已存在：{existing[0]}；确认后使用 --force 覆盖")

    for source, destination, content in jobs:
        if args.check:
            print(f"OK  {source} -> {destination}")
        else:
            atomic_write(destination, content)
            print(f"生成 {destination}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
