"""Site statistics exposed to mkdocs-macros-plugin."""

import os
import re

import yaml


# 将站点统计结果注入 MkDocs macros 的全局变量。
def register_site_stats(env):
    stats = collect_site_stats(project_dir(), env.conf.get('nav', []))
    env.variables['site_pages'] = stats['pages']
    env.variables['site_chinese_chars'] = stats['chinese_chars']


# 读取 MkDocs 配置中的导航。
def load_nav(root_dir):
    config_path = os.path.join(root_dir, 'mkdocs.yml')
    try:
        with open(config_path, 'r', encoding='utf-8') as fh:
            config = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError):
        return []
    return config.get('nav', [])


# 递归提取导航引用的 Markdown 路径，并按首次出现顺序去重。
def nav_markdown_paths(nav):
    paths = []

    def visit(item):
        if isinstance(item, str):
            path = item.split('#', 1)[0].split('?', 1)[0]
            if path.lower().endswith('.md') and path not in paths:
                paths.append(path)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            for child in item.values():
                visit(child)

    visit(nav)
    return paths


# 只统计 MkDocs 导航可以访问的 Markdown 页面和中文字符数。
def collect_site_stats(root_dir, nav=None):
    docs_dir = os.path.join(root_dir, 'docs')
    page_count = 0
    total_hanzi = 0

    if not os.path.isdir(docs_dir):
        return {'pages': 0, 'chinese_chars': 0}

    nav = load_nav(root_dir) if nav is None else nav
    docs_dir = os.path.abspath(docs_dir)
    for relative_path in nav_markdown_paths(nav):
        path = os.path.abspath(os.path.join(docs_dir, relative_path))
        try:
            if os.path.commonpath([docs_dir, path]) != docs_dir:
                continue
            with open(path, 'r', encoding='utf-8') as fh:
                text = fh.read()
        except (OSError, ValueError):
            continue
        page_count += 1
        total_hanzi += count_chinese_chars(strip_markdown_noise(text))

    return {'pages': page_count, 'chinese_chars': total_hanzi}


# 移除不应计入正文统计的 Markdown 结构。
def strip_markdown_noise(text):
    text = re.sub(r'^---[\s\S]*?---[\r\n]+', '', text, flags=re.M)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    return re.sub(r'\[.*?\]\(.*?\)', '', text)


# 统计文本中的中文汉字数量。
def count_chinese_chars(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))


# 返回项目根目录路径。
def project_dir():
    return os.path.dirname(os.path.dirname(__file__))
