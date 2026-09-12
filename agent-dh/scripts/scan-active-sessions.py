#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描会话文件，列出结构化异常事件（JSON 解析失败 / 缺 data.id / 缺 data.message.id）。

用法:
    python3 agent-dh/scripts/scan-active-sessions.py [session-id ...]

不给 session-id 时只扫描 store 目录下**最近修改的 5 个**会话（原脚本硬编码了两个
2026-09-11 的会话 ID，那两个会话已不在现役 store 里 —— 硬编码 ID 的脚本会随着
会话轮转而失效，故改为默认看最近的）。
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _dsh_paths as dp  # noqa: E402

ZSTD = '/Users/yunpeng/anaconda3/bin/zstd'
DEFAULT_RECENT = 5


def decompress(path):
    r = subprocess.run([ZSTD, '-d', '-c', '-f', path], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def recent_sessions(store, n):
    """store 下按 mtime 倒序取前 n 个会话目录名。"""
    entries = []
    for sid in os.listdir(store):
        f = os.path.join(store, sid, 'session.jsonl.zstd')
        if os.path.isfile(f):
            entries.append((os.path.getmtime(f), sid))
    entries.sort(reverse=True)
    return [sid for _, sid in entries[:n]]


def scan(path, sid):
    raw = decompress(path)
    if raw is None:
        print(f'=== {sid} ===')
        print(f'  无法解压: {path}')
        return
    lines = raw.split(b'\n')
    bad = []
    n_user = 0
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except Exception as e:
            bad.append((i, 'JSON_PARSE', '', str(e)[:60]))
            continue
        typ = ev.get('type', '')
        seq = ev.get('seq')
        data = ev.get('data') or {}
        if typ == 'user/message':
            n_user += 1
            if not data.get('id'):
                bad.append((i, 'user/message missing data.id', seq,
                            line.decode('utf-8', 'replace')[:200]))
        elif typ in ('assistant/message', 'tool/result'):
            if not (data.get('message') or {}).get('id'):
                bad.append((i, f'{typ} missing data.message.id', seq,
                            line.decode('utf-8', 'replace')[:200]))
    print(f'=== {sid} ===')
    print('  lines:', len(lines), ' user/message events:', n_user)
    print('  bad events:', len(bad))
    for ln, why, seq, head in bad:
        print(f'    line {ln} seq={seq} {why}')
        print(f'      {head}')


def main():
    root = dp.sessions_root()
    dp.require_dir(root, '会话根目录')
    store = os.path.join(root, dp.store_dir_for_cwd())
    dp.require_dir(store, f'store 目录（cwd={dp.REPO_ROOT}）')
    print(f'sessions root: {root}')
    print(f'store:         {store}')

    sids = sys.argv[1:] or recent_sessions(store, DEFAULT_RECENT)
    if not sids:
        raise SystemExit('❌ store 下没有任何会话文件。')
    for sid in sids:
        path = os.path.join(store, sid, 'session.jsonl.zstd')
        if not os.path.exists(path):
            print(f'=== {sid} ===\n  MISSING: {path}')
            continue
        scan(path, sid)


if __name__ == '__main__':
    main()
