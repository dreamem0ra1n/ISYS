"""Entry point for mkdocs-macros-plugin."""

import os
import sys

SCRIPTS_DIR = os.path.dirname(__file__)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from git_changelog import register_git_changelog
from site_stats import register_site_stats


# 注册 MkDocs macros 构建时需要的全部变量和宏。
def define_env(env):
    register_site_stats(env)
    register_git_changelog(env)
