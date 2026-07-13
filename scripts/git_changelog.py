"""Git commit log changelog macro."""

import os
import re
import subprocess


# 注册供 Markdown 页面调用的 git_changelog 宏。
def register_git_changelog(env):
    @env.macro
    # 生成指定数量的 Git 提交记录 Markdown。
    def git_changelog(limit=100):
        return build_git_changelog(env, limit)


# 读取 Git 提交历史并渲染为更新记录 Markdown。
def build_git_changelog(env, limit=100):
    repo_dir = project_dir()
    limit = normalize_limit(limit)

    try:
        output = subprocess.check_output(
            [
                'git',
                '-C',
                repo_dir,
                'log',
                f'--max-count={limit}',
                '--date=short',
                '--pretty=format:%H%x09%h%x09%ad%x09%s',
            ],
            text=True,
            encoding='utf-8',
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return '> 暂时无法读取 Git 提交历史。请确认构建环境包含 `.git` 目录，并且安装了 Git。'

    commits = parse_git_log(output)
    if not commits:
        return '> 暂时没有可展示的 Git 提交记录。'

    return render_changelog(commits, repo_url_from_env(env))


# 将用户传入的记录数量转换为有效正整数。
def normalize_limit(limit):
    try:
        return max(1, int(limit))
    except (TypeError, ValueError):
        return 120


# 将 git log 原始输出解析为结构化提交记录。
def parse_git_log(output):
    commits = []
    for line in output.splitlines():
        parts = line.split('\t', 3)
        if len(parts) != 4:
            continue
        full_hash, short_hash, date, subject = parts
        commits.append(
            {
                'full_hash': full_hash,
                'short_hash': short_hash,
                'date': date,
                'subject': clean_commit_subject(subject),
            }
        )
    return commits


# 按年份和日期分组渲染提交记录。
def render_changelog(commits, repo_url=''):
    lines = []
    current_year = ''
    current_date = ''

    for commit in commits:
        year = commit['date'][:4]
        month_day = commit['date'][5:]

        if year != current_year:
            if lines:
                lines.append('')
            lines.append(f'## {year}')
            current_year = year
            current_date = ''

        if month_day != current_date:
            lines.append('')
            lines.append(f'- {month_day}')
            current_date = month_day

        if repo_url:
            commit_url = f'{repo_url}/commit/{commit["full_hash"]}'
            commit_ref = f'[`{commit["short_hash"]}`]({commit_url})'
        else:
            commit_ref = f'`{commit["short_hash"]}`'

        lines.append(f'    - {commit_ref} {markdown_escape(commit["subject"])}')

    return '\n'.join(lines)


# 从 MkDocs 配置中读取仓库地址。
def repo_url_from_env(env):
    try:
        return env.conf.get('repo_url', '').rstrip('/')
    except AttributeError:
        return ''


# 清理提交标题中的日期前缀并规范 Conventional Commit 冒号格式。
def clean_commit_subject(subject):
    subject = subject.strip()
    subject = re.sub(r'^\d{8}[_\-\s]*', '', subject)
    subject = re.sub(r'^([A-Za-z]+):(?=\S)', r'\1: ', subject)
    return subject or '无提交说明'


# 转义提交标题中会影响 Markdown/HTML 渲染的字符。
def markdown_escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# 返回项目根目录路径。
def project_dir():
    return os.path.dirname(os.path.dirname(__file__))
