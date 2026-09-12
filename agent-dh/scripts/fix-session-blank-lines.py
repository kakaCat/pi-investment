#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除会话文件中的空行（空行会被 DSH scanner 判为 torn record）。

⚠️ 本脚本**会原地重写**会话文件（改前逐个备份到 /tmp）。默认第一个根目录就是
:13080 的**现役**数据目录，也就是说它现在直接作用于线上会话 —— 2026-09-13 之前它
指向的是旧 home `~/.dsh-agent-dh`（已在当日删除），跑起来会安静地处理那份陈旧副本。

用法:
    python3 agent-dh/scripts/fix-session-blank-lines.py           # 现役 store + 主实例 :3080
    python3 agent-dh/scripts/fix-session-blank-lines.py DIR ...   # 现役 store + 指定根（替代默认的 ~/.dsh）
    DSH_DATA_DIR=... python3 agent-dh/scripts/fix-session-blank-lines.py
"""
import glob
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _dsh_paths as dp  # noqa: E402

ZSTD = '/Users/yunpeng/anaconda3/bin/zstd'
BACKUP_ROOT = f'/tmp/session-blankline-backup-{int(time.time())}'


def decompress(path):
    r = subprocess.run([ZSTD, '-d', '-c', '-f', path], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:200])
    return r.stdout


def compress_single(data: bytes):
    r = subprocess.run([ZSTD, '-q', '-c'], input=data, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:200])
    return r.stdout


def main():
    os.makedirs(BACKUP_ROOT, exist_ok=True)

    # 现役数据目录（不存在则显式失败，不静默跳过）+ 主实例 :3080 的历史 store（可选）。
    # 给了位置参数就只扫这些额外根，不再默认带上 ~/.dsh/sessions —— 便于只针对某个
    # store 排查，避免顺手改动别的实例的会话。
    live = dp.sessions_root()
    dp.require_dir(live, '现役会话根目录')
    extra = sys.argv[1:] or [os.path.expanduser('~/.dsh/sessions')]
    roots = [(live, True)] + [(os.path.expanduser(p), False) for p in extra]

    targets = []
    for root, required in roots:
        if not os.path.isdir(root):
            # 可选根目录缺失要**说出来**：静默 continue 会让"没扫到"看起来像"没问题"
            print(f'⚠️  跳过不存在的根目录（{"必需" if required else "可选"}）: {root}')
            continue
        print(f'扫描: {root}')
        for p in sorted(glob.glob(root + '/**/session.jsonl.zstd', recursive=True)):
            raw = decompress(p)
            lines = raw.split(b'\n')
            blanks = [i + 1 for i, l in enumerate(lines) if not l.strip()]
            if blanks:
                targets.append((p, blanks))

    print('files with blank lines:', len(targets))
    fixed = []
    for p, blanks in targets:
        raw = decompress(p)
        lines = raw.split(b'\n')
        kept = [l for l in lines if l.strip()]
        new_raw = b'\n'.join(kept)
        if not new_raw.endswith(b'\n'):
            new_raw += b'\n'
        nl = new_raw.find(b'\n')
        header = new_raw[:nl + 1]
        events = new_raw[nl + 1:]
        hf = compress_single(header)
        ef = compress_single(events)
        bak = os.path.join(BACKUP_ROOT, os.path.basename(os.path.dirname(p)) + '.zstd')
        shutil.copy2(p, bak)
        with open(p + '.tmp', 'wb') as f:
            f.write(hf + ef)
        os.replace(p + '.tmp', p)
        fixed.append((p, len(blanks), len(kept)))

    print('fixed:', len(fixed))
    for p, nb, nk in fixed[:30]:
        print(f'  blanks={nb} lines={nk} {p}')
    print('backup:', BACKUP_ROOT)


if __name__ == '__main__':
    main()
