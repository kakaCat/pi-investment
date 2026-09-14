
"""按行定位扫描器命中（复用 tools/non_orm_sql_scan.py 的口径，不另立标准）。

用法: ./venv/bin/python tools/non_orm_sql_lines.py <相对路径> [<相对路径> ...]
"""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import importlib.util

SCAN = pathlib.Path(__file__).resolve().parent / 'non_orm_sql_scan.py'
spec = importlib.util.spec_from_file_location('noss', SCAN)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ROOT = m.ROOT

def report(rel):
    p = ROOT / rel
    src = p.read_text(encoding='utf-8', errors='replace')
    raw = src.splitlines()
    skip, ok = m.docstring_lines(src)
    if not ok:
        print(f'{rel}: 无法解析'); return
    # 保留原始行号，逐行判定
    keep = [(i, l) for i, l in enumerate(raw, 1)
            if i not in skip and not l.lstrip().startswith('#')]
    joined = '\n'.join(l for _, l in keep)
    # 行号映射：joined 中第 n 行 -> keep[n-1][0]
    hits = {}
    for name in ('fstring_sql', 'core_text_sql', 'read_sql'):
        for mo in m.PATTERNS[name].finditer(joined):
            ln = joined[:mo.start()].count('\n')
            hits.setdefault(keep[ln][0], set()).add(name)
    # cursor_execute / session_execute_var：逐行用分类器（含跨行首参，取该行起 2 行窗口）
    for idx, (orig, line) in enumerate(keep):
        if not re.search(r'\.(execute|executemany)\(', line):
            continue
        window = '\n'.join(l for _, l in keep[idx:idx + 3])
        nc, nv = m.classify_execute_calls(window)
        if nc:
            hits.setdefault(orig, set()).add('cursor_execute')
        if nv:
            hits.setdefault(orig, set()).add('session_execute_var')
    vi = 0
    for orig, line in keep:
        if m.SQL_LINE_RX.search(line):
            k = len(m.QUOTED_INTERP_RX.findall(line))
            if k:
                hits.setdefault(orig, set()).add('fstring_value_interp')
                vi += k
    if not hits:
        print(f'{rel}: (无命中)'); return
    total = 0
    for ln in sorted(hits):
        names = sorted(n for n in hits[ln] if n != 'session_execute_var')
        if not names:
            continue
        total += len(names)
        print(f'{rel}:{ln}  {",".join(names)}')
        print(f'    {raw[ln-1].strip()[:110]}')
    print(f'{rel}: 本轮范围站点合计 {total}')

for rel in sys.argv[1:]:
    report(rel); print()
