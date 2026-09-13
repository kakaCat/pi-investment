#!/usr/bin/env python3
"""Wiki 巡检探针（reqboard 归档线的配套检查）。

按「wiki 方式」维护 docs/：页面是节点，页面之间有链接，页面有 front-matter（机器可索引）。
规范见 docs/DOCUMENT-MANAGEMENT-PLAN.md 的「Wiki 化：页面模型」一节。

分层报告（避免"全是历史问题 → 没人看"）：
  - **wiki 页**（有 front-matter）：死链 / 孤儿页 / 状态字段问题 → **计入失败**；
  - **待迁移页**（无 front-matter）：只计数并列出 → 不计失败（历史文档逐步迁）；
  - **待写页**（status: stub）：登记但不算失败——它们是后续需求的候选。

退出码：0 = wiki 页无问题；1 = 有问题（供定时任务与 CI 使用）。
用法：python3 agent-dh/scripts/wiki_probe.py [--root .] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

SKIP_DIRS = {'.git', 'node_modules', '.claude', 'dist', 'lib', '__pycache__', '.dsh-data', '.dsh-home'}
WIKI_ROOTS = ['docs', 'agent-dh/docs']
FRONT_MATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.S)
LINK_RE = re.compile(r'\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)')
REQUIRED_FM = ('id', 'title', 'type', 'status', 'updated')


def iter_pages(root: str):
    for wiki_root in WIKI_ROOTS:
        base = os.path.join(root, wiki_root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in sorted(filenames):
                if not name.endswith('.md'):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root)
                if '/work-logs/' in '/' + rel:
                    continue
                yield path, rel


def parse_front_matter(text: str) -> dict:
    m = FRONT_MATTER_RE.match(text)
    if m is None:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        out[k.strip()] = v.strip()
    return out


def local_links(text: str):
    for m in LINK_RE.finditer(text):
        target = m.group(1)
        if target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        yield target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    all_pages = list(iter_pages(root))
    wiki_pages = []
    legacy = []
    fm_of = {}
    for path, rel in all_pages:
        text = open(path, encoding='utf-8').read()
        fm = parse_front_matter(text)
        fm_of[rel] = fm
        (wiki_pages if fm else legacy).append((path, rel, text))

    wiki_ids = {rel for _p, rel, _t in wiki_pages}
    inbound = {rel: set() for rel in wiki_ids}
    dead, bad_fm, stubs = [], [], []
    for path, rel, text in wiki_pages:
        fm = fm_of[rel]
        if fm.get('status') == 'stub':
            stubs.append(rel)
        missing = [k for k in REQUIRED_FM if k not in fm]
        if missing:
            bad_fm.append({'page': rel, 'missing': missing})
        for target in local_links(text):
            candidate = os.path.normpath(
                os.path.join(root, target.lstrip('/')) if target.startswith('/')
                else os.path.join(os.path.dirname(path), target))
            if not os.path.exists(candidate):
                dead.append({'page': rel, 'target': target})
                continue
            tgt = os.path.relpath(candidate, root)
            if tgt in inbound and tgt != rel:
                inbound[tgt].add(rel)

    orphans = sorted(rel for rel, src in inbound.items() if not src and os.path.basename(rel) != 'README.md')
    problems = len(dead) + len(orphans) + len(bad_fm)

    report = {
        'wiki_pages': len(wiki_pages),
        'legacy_pages': len(legacy),
        'dead_links': dead,
        'orphans': orphans,
        'stubs': sorted(stubs),
        'front_matter_incomplete': bad_fm,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f'wiki 页 {len(wiki_pages)} 个 / 待迁移页 {len(legacy)} 个')
        if dead:
            print(f'死链 {len(dead)} 条（wiki 页内）：')
            for d in dead[:20]:
                print(f"  - {d['page']} -> {d['target']}")
        if orphans:
            print(f'孤儿页 {len(orphans)} 个（没有任何页面链到它）：')
            for o in orphans[:20]:
                print(f'  - {o}')
        if bad_fm:
            print(f'front-matter 缺字段 {len(bad_fm)} 个（需 {"/".join(REQUIRED_FM)}）：')
            for b in bad_fm[:20]:
                print(f"  - {b['page']} 缺 {','.join(b['missing'])}")
        if stubs:
            print(f'待写页（status: stub）{len(stubs)} 个：')
            for s in stubs[:20]:
                print(f'  - {s}')
        if problems == 0:
            print('OK：wiki 页无死链、无孤儿页、front-matter 完整')
        if legacy:
            print(f'提示：{len(legacy)} 个历史页面还没有 front-matter（迁到一个是一个，不计失败）')
    return 1 if problems > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
