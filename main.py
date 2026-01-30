# main.py — for mkdocs-macros-plugin
# define_env(env) will be called by mkdocs-macros-plugin at build time
# This collects: site_pages (number of .md pages) and site_chinese_chars (汉字数)

import os
import re

def define_env(env):
    docs_dir = os.path.join(os.path.dirname(__file__), 'docs')
    md_files = []
    total_hanzi = 0

    if not os.path.isdir(docs_dir):
        env.variables['site_pages'] = 0
        env.variables['site_chinese_chars'] = 0
        return

    for root, _, files in os.walk(docs_dir):
        for f in files:
            if not f.endswith('.md'):
                continue
            path = os.path.join(root, f)
            md_files.append(path)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    text = fh.read()
            except Exception:
                continue
            # remove YAML front matter
            text = re.sub(r'^---[\s\S]*?---[\r\n]+', '', text, flags=re.M)
            # remove fenced code blocks ```...```
            text = re.sub(r'```[\s\S]*?```', '', text)
            # remove inline code `...`
            text = re.sub(r'`[^`]*`', '', text)
            # remove images and links
            text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
            text = re.sub(r'\[.*?\]\(.*?\)', '', text)
            # count Chinese Han characters (basic range)
            hanzi = re.findall(r'[\u4e00-\u9fff]', text)
            total_hanzi += len(hanzi)

    env.variables['site_pages'] = len(md_files)
    env.variables['site_chinese_chars'] = total_hanzi
