#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复两个活跃会话文件中「缺 id 的 instruction-hint user/message 事件」。
仅允许在 :13080 服务停止时运行（用户手动重启窗口），否则拒绝执行（--force 可绕过）。

格式规范（与 DSH src/index.ts 一致）：
  - 文件 = 多个 zstd 帧拼接
  - 帧1 = header 行（meta JSON + '\n'）单独压缩（解码后必须恰好一行）
  - 后续帧 = 事件批次（事件 JSONL + '\n'）单独压缩
  - 文件末尾恰一个 '\n'，不允许空行（空行会被 scanner 判为 torn record）

修复规则：
  - type == 'user/message'    -> 缺 data.id 则补 'repair-<type>-<seq>-<time>'
  - type in ('assistant/message','tool/result') -> 缺 data.message.id 则补同格式 id
  - 其他事件不修改；已修复行用 json.dumps 重序列化，未修复行保持原字节
"""
import json, os, shutil, socket, subprocess, sys, time

ZSTD = '/Users/yunpeng/anaconda3/bin/zstd'
SESSIONS_ROOT = '/Users/yunpeng/.dsh-agent-dh/sessions'
STORE_DIR = '--Users-yunpeng-pi-investment-agent-dh--'
TARGETS = [
    'session-d8c936df-7d52-452e-b3ea-8d5eaf87d3df',
    'session-a1484624-d538-4e42-8a83-dd15c522bce5',
]
PORT = 13080
BACKUP_ROOT = f'/tmp/session-repair-active-backup-{int(time.time())}'


def server_running(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(('127.0.0.1', port))
            return True
        except OSError:
            return False


def decompress(path: str) -> bytes:
    r = subprocess.run([ZSTD, '-d', '-c', '-f', path], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f'decompress failed {path}: {r.stderr[:300]!r}')
    return r.stdout


def compress_single(data: bytes) -> bytes:
    r = subprocess.run([ZSTD, '-q', '-c'], input=data, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f'compress failed: {r.stderr[:300]!r}')
    return r.stdout


def needs_id(ev: dict) -> bool:
    t = ev.get('type')
    d = ev.get('data')
    if not isinstance(d, dict):
        return False
    if t == 'user/message':
        m = d
    elif t in ('assistant/message', 'tool/result'):
        m = d.get('message')
    else:
        return False
    if not isinstance(m, dict):
        return False
    return not (isinstance(m.get('id'), str) and m['id'])


def fix_event(ev: dict, fallback_ms: int) -> dict:
    t = ev.get('type', '?')
    seq = ev.get('seq', '?')
    ts = ev.get('time') or fallback_ms
    new_id = f'repair-{t}-{seq}-{ts}'
    d = ev['data']
    if t == 'user/message':
        d['id'] = new_id
    else:
        d['message']['id'] = new_id
    return ev


def repair_file(path: str, backup_root: str) -> dict:
    os.makedirs(backup_root, exist_ok=True)
    raw = decompress(path)
    lines = raw.split(b'\n')
    out_lines = []
    fixed = 0
    blank = 0
    fallback_ms = int(time.time() * 1000)
    for line in lines:
        if not line.strip():
            blank += 1
            continue
        try:
            ev = json.loads(line)
            if isinstance(ev, dict) and needs_id(ev):
                ev = fix_event(ev, fallback_ms)
                fixed += 1
                out_lines.append(json.dumps(ev, ensure_ascii=False).encode('utf-8'))
            else:
                out_lines.append(line)
        except (ValueError, UnicodeDecodeError):
            out_lines.append(line)
    new_raw = b'\n'.join(out_lines)
    if not new_raw.endswith(b'\n'):
        new_raw += b'\n'
    if not new_raw.strip():
        raise RuntimeError(f'empty content after repair: {path}')
    nl = new_raw.find(b'\n')
    header = new_raw[:nl + 1]
    events = new_raw[nl + 1:]
    hf = compress_single(header)
    ef = compress_single(events)
    check = decompress_to_memory_check(hf)
    if check != header:
        raise RuntimeError(f'header frame roundtrip mismatch: {path}')
    bak = os.path.join(backup_root, os.path.basename(os.path.dirname(path)) + '.zstd')
    shutil.copy2(path, bak)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(hf + ef)
    os.replace(tmp, path)
    return {'fixed': fixed, 'blank_removed': blank, 'lines': len(out_lines), 'backup': bak}


def decompress_to_memory_check(data: bytes) -> bytes:
    r = subprocess.run([ZSTD, '-d', '-c', '-f'], input=data, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f'roundtrip decompress failed: {r.stderr[:300]!r}')
    return r.stdout


def main():
    force = '--force' in sys.argv
    if server_running(PORT) and not force:
        print(f'ABORT: :{PORT} is RUNNING. 请先停止 DSH 服务（用户手动重启窗口）再运行本脚本；或用 --force 强制（不推荐）。')
        sys.exit(2)
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    print(f'backup root: {BACKUP_ROOT}')
    for sid in TARGETS:
        path = os.path.join(SESSIONS_ROOT, STORE_DIR, sid, 'session.jsonl.zstd')
        if not os.path.exists(path):
            print(f'MISSING: {path}')
            continue
        info = repair_file(path, BACKUP_ROOT)
        print(f'OK fixed={info["fixed"]} blanks_removed={info["blank_removed"]} lines={info["lines"]}')
        print(f'   {path}')
    print('DONE')


if __name__ == '__main__':
    main()
