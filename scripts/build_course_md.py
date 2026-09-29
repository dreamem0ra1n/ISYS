#!/usr/bin/env python3
"""Build course Markdown pages from JSON data and content/template.md.

Run ``python scripts/build_course_md.py --help`` for command-line usage.  A
complete input example lives in ``scripts/course_data.example.json``.

Only ``title`` is required. Header fields and content sections that are not
present in JSON are omitted. Each JSON file describes exactly one course.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_DIR / "data"
DEFAULT_DOCS_DIR = PROJECT_DIR / "content"
DEFAULT_TEMPLATE = DEFAULT_DOCS_DIR / "template.md"

CATEGORY_INFO = {
    "专业基础": ("basic", "专业基础", "专业基础"),
    "专业必修": ("required", "专业必修", "专业必修"),
    "专业进阶": ("advanced", "专业进阶", "专业进阶"),
    "实践教学": ("practice", "实践教学", "实践教学"),
    "专业选修-应用基础": (
        "elective-basic",
        "专业选修-应用基础",
        "专业选修/应用基础类",
    ),
    "专业选修-实践拓展": (
        "elective-practice",
        "专业选修-实践拓展",
        "专业选修/实践拓展类",
    ),
}

CATEGORY_ALIASES = {
    "应用基础": "专业选修-应用基础",
    "应用基础类": "专业选修-应用基础",
    "专业选修-应用基础类": "专业选修-应用基础",
    "实践拓展": "专业选修-实践拓展",
    "实践拓展类": "专业选修-实践拓展",
    "专业选修-实践拓展类": "专业选修-实践拓展",
}

LOCATION_CLASSES = {
    "紫金港": "location-zjg",
    "玉泉": "location-yq",
    "西溪": "location-xx",
    "华家池": "location-hjc",
    "海宁": "location-hn",
    "舟山": "location-zs",
    "之江": "location-zj",
}

SECTION_FIELDS = {
    "课程简介": "description",
    "任课教师": "teachers",
    "教材信息": "textbooks",
    "成绩构成": "grading",
    "相关资源": "resources",
}


class BuildError(ValueError):
    """An input or template error with a user-facing message."""

# 命令行参数解析
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据 JSON 数据和课程模板生成 Markdown 文档。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="JSON 文件；不指定时递归读取 data 目录中的所有 .json 文件",
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--content-dir", "--docs-dir", dest="docs_dir", type=Path, default=DEFAULT_DOCS_DIR
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="单篇文档的输出路径（只能与一门课程一起使用）",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="将单篇生成结果输出到标准输出，不写文件",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验输入并显示目标路径，不写文件",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已经存在的 Markdown 文件",
    )
    parser.add_argument(
        "--print-example",
        action="store_true",
        help="输出示例 JSON 后退出",
    )
    return parser.parse_args(argv)

# 读取 JSON 文件并返回字典
def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except OSError as exc:
        raise BuildError(f"无法读取 {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BuildError(
            f"{path}:{exc.lineno}:{exc.colno}: JSON 格式错误：{exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise BuildError(f"{path}: 顶层必须是单个课程对象")
    if "courses" in payload or "defaults" in payload:
        raise BuildError(f"{path}: 每个 JSON 文件只能直接描述一门课程")
    return payload

# 读取模板文件并检查必要的占位符
def read_template(path: Path) -> str:
    try:
        template = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BuildError(f"无法读取模板 {path}: {exc}") from exc

    missing = [name for name in SECTION_FIELDS if f"### {name}" not in template]
    if missing:
        raise BuildError(f"模板缺少三级标题：{', '.join(missing)}")
    if "title:" not in template or '<div class="course-tags">' not in template:
        raise BuildError("模板缺少课程 front matter 或 course-tags 区块")
    return template

# 将标量值转换为字符串并去除首尾空白，确保是字符串或数字
def scalar(value: Any, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise BuildError(f"{field} 必须是字符串或数字")
    return str(value).strip()

# 返回标量值或 None，如果字段不存在或为空
def optional_scalar(data: dict[str, Any], field: str) -> str | None:
    if field not in data or data[field] is None or data[field] == "":
        return None
    value = scalar(data[field], field)
    return value or None

# 将 category 字段解析为 CSS 类、标签和路径，支持字符串别名和自定义对象
def category_details(value: Any) -> tuple[str, str, str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        name = CATEGORY_ALIASES.get(value.strip(), value.strip())
        if name not in CATEGORY_INFO:
            choices = "、".join(CATEGORY_INFO)
            raise BuildError(f"未知 category {value!r}；可选值：{choices}")
        return CATEGORY_INFO[name]
    if isinstance(value, dict):
        try:
            css_class = scalar(value["class"], "category.class")
            label = scalar(value["label"], "category.label")
        except KeyError as exc:
            raise BuildError("自定义 category 必须包含 class 和 label") from exc
        path = scalar(value.get("path", label), "category.path")
        return css_class.removeprefix("tag-"), label, path
    raise BuildError("category 必须是字符串或对象")

# 解析 location 字段为 CSS 类和标签
def location_details(value: Any) -> tuple[str, str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        label = value.strip()
        css_class = LOCATION_CLASSES.get(label)
        if not css_class:
            raise BuildError(
                f"未知 location {value!r}；请改用包含 class 和 label 的对象"
            )
        return css_class, label
    if isinstance(value, dict):
        try:
            css_class = scalar(value["class"], "location.class")
            label = scalar(value["label"], "location.label")
        except KeyError as exc:
            raise BuildError("自定义 location 必须包含 class 和 label") from exc
        return css_class.removeprefix("tag-"), label
    raise BuildError("location 必须是字符串或对象")

# 将字符串值转换为 YAML 字符串，使用 JSON 转义规则
def yaml_value(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)

# 渲染模板头部
def render_template_header(template: str, data: dict[str, Any]) -> str:
    prefix = template.split("### ", 1)[0].rstrip()
    title = optional_scalar(data, "title")
    if not title:
        raise BuildError("缺少必填字段 title")

    comments = data.get("comments", True)
    if not isinstance(comments, bool):
        raise BuildError("comments 必须是 true 或 false")
    en_title = optional_scalar(data, "en_title")
    category = category_details(data.get("category"))
    location = location_details(data.get("location"))
    credits = optional_scalar(data, "credits")
    number = optional_scalar(data, "course_number")
    semester = optional_scalar(data, "recommended_semester")

    output = []
    generic_tag_slot = 0
    prefix_lines = prefix.splitlines()
    index = 0
    while index < len(prefix_lines):
        line = prefix_lines[index]
        stripped = line.strip()
        if re.match(r"^comments\s*:", stripped):
            replacement = f"comments: {str(comments).lower()}"
            output.append(re.sub(r"comments\s*:.*", replacement, line))
        elif re.match(r"^title\s*:", stripped):
            output.append(re.sub(r"title\s*:.*", f"title: {yaml_value(title)}", line))
        elif re.match(r"^en_title\s*:", stripped):
            if en_title:
                replacement = f"en_title: {yaml_value(en_title)}"
                output.append(re.sub(r"en_title\s*:.*", replacement, line))
        elif '<span class="tag tag-credit">' in line:
            if credits:
                label = credits if credits.endswith("学分") else f"{credits}学分"
                output.append(render_tag_line(line, "credit", label))
        elif '<span class="tag tag-number">' in line:
            if number:
                output.append(render_tag_line(line, "number", number))
        elif "tag-【location-" in line:
            if location:
                output.append(render_tag_line(line, location[0], location[1]))
        elif "tag-【" in line:
            details = category if generic_tag_slot == 0 else location
            generic_tag_slot += 1
            if details:
                output.append(render_tag_line(line, details[0], details[1]))
        elif stripped.startswith("> [!note] 培养方案推荐修读学期"):
            if semester:
                output.append(f"> [!note] 培养方案推荐修读学期：**{semester}**")
        else:
            output.append(line)
        if (
            stripped.startswith("> [!note] 培养方案推荐修读学期")
            and index + 1 < len(prefix_lines)
            and prefix_lines[index + 1].strip() == ">"
        ):
            index += 1
        index += 1

    header = "\n".join(output).rstrip()
    if "【" in header or "】" in header:
        raise BuildError("模板头部含有无法识别的【占位符】")
    return header

# 渲染标签行
def render_tag_line(template_line: str, css_class: str, label: str) -> str:
    indent = template_line[: len(template_line) - len(template_line.lstrip())]
    return (
        f'{indent}<span class="tag tag-{html.escape(css_class, quote=True)}">'
        f"{html.escape(label)}</span>"
    )

# 渲染 admonition 块
def render_notes(value: Any) -> str:
    if value is None or value == "" or value == []:
        return ""
    notes = value if isinstance(value, list) else [value]
    rendered = []
    for index, note in enumerate(notes):
        if isinstance(note, str):
            rendered.append(f"> [!note] {note.replace(chr(34), '')}")
            continue
        if not isinstance(note, dict) or not note.get("title"):
            raise BuildError(f"notes[{index}] 必须是字符串或含 title 的对象")
        admonition_type = note.get("type", "note")
        if not isinstance(admonition_type, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]*", admonition_type
        ):
            raise BuildError(f"notes[{index}].type 格式无效")
        title = scalar(note["title"], f"notes[{index}].title")
        title = title.replace('"', '&quot;')
        block = [f"> [!{admonition_type}] {title}"]
        content = note.get("content")
        if content:
            block.extend(
                f"> {line}" if line else ">"
                for line in scalar(content, f"notes[{index}].content").splitlines()
            )
        rendered.append("\n".join(block))
    return "\n\n".join(rendered)

# 渲染 Markdown 链接
def render_markdown_link(item: dict[str, Any], field: str) -> str:
    text_value = item.get("title", item.get("text"))
    if text_value is None:
        raise BuildError(f"{field} 缺少 title 或 text")
    text = scalar(text_value, f"{field}.title")
    url = optional_scalar(item, "url")
    if url:
        escaped_text = text.replace("[", r"\[").replace("]", r"\]")
        result = f"[{escaped_text}]({url.replace(' ', '%20')})"
    else:
        result = text
    description = optional_scalar(item, "description")
    if description:
        result += description if description.startswith("（") else f"（{description}）"
    return result

# 渲染列表项，支持嵌套
def render_list(items: Any, field: str, indent: int = 0) -> list[str]:
    if not isinstance(items, list):
        raise BuildError(f"{field} 必须是数组")
    lines = []
    for index, item in enumerate(items):
        item_field = f"{field}[{index}]"
        children = None
        if isinstance(item, (str, int, float)) and not isinstance(item, bool):
            text = str(item).strip()
        elif isinstance(item, dict):
            text = render_markdown_link(item, item_field)
            children = item.get("items", item.get("children"))
        else:
            raise BuildError(f"{item_field} 必须是文本或对象")
        if not text:
            raise BuildError(f"{item_field} 不能为空")
        lines.append(f"{' ' * indent}- {text}")
        if children is not None:
            lines.extend(render_list(children, f"{item_field}.items", indent + 4))
    return lines

# 缩进文本块
def indent_block(text: str, spaces: int = 4) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else "" for line in text.splitlines())

# 渲染选项卡内容(26春夏/25春夏)
def render_tab(tab: Any, field: str) -> str:
    if not isinstance(tab, dict):
        raise BuildError(f"{field} 必须是对象")
    label_value = tab.get("term", tab.get("title"))
    if label_value is None:
        raise BuildError(f"{field} 缺少 term 或 title")
    label = scalar(label_value, f"{field}.term").replace('"', '&quot;')
    if "content" in tab and tab["content"] not in (None, ""):
        content = scalar(tab["content"], f"{field}.content")
    elif "items" in tab:
        content = "\n".join(render_list(tab["items"], f"{field}.items"))
    else:
        raise BuildError(f"{field} 需要 content 或 items")
    return f'=== "{label}"\n{indent_block(content)}'

# 渲染按学期划分的教师信息
def render_teachers(value: Any) -> str:
    if not isinstance(value, list):
        raise BuildError("teachers 必须是学期对象数组")
    for index, term in enumerate(value):
        if not isinstance(term, dict) or "term" not in term or "items" not in term:
            raise BuildError(f"teachers[{index}] 必须包含 term 和 items")
    return "\n\n".join(
        render_tab(item, f"teachers[{index}]") for index, item in enumerate(value)
    )

# 渲染教材信息，支持字符串或数组
def render_textbooks(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return "\n".join(render_list(value, "textbooks"))

# 渲染成绩构成，支持字符串或学期对象数组
def render_grading(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        raise BuildError("grading 必须是 Markdown 文本或学期对象数组")
    return "\n\n".join(
        render_tab(item, f"grading[{index}]") for index, item in enumerate(value)
    )

# 渲染资源分组，支持对象，必须包含 title，且至少包含 content、items 或 tabs
def render_resource_group(group: Any, field: str) -> str:
    if not isinstance(group, dict) or not group.get("title"):
        raise BuildError(f"{field} 必须是含 title 的对象")
    title = scalar(group["title"], f"{field}.title")
    parts = [f"#### {title}"]
    if "content" in group and group["content"] not in (None, ""):
        parts.append(scalar(group["content"], f"{field}.content"))
    if "items" in group:
        parts.append("\n".join(render_list(group["items"], f"{field}.items")))
    tabs = group.get("tabs", group.get("terms"))
    if tabs is not None:
        if not isinstance(tabs, list):
            raise BuildError(f"{field}.tabs 必须是数组")
        parts.append(
            "\n\n".join(
                render_tab(tab, f"{field}.tabs[{index}]")
                for index, tab in enumerate(tabs)
            )
        )
    if len(parts) == 1:
        raise BuildError(f"{field} 需要 content、items 或 tabs")
    return "\n".join(part for part in parts if part)

# 渲染资源信息，支持 Markdown 文本、分组数组或对象，必须至少包含 links、exams 或 sections
def render_resources(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n\n".join(
            render_resource_group(group, f"resources[{index}]")
            for index, group in enumerate(value)
        )
    if not isinstance(value, dict):
        raise BuildError("resources 必须是 Markdown 文本、分组数组或对象")

    groups = []
    links = value.get("external_links", value.get("links"))
    if links:
        groups.append({"title": "外链索引", "items": links})
    exams = value.get("exams")
    if exams:
        groups.append({"title": "回忆卷", "tabs": exams})
    sections = value.get("sections", [])
    if not isinstance(sections, list):
        raise BuildError("resources.sections 必须是数组")
    groups.extend(sections)
    if not groups:
        raise BuildError("resources 对象至少需要 links、exams 或 sections")
    return "\n\n".join(
        render_resource_group(group, f"resources[{index}]")
        for index, group in enumerate(groups)
    )

# 渲染整门课程的 Markdown 内容，包含头部和各个内容区块
def render_course(data: dict[str, Any], template: str) -> str:
    header = render_template_header(template, data)
    notes = render_notes(data.get("notes"))
    if notes:
        header = f"{header}\n\n{notes}"

    renderers = {
        "description": lambda value: scalar(value, "description"),
        "teachers": render_teachers,
        "textbooks": render_textbooks,
        "grading": render_grading,
        "resources": render_resources,
    }
    sections = []
    for heading in re.findall(r"^### (.+?)\s*$", template, flags=re.MULTILINE):
        field = SECTION_FIELDS.get(heading)
        if not field or data.get(field) in (None, "", []):
            continue
        content = renderers[field](data[field]).strip()
        if content:
            sections.append(f"### {heading}\n{content}")

    return "\n\n".join([header, *sections]).rstrip() + "\n"

# 检查路径是否为 content 目录内的相对路径，防止目录遍历攻击
def safe_relative_path(value: str, field: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise BuildError(f"{field} 必须是 content 目录内的相对路径")
    return path

# 根据 JSON 数据和内容目录计算输出 Markdown 文件的路径，优先使用 output 字段，否则根据 title 和 category 生成路径
def output_path(data: dict[str, Any], docs_dir: Path) -> Path:
    explicit = optional_scalar(data, "output")
    if explicit:
        relative = safe_relative_path(explicit, "output")
        return docs_dir / relative.with_suffix(".md")

    title = optional_scalar(data, "title")
    if not title:
        raise BuildError("缺少必填字段 title")
    if title in {".", ".."} or any(char in title for char in "/\\\0"):
        raise BuildError("title 不能包含路径分隔符")
    category = category_details(data.get("category"))
    return docs_dir / f"{title}.md"

# 原子性写入文件
def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise

# 读取文本文件并返回内容，遇到错误时抛出 BuildError
def read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BuildError(f"无法读取 {label} {path}: {exc}") from exc

# 解析 YAML 标量值，支持单引号、双引号和注释
def parse_yaml_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return parsed if isinstance(parsed, str) else value
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value.split(" #", 1)[0].rstrip()

# 将输出路径转换为相对于 content 目录的路径，并检查是否在内容目录内，确保使用 .md 扩展名
def relative_docs_path(path: Path, docs_dir: Path) -> str:
    try:
        relative = path.resolve().relative_to(docs_dir.resolve())
    except ValueError as exc:
        raise BuildError(f"输出文件必须位于 content 目录内：{path}") from exc
    if relative.suffix.lower() != ".md":
        raise BuildError(f"课程页面必须使用 .md 扩展名：{path}")
    return relative.as_posix()

# 查找输入 JSON 文件，如果指定了路径则使用这些路径，否则递归查找 data 目录中的所有 .json 文件
def find_inputs(paths: list[Path]) -> list[Path]:
    if paths:
        return paths
    if not DEFAULT_DATA_DIR.is_dir():
        return []
    return sorted(
        path
        for path in DEFAULT_DATA_DIR.rglob("*.json")
        if path != DEFAULT_DATA_DIR / "友链.json"
    )

# 主函数，解析命令行参数，读取输入 JSON 文件和模板并生成 Markdown 文档。
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_example:
        example = Path(__file__).with_name("course_data.example.json")
        try:
            sys.stdout.write(example.read_text(encoding="utf-8"))
        except OSError as exc:
            raise BuildError(f"无法读取示例 {example}: {exc}") from exc
        return 0

    input_paths = find_inputs(args.inputs)
    if not input_paths:
        raise BuildError(
            "data 目录中没有 JSON 文件；可用 --print-example 查看数据格式"
        )
    template = read_template(args.template)

    jobs: list[tuple[Path, str, str]] = []
    for source in input_paths:
        course = read_json(source)
        try:
            destination = output_path(course, args.docs_dir)
            content = render_course(course, template)
        except BuildError as exc:
            raise BuildError(f"{source}: {exc}") from exc
        jobs.append((destination, content, str(source)))

    if (args.output or args.stdout) and len(jobs) != 1:
        raise BuildError("--output 和 --stdout 只能用于恰好一门课程")
    if args.output:
        jobs[0] = (args.output, jobs[0][1], jobs[0][2])

    seen: dict[Path, str] = {}
    for destination, _, source in jobs:
        resolved = destination.resolve()
        if resolved in seen:
            raise BuildError(f"{source} 与 {seen[resolved]} 的输出路径相同：{destination}")
        seen[resolved] = source

    if args.stdout:
        sys.stdout.write(jobs[0][1])
        return 0

    if not (args.force or args.check):
        for destination, _, _ in jobs:
            if not destination.exists():
                continue
            raise BuildError(f"目标已存在：{destination}；确认后使用 --force 覆盖")

    for destination, content, source in jobs:
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
