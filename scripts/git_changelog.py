"""Git commit log changelog macro."""

import hashlib
import html
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request


# 头像尺寸（像素）、GitHub API 分页大小与请求超时（秒）。
AVATAR_SIZE = 64
GITHUB_API_PER_PAGE = 100
GITHUB_API_TIMEOUT = 5

# GitHub API 入口，测试时可替换为本地服务。
GITHUB_API_BASE = 'https://api.github.com'

# 可选的本地头像缓存文件名，内容为 {邮箱: 头像地址}，用于离线构建。
AVATAR_CACHE_FILE = 'avatar_cache.json'

# GitHub noreply 邮箱，形如 1234+login@users.noreply.github.com。
NOREPLY_PATTERN = re.compile(r'^(?:(\d+)\+)?([^@\s]+)@users\.noreply\.github\.com$', re.IGNORECASE)

# 首字母头像的配色，按邮箱哈希取色，深浅色主题下白色文字均可读。
AVATAR_COLORS = (
    '#1e88e5',
    '#00897b',
    '#8e24aa',
    '#e53935',
    '#fb8c00',
    '#3949ab',
    '#00838f',
    '#6d4c41',
)

# 构建期间复用远程头像查询结果，避免 mkdocs serve 反复请求 GitHub。
REMOTE_AVATAR_CACHE = {}


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

    output = read_git_log(repo_dir, limit)
    if output is None:
        return '> 暂时无法读取 Git 提交历史。请确认构建环境包含 `.git` 目录，并且安装了 Git。'

    commits = parse_git_log(output)
    if not commits:
        return '> 暂时没有可展示的 Git 提交记录。'

    repo_url = repo_url_from_env(env)
    avatars = build_avatar_index(commits, repo_url, repo_dir, limit)
    return render_changelog(commits, repo_url, avatars)


# 执行 git log 读取提交记录，失败时返回 None。
def read_git_log(repo_dir, limit):
    try:
        return subprocess.check_output(
            [
                'git',
                '-C',
                repo_dir,
                'log',
                f'--max-count={limit}',
                '--date=short',
                '--pretty=format:%H%x09%h%x09%ad%x09%an%x09%ae%x09%s',
            ],
            text=True,
            encoding='utf-8',
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


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
        parts = line.split('\t', 5)
        if len(parts) != 6:
            continue
        full_hash, short_hash, date, author, email, subject = parts
        commits.append(
            {
                'full_hash': full_hash,
                'short_hash': short_hash,
                'date': date,
                'author': author.strip(),
                'email': email.strip(),
                'subject': clean_commit_subject(subject),
            }
        )
    return commits


# 按年份和日期分组渲染提交记录。
def render_changelog(commits, repo_url='', avatars=None):
    avatars = avatars or {}
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

        avatar = render_avatar(commit, avatars)
        lines.append(f'    - {avatar} {commit_ref} {markdown_escape(commit["subject"])}')

    return '\n'.join(lines)


# 为每个提交作者解析头像地址，返回 {邮箱: 头像地址} 索引。
def build_avatar_index(commits, repo_url, repo_dir, limit):
    cache = load_avatar_cache()
    index = {}
    pending = {}

    for commit in commits:
        key = avatar_key(commit)
        if key in index or key in pending:
            continue
        url = cache.get(key) or noreply_avatar_url(commit['email'])
        if url:
            index[key] = url
        else:
            pending[key] = commit

    if pending:
        remote = fetch_github_avatars(repo_url, repo_dir, limit)
        for key, commit in pending.items():
            url = remote.get(key) or remote.get(commit['full_hash'])
            if url:
                index[key] = url

    return index


# 读取可选的本地头像缓存文件，缺失或损坏时返回空索引。
def load_avatar_cache():
    path = os.path.join(project_dir(), 'scripts', AVATAR_CACHE_FILE)
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(cache, dict):
        return {}
    return {
        str(email).strip().lower(): str(url)
        for email, url in cache.items()
        if str(url).strip()
    }


# 从 GitHub noreply 邮箱直接推导头像地址，无需网络请求。
def noreply_avatar_url(email):
    match = NOREPLY_PATTERN.match((email or '').strip())
    if not match:
        return ''
    number, login = match.groups()
    if number:
        return f'https://avatars.githubusercontent.com/u/{number}?s={AVATAR_SIZE}&v=4'
    return f'https://github.com/{urllib.parse.quote(login, safe="")}.png?size={AVATAR_SIZE}'


# 通过 GitHub API 查询提交作者头像，失败时静默返回空索引。
def fetch_github_avatars(repo_url, repo_dir, limit):
    owner_repo = github_owner_repo(repo_url)
    if not owner_repo or offline_mode():
        return {}

    pages = max(1, (limit + GITHUB_API_PER_PAGE - 1) // GITHUB_API_PER_PAGE)
    # 先按当前 HEAD 查询；本地未推送的提交查不到时退回默认分支。
    for ref in (head_commit(repo_dir), ''):
        avatars = github_avatars_for_ref(owner_repo, ref, pages)
        if avatars:
            return avatars
    return {}


# 带进程内缓存的单次 GitHub 头像查询。
def github_avatars_for_ref(owner_repo, ref, pages):
    cache_key = (owner_repo, ref)
    if cache_key in REMOTE_AVATAR_CACHE:
        return REMOTE_AVATAR_CACHE[cache_key]
    avatars = index_github_commits(fetch_github_commits(owner_repo, ref, pages))
    REMOTE_AVATAR_CACHE[cache_key] = avatars
    return avatars


# 分页拉取 GitHub commits API，任一页请求失败都返回空表。
def fetch_github_commits(owner_repo, ref, pages):
    items = []
    for page in range(1, pages + 1):
        page_items = request_github_commits(owner_repo, ref, page)
        if page_items is None:
            return []
        items.extend(page_items)
        if len(page_items) < GITHUB_API_PER_PAGE:
            break
    return items


# 请求单页 commits API，返回 None 表示请求失败。
def request_github_commits(owner_repo, ref, page):
    query = f'per_page={GITHUB_API_PER_PAGE}&page={page}'
    if ref:
        query = f'sha={urllib.parse.quote(ref, safe="")}&{query}'
    request = urllib.request.Request(
        f'{GITHUB_API_BASE}/repos/{owner_repo}/commits?{query}',
        headers=github_api_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_API_TIMEOUT) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return payload if isinstance(payload, list) else []


# 构造 GitHub API 请求头，存在令牌时使用以放宽速率限制。
def github_api_headers():
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'ISYS-changelog',
    }
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


# 将 commits API 结果整理为 {提交哈希/作者邮箱: 头像地址} 索引。
def index_github_commits(items):
    avatars = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        author = item.get('author') if isinstance(item.get('author'), dict) else {}
        avatar_url = str(author.get('avatar_url') or '')
        if not avatar_url:
            continue
        sha = str(item.get('sha') or '')
        if sha:
            avatars[sha] = avatar_url
        commit = item.get('commit') if isinstance(item.get('commit'), dict) else {}
        person = commit.get('author') if isinstance(commit.get('author'), dict) else {}
        email = str(person.get('email') or '').strip().lower()
        if email:
            avatars.setdefault(email, avatar_url)
    return avatars


# 通过环境变量关闭构建期的远程头像查询。
def offline_mode():
    value = os.environ.get('ISYS_CHANGELOG_OFFLINE', '').strip().lower()
    return value not in ('', '0', 'false', 'no')


# 从仓库地址解析 owner/repo，非 GitHub 地址返回空串。
def github_owner_repo(repo_url):
    match = re.match(r'https?://github\.com/([^/]+)/([^/#?]+)', (repo_url or '').strip(), re.IGNORECASE)
    if not match:
        return ''
    owner, repo = match.group(1), match.group(2)
    if repo.endswith('.git'):
        repo = repo[:-4]
    return f'{owner}/{repo}'


# 读取当前 HEAD 的提交哈希，失败时返回空串。
def head_commit(repo_dir):
    try:
        return subprocess.check_output(
            ['git', '-C', repo_dir, 'rev-parse', 'HEAD'],
            text=True,
            encoding='utf-8',
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ''


# 头像索引的键：提交邮箱，缺失时退回到作者名。
def avatar_key(commit):
    return (commit['email'] or commit['author']).strip().lower()


# 渲染提交作者头像，没有可用头像地址时退回首字母头像。
def render_avatar(commit, avatars):
    author = commit['author'] or commit['email'] or '匿名'
    label = html.escape(author, quote=True)
    url = avatars.get(avatar_key(commit), '')
    if url:
        return (
            f'<img class="changelog-avatar" src="{html.escape(url, quote=True)}"'
            f' alt="{label}" title="{label}" width="20" height="20" loading="lazy">'
        )
    return (
        '<span class="changelog-avatar changelog-avatar-letter"'
        f' style="background-color: {avatar_color(avatar_key(commit))}" title="{label}">'
        f'{html.escape(avatar_initial(author))}</span>'
    )


# 取作者名首字母，中文取第一个字，英文取前两个词的首字母。
def avatar_initial(name):
    name = (name or '').strip()
    if not name:
        return '?'
    if name.isascii():
        words = [part for part in re.split(r'[\s._\-]+', name) if part]
        return (''.join(word[0] for word in words[:2]) or name[0]).upper()
    return name[0]


# 按邮箱哈希取一个稳定的头像底色。
def avatar_color(key):
    digest = hashlib.md5(key.encode('utf-8')).hexdigest()
    return AVATAR_COLORS[int(digest[:8], 16) % len(AVATAR_COLORS)]


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
