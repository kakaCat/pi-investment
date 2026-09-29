#!/usr/bin/env python3
"""构建队列 DAG 卡片类型演示页（REQ-260928001915-f978）。

用法（工作区根目录或任意位置均可，脚本按自身位置定位路径）：

    python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py

做四件事：
  1. 读全仓 docs/requirements/*/queue.json，统计四轴频次、挑各类型标本、抽四档数据集
  2. 用 esbuild 把 demo/integration.ts 及其依赖打成一个 IIFE bundle（挂到 window.DagDemo）
  3. 跑一遍模块自测（demo/selftest.mjs，无浏览器）——不过就退出码 1
  4. 把数据 + bundle 注入 template.html，写出 demo/dag-card-types-demo.html

退出码：0 = 构建并自测通过；非 0 表示失败（失败要响亮，不静默降级）。
"""
import collections
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REQ_DIR = os.path.dirname(HERE)
REQUIREMENTS_DIR = os.path.dirname(REQ_DIR)
AGENT_DH_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
REPO_ROOT = os.path.dirname(AGENT_DH_ROOT)

TEMPLATE = os.path.join(HERE, 'template.html')
SELFTEST = os.path.join(HERE, 'selftest.mjs')
OUTPUT = os.path.join(HERE, 'dag-card-types-demo.html')
ENTRY = os.path.join(HERE, 'integration.ts')

# 演示数据集（顺序即按钮顺序）
# 四档真实队列（标签写明卡数/层数，与 README 的"小图 12 卡 / 中图 20 卡 / 压力 65 卡"一致）
DATASETS = [
    ('REQ-260928001915-f978', 'd0', '本需求 · 真实队列'),
    ('REQ-260922213356-4a45', 'd1', '小图 · 12 卡 7 层'),
    ('REQ-6f39b5', 'd2', '中图 · 20 卡 5 层'),
    ('REQ-260924213231-b1c4', 'd3', '压力 · 65 卡 12 层 83 边'),
]

STAGE_ORDER = ['dev', 'integrate', 'review', 'test']


def find_esbuild():
    """定位 esbuild（本仓 node_modules 里就有，避免依赖 PATH 或联网 npx）。"""
    candidates = [
        os.path.join(AGENT_DH_ROOT, 'node_modules', '.pnpm', 'node_modules', '.bin', 'esbuild'),
        os.path.join(AGENT_DH_ROOT, 'node_modules', '.bin', 'esbuild'),
        os.path.join(REPO_ROOT, 'node_modules', '.bin', 'esbuild'),
        shutil.which('esbuild'),
    ]
    for c in candidates:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    sys.stderr.write(
        '找不到 esbuild。请先在本仓安装依赖（agent-dh/node_modules 应已存在），\n'
        '或把 esbuild 加到 PATH 后重试。\n'
    )
    sys.exit(2)


def bundle(esbuild, fmt, global_name, outfile):
    cmd = [esbuild, ENTRY, '--bundle', '--target=es2020', '--format=' + fmt,
           '--outfile=' + outfile, '--log-level=warning']
    if global_name:
        cmd.insert(-1, '--global-name=' + global_name)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write('esbuild 打包失败：\n' + (proc.stderr or '') + '\n')
        sys.exit(3)
    if not os.path.exists(outfile) or os.path.getsize(outfile) == 0:
        sys.stderr.write('esbuild 退出码为 0 但产物为空：' + outfile + '\n')
        sys.exit(3)
    return outfile


def collect():
    """扫全仓队列文件，产出渲染所需的数据载荷。"""
    files = sorted(glob.glob(os.path.join(REQUIREMENTS_DIR, '*', 'queue.json')))

    freq = {'phase': collections.Counter(), 'side': collections.Counter(),
            'status': collections.Counter(), 'role': collections.Counter()}
    specimens = {}
    parents = {}
    all_tasks = {}
    ntasks = 0

    for f in files:
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        req = os.path.basename(os.path.dirname(f))
        kids_of = collections.defaultdict(list)
        for t in d.get('tasks', []):
            ntasks += 1
            all_tasks[t['id']] = (req, t)
            freq['phase'][t.get('phase')] += 1
            freq['side'][t.get('side')] += 1
            freq['status'][t.get('status')] += 1
            if t.get('parentId'):
                kids_of[t['parentId']].append(t)
            # 标本优先挑非 done 的真实卡：全挑 done 会让标本墙清一色绿底，看不出"类型 ≠ 状态"
            p = t.get('phase')
            cur = specimens.get(p)
            if cur is None or (cur['status'] == 'done' and t.get('status') != 'done'):
                specimens[p] = {'id': t['id'], 'title': t.get('title'), 'status': t.get('status'),
                                'side': t.get('side'), 'phase': p, 'req': req}
        for pid, kids in kids_of.items():
            parents[pid] = kids

    for _, (req, t) in all_tasks.items():
        if t.get('parentId'):
            freq['role']['child'] += 1
        elif t['id'] in parents:
            freq['role']['parent'] += 1
        else:
            freq['role']['solo'] += 1

    # 角色标本：优先挑一张正好 4 段子卡的父卡
    parent_id = None
    for pid, kids in parents.items():
        if len(kids) == 4:
            parent_id = pid
            break
    if parent_id is None and parents:
        parent_id = next(iter(parents))

    roles = None
    if parent_id is not None:
        prole, pt = all_tasks[parent_id]
        kids = sorted(parents[parent_id],
                      key=lambda k: STAGE_ORDER.index(k['stageKind'])
                      if k.get('stageKind') in STAGE_ORDER else 9)
        solo = None
        for _, (req, t) in all_tasks.items():
            if not t.get('parentId') and t['id'] not in parents:
                solo = (req, t)
                break
        if solo is None:
            solo = (prole, pt)
        child = kids[1] if len(kids) > 1 else kids[0]
        roles = {
            'parent': {'id': parent_id, 'title': pt.get('title'), 'status': pt.get('status'),
                       'phase': pt.get('phase'), 'side': pt.get('side'), 'req': prole},
            'child': {'id': child['id'], 'title': child.get('title'), 'status': child.get('status'),
                      'phase': child.get('phase'), 'side': child.get('side'),
                      'stageKind': child.get('stageKind'), 'req': prole},
            'solo': {'id': solo[1]['id'], 'title': solo[1].get('title'), 'status': solo[1]['status'],
                     'phase': solo[1].get('phase'), 'side': solo[1].get('side'), 'req': solo[0]},
            'kids': [{'id': k['id'], 'stageKind': k.get('stageKind'), 'status': k.get('status'),
                      'title': k.get('title')} for k in kids],
        }

    def trim(req, key, label, path):
        d = json.load(open(path, encoding='utf-8'))
        kids_of = collections.defaultdict(list)
        for t in d['tasks']:
            if t.get('parentId'):
                kids_of[t['parentId']].append(t)
        out = []
        for t in d['tasks']:
            o = {'id': t['id'], 'title': t.get('title'), 'status': t.get('status'),
                 'phase': t.get('phase'), 'side': t.get('side'), 'layer': t.get('layer', 0),
                 'dependsOn': t.get('dependsOn') or []}
            if t.get('parentId'):
                o['role'] = 'child'
                o['parentId'] = t['parentId']
                o['stageKind'] = t.get('stageKind')
            elif t['id'] in kids_of:
                o['role'] = 'parent'
                o['kids'] = [{'id': k['id'], 'stageKind': k.get('stageKind'), 'status': k.get('status'),
                              'title': k.get('title')} for k in sorted(
                    kids_of[t['id']],
                    key=lambda k: STAGE_ORDER.index(k['stageKind'])
                    if k.get('stageKind') in STAGE_ORDER else 9)]
            else:
                o['role'] = 'solo'
            out.append(o)
        return {'key': key, 'label': label, 'req': req, 'tasks': out,
                'edges': d.get('edges') or [], 'ready': d.get('ready') or [],
                'layerCount': len(d.get('layers') or [])}

    datasets = []
    for req, key, label in DATASETS:
        p = os.path.join(REQUIREMENTS_DIR, req, 'queue.json')
        if not os.path.exists(p):
            continue
        datasets.append(trim(req, key, label, p))

    if not datasets:
        sys.stderr.write('没有找到任何可用的队列文件（docs/requirements/*/queue.json）\n')
        sys.exit(4)

    meta = {'at': None, 'files': len(files), 'tasks': ntasks}
    return {'meta': meta, 'freq': {k: dict(v) for k, v in freq.items()},
            'specimens': specimens, 'roles': roles, 'datasets': datasets}


def run_selftest(node, cjs_bundle, datasets_payload):
    env = dict(os.environ)
    env['DAG_BUNDLE'] = cjs_bundle
    env['DAG_QUEUES'] = json.dumps([os.path.join(REQUIREMENTS_DIR, d[0], 'queue.json')
                                    for d in DATASETS])
    proc = subprocess.run([node, SELFTEST], capture_output=True, text=True, env=env)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or '')
        sys.stderr.write('模块自测未通过（退出码 %d）——已停止构建，未写出 HTML。\n' % proc.returncode)
        sys.exit(5)


def main():
    esbuild = find_esbuild()
    node = shutil.which('node')
    if not node:
        sys.stderr.write('找不到 node，无法运行模块自测。\n')
        sys.exit(2)

    payload = collect()

    with tempfile.TemporaryDirectory(prefix='dag-demo-') as tmp:
        iife = bundle(esbuild, 'iife', 'DagDemo', os.path.join(tmp, 'dag-bundle.js'))
        cjs = bundle(esbuild, 'cjs', None, os.path.join(tmp, 'dag-bundle.cjs'))
        run_selftest(node, cjs, payload['datasets'])
        with open(iife, encoding='utf-8') as fh:
            bundle_js = fh.read()

    payload['meta']['at'] = datetime.date.today().isoformat()

    tpl = open(TEMPLATE, encoding='utf-8').read()
    if '__DATA_JSON__' not in tpl or '/*__DAG_BUNDLE__*/' not in tpl:
        sys.stderr.write('template.html 缺少注入点（__DATA_JSON__ / /*__DAG_BUNDLE__*/）\n')
        sys.exit(6)
    out = tpl.replace('__DATA_JSON__', json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    out = out.replace('/*__DAG_BUNDLE__*/', bundle_js.replace('</script>', '<\\/script>'))
    with open(OUTPUT, 'w', encoding='utf-8') as fh:
        fh.write(out)

    print('写出 %s（%d 字节）' % (OUTPUT, len(out)))
    print('数据源队列文件 %d 份 / 任务 %d 张' % (payload['meta']['files'], payload['meta']['tasks']))
    print('phase 频次 %s' % dict(collections.Counter(payload['freq']['phase']).most_common()))
    print('role 频次 %s' % payload['freq']['role'])
    for d in payload['datasets']:
        print('数据集 %s · %s：%d 卡 / %d 边 / %d 层 / %d 可开工'
              % (d['key'], d['req'], len(d['tasks']), len(d['edges']), d['layerCount'], len(d['ready'])))


if __name__ == '__main__':
    main()
