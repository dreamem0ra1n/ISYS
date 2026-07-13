"""Site statistics exposed to mkdocs-macros-plugin."""

import os
import re


# 将站点统计结果注入 MkDocs macros 的全局变量。
def register_site_stats(env):
    stats = collect_site_stats(project_dir())
    env.variables['site_pages'] = stats['pages']
    env.variables['site_chinese_chars'] = stats['chinese_chars']


# 遍历 docs 目录并统计 Markdown 页面数和中文字符数。
def collect_site_stats(root_dir):
    docs_dir = os.path.join(root_dir, 'docs')
    md_files = []
    total_hanzi = 0

    if not os.path.isdir(docs_dir):
        return {'pages': 0, 'chinese_chars': 0}

    for root, _, files in os.walk(docs_dir):
        for filename in files:
            if not filename.endswith('.md'):
                continue
            path = os.path.join(root, filename)
            md_files.append(path)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    text = fh.read()
            except OSError:
                continue
            total_hanzi += count_chinese_chars(strip_markdown_noise(text))

    return {'pages': len(md_files), 'chinese_chars': total_hanzi}


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
