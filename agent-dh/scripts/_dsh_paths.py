#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DSH 运行目录的**自定位**（供 scripts/ 下的会话诊断脚本共用）。

## 为什么有这个模块

2026-09-13 把 :13080 的 `DSH_HOME` 迁进项目内（`.dsh-home`）、数据迁进 `.dsh-data`
之后，多个诊断脚本仍硬编码 `~/.dsh-agent-dh/sessions`（旧 home）。旧 home 已于当日删除，
但这类硬编码的**失败模式**本身才值得记牢：

    它不会报错。它只是安静地去处理旧目录里那份**陈旧副本**，输出看着一切正常。

这与 `relink-profile.py` 那次「验错对象、却打印一句漂亮 OK」是同一个病：
**判定依据指向了错的目录，而没有任何迹象**。

所以这里统一从脚本自身位置反推，**不硬编码 home**：

    scripts/  ->  agent-dh/  ->  agent-dh/.dsh-data/sessions

可用 `DSH_DATA_DIR` 覆盖（与 start.sh / launchd 传的变量同名）。
"""
import os

# scripts/ -> agent-dh/
_HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_DH = os.path.dirname(_HERE)
REPO_ROOT = os.path.dirname(AGENT_DH)


def data_dir():
    """DSH 数据目录。优先 DSH_DATA_DIR 环境变量，否则项目内托管布局的 .dsh-data。"""
    env = os.environ.get("DSH_DATA_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(AGENT_DH, ".dsh-data")


def sessions_root(data=None):
    """会话文件根目录。"""
    return os.path.join(data or data_dir(), "sessions")


def store_dir_for_cwd(cwd=None):
    """DSH 按**进程 cwd** 给会话分 store 子目录，命名规则是：

        '-' + cwd.replace(os.sep, '-') + '--'

    例：/Users/yunpeng/pi-investment/agent-dh
        -> --Users-yunpeng-pi-investment-agent-dh--

    **默认取 AGENT_DH 而不是 REPO_ROOT**：DSH 实例的 cwd 是 `agent-dh/`（launchd 起
    进程时的 cwd，实测 `lsof -a -p <pid> -d cwd` = /Users/yunpeng/pi-investment/agent-dh），
    不是 git 仓库根。用 REPO_ROOT 会推出 `--Users-yunpeng-pi-investment--` 这种不存在的
    目录 —— 2026-09-13 初版就是这么写错的，靠下面的 require_dir 当场拦下。

    不要把这个名字抄成字面量：它跟着 cwd 走，抄下来就又是一处硬编码。
    """
    cwd = os.path.abspath(cwd or AGENT_DH)
    return "-" + cwd.replace(os.sep, "-") + "--"


def require_dir(path, what):
    """目录不存在时**显式失败**，而不是静默跳过。

    "根目录不存在 -> 什么都不处理 -> 打印 0 条" 正是上面说的那种安静错误：
    看起来像"检查过了没问题"，实际是根本没检查。
    """
    if not os.path.isdir(path):
        raise SystemExit(
            f"❌ {what} 不存在: {path}\n"
            f"   确认项目内托管布局（{AGENT_DH}/.dsh-data）是否就绪，"
            f"或用 DSH_DATA_DIR 显式指定数据目录。"
        )
    return path
