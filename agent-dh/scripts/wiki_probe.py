#!/usr/bin/env python3
"""Wiki 巡检探针（reqboard 归档线的配套检查）。

按「wiki 方式」维护 docs/：页面是节点，页面之间有链接，页面有 front-matter（机器可索引）。
规范见 docs/DOCUMENT-MANAGEMENT-PLAN.md 的「Wiki 化：页面模型」一节。

分层报告（避免"全是历史问题 → 没人看"）：
  - **wiki 页**（有 front-matter 的认知页）：死链 / 孤儿页 / front-matter 缺字段 /
    type-status 越界 → **计入失败**；
  - **档案页**（`work-logs/`）：**要求** front-matter；死链与孤儿只报告、**不计失败**
    （历史快照引用当时的路径，不回改）；
  - **待迁移页**（无 front-matter 的认知页）：只计数并列出 → 不计失败（历史文档逐步迁）；
  - **需求档案**（`requirements/REQ-*`、`_template/`）：**豁免** front-matter（由 INDEX.md 登记），
    单列提示；未被 `INDEX.md` 登记的 REQ 目录也在此提示。

退出码：0 = 无失败项；1 = 有失败项（供定时任务与 CI 使用）。
用法：python3 agent-dh/scripts/wiki_probe.py [--root .] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

SKIP_DIRS = {'.git', 'node_modules', '.claude', 'dist', 'lib', '__pycache__',
             '.dsh-data', '.dsh-home', 'worktrees', '.pnpm', '.deploy-backup',
             '.genome', 'output', '_archive', '.idea', '.pytest_cache'}

# 扫描根（相对 --root；从仓库根或从 agent-dh/ 运行都命中，不存在则跳过）
WIKI_ROOTS = ['docs', 'agent-dh/docs',
              'packages', 'agent-dh/packages',
              'examples', 'agent-dh/examples',
              'profiles', 'agent-dh/profiles']
EXTRA_FILES = ['README.md', 'agent-dh/README.md']

ARCHIVE_MARK = '/work-logs/'      # L3 工作日志：要 front-matter，死链/孤儿不计失败
REQUIREMENT_MARKS = ('/requirements/REQ-', '/requirements/_template/')  # L3 需求档案：豁免 front-matter

FRONT_MATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.S)
LINK_RE = re.compile(r'\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)')
REQUIRED_FM = ('id', 'title', 'type', 'status', 'updated')

TYPES = {'manual', 'architecture', 'guide', 'standard', 'protocol', 'adr', 'rfc',
         'design', 'research', 'package', 'profile', 'example', 'doc',
         'worklog', 'requirement', 'plan', 'verification', 'retro', 'troubleshooting',
         'index', 'template'}
STATUSES = {'living', 'stub', 'frozen', 'archived', 'superseded', 'legacy', 'template'}


def iter_pages(root: str):
    seen = set()
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
                if path in seen:
                    continue
                seen.add(path)
                yield path, os.path.relpath(path, root)
    for rel in EXTRA_FILES:
        path = os.path.join(root, rel)
        if os.path.isfile(path) and path not in seen:
            seen.add(path)
            yield path, os.path.relpath(path, root)


def parse_front_matter(text: str) -> dict:
    m = FRONT_MATTER_RE.match(text)
    if m is None:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ':' not in line or line.lstrip().startswith('#'):
            continue
        k, v = line.split(':', 1)
        out[k.strip()] = v.split('#')[0].strip()
    return out


def local_links(text: str):
    for m in LINK_RE.finditer(text):
        target = m.group(1)
        if target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        yield target


def is_archive(rel: str) -> bool:
    return ARCHIVE_MARK in '/' + rel


def is_requirement(rel: str) -> bool:
    return any(mark in '/' + rel for mark in REQUIREMENT_MARKS)


def find_requirement_dirs(root: str):
    """找出所有需求档案目录（相对 --root），用于 INDEX 登记检查。"""
    out = []
    for wiki_root in ('docs', 'agent-dh/docs'):
        base = os.path.join(root, wiki_root, 'requirements')
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if re.fullmatch(r'REQ-[0-9a-z]+', name) and os.path.isdir(os.path.join(base, name)):
                out.append(os.path.relpath(os.path.join(base, name), root))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    # 管辖范围：本探针只对 agent-dh 的文档树判失败。从仓库根运行时，其他项目/根 docs 的
    # 历史页只做提示（它们的文档体系不归 agent-dh 管，见 docs/DOCUMENT-MANAGEMENT-PLAN.md）。
    manage_all = not os.path.exists(os.path.join(root, 'agent-dh'))

    def managed(rel: str) -> bool:
        return manage_all or rel.startswith('agent-dh/')

    pages = list(iter_pages(root))
    wiki_pages, archive_pages, legacy, req_pages = [], [], [], []
    fm_of = {}
    for path, rel in pages:
        text = open(path, encoding='utf-8').read()
        fm = parse_front_matter(text)
        fm_of[rel] = fm
        # 目录的 README.md 是索引页（导航），即使落在 work-logs/ 下也按 wiki 页检查其链接
        arch = is_archive(rel) and os.path.basename(rel) != 'README.md'
        if is_requirement(rel):
            req_pages.append((path, rel, text))
        elif fm:
            (archive_pages if arch else wiki_pages).append((path, rel, text))
        else:
            (archive_pages if arch else legacy).append((path, rel, text))

    wiki_ids = {rel for _p, rel, _t in wiki_pages}
    archive_ids = {rel for _p, rel, _t in archive_pages}
    inbound = {rel: set() for rel in wiki_ids | archive_ids}
    dead, dead_archive, bad_fm, bad_enum, stubs = [], [], [], [], []
    bad_fm_other, bad_enum_other = [], []
    for group, is_arch in ((wiki_pages, False), (archive_pages, True)):
        for path, rel, text in group:
            fm = fm_of.get(rel, {})
            if fm.get('status') == 'stub':
                stubs.append(rel)
            missing = [k for k in REQUIRED_FM if k not in fm]
            if missing:
                (bad_fm if managed(rel) else bad_fm_other).append({'page': rel, 'missing': missing})
            if fm.get('type') and fm['type'] not in TYPES:
                (bad_enum if managed(rel) else bad_enum_other).append({'page': rel, 'field': 'type', 'value': fm['type']})
            if fm.get('status') and fm['status'] not in STATUSES:
                (bad_enum if managed(rel) else bad_enum_other).append({'page': rel, 'field': 'status', 'value': fm['status']})
            for target in local_links(text):
                candidate = os.path.normpath(
                    os.path.join(root, target.lstrip('/')) if target.startswith('/')
                    else os.path.join(os.path.dirname(path), target))
                if not os.path.exists(candidate):
                    if is_arch or not managed(rel):
                        dead_archive.append({'page': rel, 'target': target})
                    else:
                        dead.append({'page': rel, 'target': target})
                    continue
                tgt = os.path.relpath(candidate, root)
                if tgt in inbound and tgt != rel:
                    inbound[tgt].add(rel)

    # front-matter 缺失：档案页算失败（规范要求），认知页只计数
    archive_missing_fm = [rel for _p, rel, _t in archive_pages if not fm_of.get(rel) and managed(rel)]
    orphans = sorted(rel for rel, src in inbound.items()
                     if not src and os.path.basename(rel) != 'README.md'
                     and not is_archive(rel) and managed(rel))
    orphans_archive = sorted(rel for rel, src in inbound.items()
                             if not src and os.path.basename(rel) != 'README.md' and is_archive(rel))

    # 需求档案未登记进 INDEX.md（提示，不计失败——进行中的需求尚未归档）
    req_unlisted = []
    req_dirs = find_requirement_dirs(root)
    if req_dirs:
        index_text = ''
        for cand in (os.path.join(root, 'agent-dh/docs/requirements/INDEX.md'),
                     os.path.join(root, 'docs/requirements/INDEX.md')):
            if os.path.isfile(cand):
                index_text += open(cand, encoding='utf-8').read()
        for d in req_dirs:
            if os.path.basename(d) not in index_text:
                req_unlisted.append(d)

    problems = len(dead) + len(orphans) + len(bad_enum) + len(archive_missing_fm) + len(bad_fm)

    report = {
        'wiki_pages': len(wiki_pages),
        'archive_pages': len(archive_pages),
        'requirement_pages': len(req_pages),
        'legacy_pages': len(legacy),
        'dead_links': dead,
        'dead_links_archive': dead_archive,
        'orphans': orphans,
        'orphans_archive': orphans_archive,
        'stubs': sorted(stubs),
        'front_matter_incomplete': bad_fm,
        'bad_enum': bad_enum,
        'bad_fm_other_trees': bad_fm_other,
        'bad_enum_other_trees': bad_enum_other,
        'archive_missing_front_matter': archive_missing_fm,
        'requirements_unlisted': req_unlisted,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f'wiki 页 {len(wiki_pages)} / 档案页(work-logs) {len(archive_pages)} / '
              f'需求档案 {len(req_pages)} / 无 front-matter {len(legacy)}')
        if dead:
            print(f'死链 {len(dead)} 条（现行页）：')
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
        if archive_missing_fm:
            print(f'档案页缺 front-matter {len(archive_missing_fm)} 个（work-logs 要求 front-matter）：')
            for b in archive_missing_fm[:20]:
                print(f'  - {b}')
        if bad_enum:
            print(f'type/status 越界 {len(bad_enum)} 个（闭集见 DOCUMENT-MANAGEMENT-PLAN.md）：')
            for b in bad_enum[:20]:
                print(f"  - {b['page']} {b['field']}={b['value']}")
        if stubs:
            print(f'待写页（status: stub）{len(stubs)} 个：')
            for s in stubs[:20]:
                print(f'  - {s}')
        if dead_archive:
            print(f'（提示）档案页死链 {len(dead_archive)} 条——历史快照不回改，不计失败')
        if orphans_archive:
            print(f'（提示）档案页孤儿 {len(orphans_archive)} 个——应挂进 work-logs/README.md 索引')
        if req_unlisted:
            print(f'（提示）需求目录未登记进 INDEX.md {len(req_unlisted)} 个：')
            for r in req_unlisted[:20]:
                print(f'  - {r}')
        if legacy:
            print(f'（提示）{len(legacy)} 个历史页还没有 front-matter（迁一个是一个，不计失败）')
        if bad_fm_other:
            print(f'（提示）管辖范围外（其他项目/根 docs）front-matter 缺字段 {len(bad_fm_other)} 个——不归 agent-dh 管，只报告')
        if problems == 0:
            print('OK：现行页无死链、无孤儿、front-matter 与 type/status 全部合规')
    return 1 if problems > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
