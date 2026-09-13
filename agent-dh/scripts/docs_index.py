#!/usr/bin/env python3
"""文档索引生成器（wiki 的机器可读入口）。

为什么需要它：front-matter 字段（type/status/summary/updated）如果没有消费者，就只是台账。
本脚本是消费者——把散在各页的 front-matter 汇成**一张表**，让 agent 一次读完就知道
「这个 wiki 有哪些页、每页讲什么、最近改了什么」，不必逐页打开。

产物（自动区都带 AUTO 标记，手改会被 --check 判为过期）：
  - docs/INDEX.md                     全站页面地图（页 | type | status | 一句话 | 更新）
  - docs/README.md 的「最近改动」区     按 fm.updated 倒序
  - docs/work-logs/README.md 的台账区   全部日志 + 提炼去向（distilled_into）

用法：
  python3 agent-dh/scripts/docs_index.py            # 生成 / 刷新
  python3 agent-dh/scripts/docs_index.py --check    # 只校验是否与文档一致（退出码 1 = 过期，供巡检/CI）
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys

SKIP_DIRS = {'.git', 'node_modules', '.claude', 'dist', 'lib', '__pycache__',
             '.dsh-data', '.dsh-home', 'worktrees', '.pnpm', '.deploy-backup',
             '.genome', 'output', '_archive', '.idea', '.pytest_cache'}
WIKI_ROOTS = ['docs', 'agent-dh/docs',
              'packages', 'agent-dh/packages',
              'examples', 'agent-dh/examples',
              'profiles', 'agent-dh/profiles']
EXTRA_FILES = ['README.md', 'agent-dh/README.md']

FRONT_MATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.S)
ANSWERS_RE = re.compile(r'\*\*这页回答\*\*[:：]\s*(.+)$', re.M)
BT = chr(96)

RECENT_BEGIN = '<!-- AUTO:recent BEGIN -->'
RECENT_END = '<!-- AUTO:recent END -->'
LEDGER_BEGIN = '<!-- AUTO:ledger BEGIN -->'
LEDGER_END = '<!-- AUTO:ledger END -->'

GROUP_TITLES = {
    'docs': '入口与发布说明',
    'docs/architecture': '架构与生命周期',
    'docs/standards': '技术要求规范（强制卷）',
    'docs/protocols': '工具与协议',
    'docs/guides': '指南（怎么做 / 怎么排障）',
    'docs/design': '设计与实施方案（历史）',
    'docs/rfcs': 'RFC 设计提案',
    'docs/examples': '示例',
    'packages': '包内入口页（怎么用这个包）',
    'examples': '示例目录',
    'profiles': 'Profile 与配置',
    'root': '仓库入口',
}


def parse_front_matter(text: str) -> dict:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ':' not in line or line.lstrip().startswith('#'):
            continue
        k, v = line.split(':', 1)
        out[k.strip()] = v.split(' #')[0].strip()
    return out


def clean(s: str, limit: int = 96) -> str:
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = s.replace('**', '').replace(BT, '').strip()
    s = re.sub(r'\s+', ' ', s)
    return s if len(s) <= limit else s[:limit - 1] + '…'


META_RE = re.compile(r'^(日期|最后更新|更新日期|发布日期|分析日期|执行日期|版本|作者|窗口|分支|状态|测试时间|日期时间)\\s*[:：]')
FENCE_RE = re.compile(r'^\s*'
                      + chr(96) * 3)


def derive_summary(text: str, fm: dict) -> str:
    if fm.get('summary'):
        return clean(fm['summary'])
    body = FRONT_MATTER_RE.sub('', text, count=1)
    m = ANSWERS_RE.search(body)
    if m:
        return clean(m.group(1))
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith('# '):
            continue
        in_fence = False
        for nxt in lines[i + 1:]:
            s = nxt.strip()
            if FENCE_RE.match(s):
                in_fence = not in_fence
                continue
            if in_fence or not s:
                continue
            if s.startswith(('#', '>', '|', '-', '*', '---', '![', '~')) or META_RE.match(s):
                continue
            if len(s) < 8:
                continue
            return clean(s)
        break
    return '—'


def iter_pages(root: str):
    seen = set()
    for wiki_root in WIKI_ROOTS:
        base = os.path.join(root, wiki_root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in sorted(filenames):
                if not name.endswith('.md') or name.startswith('_'):
                    continue
                path = os.path.join(dirpath, name)
                if path in seen:
                    continue
                seen.add(path)
                yield path, os.path.relpath(path, root)
    for rel in EXTRA_FILES:
        path = os.path.join(root, rel)
        if os.path.isfile(path) and path not in seen:
            seen.add(path)
            yield path, os.path.relpath(path, root)


def load(root: str):
    # 管辖范围与 wiki_probe 一致：从仓库根跑时只索引 agent-dh 的文档树
    # （其他项目/根 docs 的页面不归本索引管，否则同一份 INDEX.md 会有两种内容）
    manage_all = not os.path.isdir(os.path.join(root, 'agent-dh'))
    wiki, logs = [], []
    for path, rel in iter_pages(root):
        if not manage_all and not rel.startswith('agent-dh/'):
            continue
        text = open(path, encoding='utf-8').read()
        fm = parse_front_matter(text)
        item = {'rel': rel, 'path': path, 'fm': fm, 'summary': derive_summary(text, fm),
                'updated': fm.get('updated', ''), 'title': clean(fm.get('title', os.path.basename(rel)), 80)}
        if '/work-logs/' in '/' + rel and os.path.basename(rel) != 'README.md':
            logs.append(item)
        elif '/requirements/' in '/' + rel:
            continue
        else:
            wiki.append(item)
    return wiki, logs


def strip_project(rel: str) -> str:
    """统一成项目内路径（去掉仓库根运行时的 agent-dh/ 前缀）。"""
    return rel[len('agent-dh/'):] if rel.startswith('agent-dh/') else rel


def group_of(rel: str) -> str:
    sub = strip_project(rel).split('/')
    if len(sub) == 1:
        return 'root'
    if sub[0] == 'docs':
        if len(sub) > 2:
            key = 'docs/' + sub[1]
            return key if key in GROUP_TITLES else 'docs'
        return 'docs'
    return sub[0]


def doc_link(rel: str) -> str:
    """链接相对 docs/ 计算（INDEX.md 与 docs/README.md 都在 docs/ 下）。"""
    sub = strip_project(rel)
    if sub.startswith('docs/'):
        return sub[len('docs/'):]
    if sub == 'README.md':
        return '../README.md'
    return '../' + sub


def render_index(wiki, today: str) -> str:
    groups = {}
    for it in wiki:
        groups.setdefault(group_of(it['rel']), []).append(it)
    keys = [k for k in GROUP_TITLES if k in groups] + sorted(k for k in groups if k not in GROUP_TITLES)
    out = ['---',
           'id: docs-index',
           'title: 全站页面索引（机器可读入口）',
           'type: index',
           'status: living',
           'updated: ' + today,
           'owners: [agent-dh]',
           'tags: [index, wiki]',
           '---', '',
           '# 全站页面索引',
           '',
           '**这页回答**：这个 wiki 有哪些页、每页讲什么（一句话）——先读这张表，再决定打开哪页。',
           '',
           '> 本页由 ' + BT + 'python3 agent-dh/scripts/docs_index.py' + BT + ' 生成，**勿手改**；'
           '改了页面后跑一次生成，' + BT + '--check' + BT + ' 会校验是否过期。日志明细见 '
           '[工作日志索引](work-logs/README.md)，需求档案见 [需求档案索引](requirements/INDEX.md)。',
           '']
    for k in keys:
        items = sorted(groups[k], key=lambda x: x['rel'])
        out.append('### ' + GROUP_TITLES.get(k, k) + ' · ' + BT + k + BT + '（' + str(len(items)) + ' 页）')
        out.append('')
        out.append('| 页 | type | status | 一句话 | 更新 |')
        out.append('|---|---|---|---|---|')
        for it in items:
            out.append('| [' + it['title'] + '](' + doc_link(it['rel']) + ') | '
                       + it['fm'].get('type', '—') + ' | ' + it['fm'].get('status', '—')
                       + ' | ' + it['summary'] + ' | ' + (it['updated'] or '—') + ' |')
        out.append('')
    return '\n'.join(out)


def render_recent(wiki, limit: int = 15) -> str:
    items = sorted([i for i in wiki if i['updated']], key=lambda x: (x['updated'], x['rel']), reverse=True)[:limit]
    out = [RECENT_BEGIN,
           '| 日期 | 页面 | 一句话 |',
           '|---|---|---|']
    for it in items:
        out.append('| ' + it['updated'] + ' | [' + it['title'] + '](' + doc_link(it['rel']) + ') | '
                   + it['summary'] + ' |')
    out.append('')
    out.append('> 自动生成（' + BT + 'docs_index.py' + BT + '）：按 front-matter 的 updated 倒序取前 ' + str(limit) + ' 页。')
    out.append(RECENT_END)
    return '\n'.join(out)


def render_ledger(logs) -> str:
    out = [LEDGER_BEGIN,
           '合计 **' + str(len(logs)) + '** 篇。**提炼去向**（' + BT + 'distilled_into' + BT + '）为空的都在'
           '「待提炼队列」里——那才是要干的活，其余不必读。', '']
    by_month = {}
    for it in logs:
        m = re.search(r'work-logs/([0-9]{4}-[0-9]{2})/', '/' + it['rel'])
        by_month.setdefault(m.group(1) if m else '未归类', []).append(it)
    for month in sorted(by_month, reverse=True):
        items = sorted(by_month[month], key=lambda x: (x['updated'], x['rel']), reverse=True)
        out.append('### ' + month + '（' + str(len(items)) + ' 篇）')
        out.append('')
        out.append('| 日期 | 日志 | 提炼去向 |')
        out.append('|---|---|---|')
        for it in items:
            name = it['rel'].split('/')[-1]
            raw = strip_project(it['fm'].get('distilled_into', '').lstrip('./'))
            if raw:
                link = os.path.relpath(raw, 'docs/work-logs')
                dst = '✅ [' + os.path.basename(raw)[:-3] + '](' + link + ')'
            else:
                dst = '⏳ 待提炼'
            out.append('| ' + (it['updated'] or '—') + ' | [' + it['title'] + '](' + month + '/' + name + ') | ' + dst + ' |')
        out.append('')
    out.append(LEDGER_END)
    return '\n'.join(out)


def run(root: str, check: bool) -> int:
    today = datetime.date.today().isoformat()
    wiki, logs = load(root)
    # 从仓库根跑时文档在 agent-dh/ 下；从 agent-dh/ 内跑时 root 本身就是项目根
    ad = os.path.join(root, 'agent-dh') if os.path.isdir(os.path.join(root, 'agent-dh')) else root
    failures = []
    index_path = os.path.join(ad, 'docs/INDEX.md')
    body = render_index(wiki, today)
    current = open(index_path, encoding='utf-8').read() if os.path.isfile(index_path) else None
    if current != body:
        if check:
            failures.append(os.path.relpath(index_path, root))
        else:
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            open(index_path, 'w', encoding='utf-8').write(body)
            print('生成 ' + os.path.relpath(index_path, root))
    regions = [
        (os.path.join(ad, 'docs/README.md'), RECENT_BEGIN, RECENT_END, render_recent(wiki), '## 最近改动'),
        (os.path.join(ad, 'docs/work-logs/README.md'), LEDGER_BEGIN, LEDGER_END, render_ledger(logs), None),
    ]
    for path, begin, end, block, anchor in regions:
        text = open(path, encoding='utf-8').read() if os.path.isfile(path) else ''
        if begin in text and end in text:
            head, rest = text.split(begin, 1)
            _old, tail = rest.split(end, 1)
            new = head + block + tail
        elif anchor and anchor in text:
            head, tail = text.split(anchor, 1)
            new = head + anchor + '\n\n' + block + '\n' + tail
        else:
            new = text.rstrip('\n') + '\n\n' + block + '\n'
        if new != text:
            if check:
                failures.append(os.path.relpath(path, root) + '（自动区）')
            else:
                open(path, 'w', encoding='utf-8').write(new)
                print('刷新 ' + os.path.relpath(path, root) + ' 的自动区')
    if check:
        if failures:
            print('索引与文档不一致（跑一次 docs_index.py）：')
            for f in failures:
                print('  - ' + f)
            return 1
        print('OK：索引与文档一致')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    return run(os.path.abspath(args.root), args.check)


if __name__ == '__main__':
    sys.exit(main())
