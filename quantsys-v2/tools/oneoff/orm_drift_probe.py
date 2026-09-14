# -*- coding: utf-8 -*-
"""漂移探针 v2：按 (module, class) 去重，完整列出重复定义与漂移"""
import importlib, inspect, os, pkgutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import class_mapper
from infrastructure.persistence.orm.base import Base

DB_URL = os.environ.get("QUANT_DATABASE_URL", "postgresql+psycopg2://localhost/quant_investment")
engine = create_engine(DB_URL)

with engine.connect() as c:
    rows = c.execute(text(
        "SELECT table_schema, table_name, column_name FROM information_schema.columns "
        "WHERE table_schema IN ('public','quant')")).fetchall()
dbc = {}
for s, t, col in rows:
    dbc.setdefault((s, t), set()).add(col)

def collect(pkg_name):
    """返回 {(schema,table): {cls_key: (cls, cols)}}"""
    out = {}
    mod = importlib.import_module(pkg_name)
    paths = getattr(mod, "__path__", None)
    mods = [m.name for m in pkgutil.walk_packages(paths, pkg_name + ".")] if paths else [pkg_name]
    mods.append(pkg_name)
    for name in mods:
        try:
            m = importlib.import_module(name)
        except Exception as e:
            print("  [导入失败] %s: %s" % (name, e)); continue
        for _, cls in inspect.getmembers(m, inspect.isclass):
            if not issubclass(cls, Base) or cls is Base: continue
            try: mapper = class_mapper(cls)
            except Exception: continue
            tbl = mapper.persist_selectable
            key = (tbl.schema or "public", tbl.name)
            ck = (cls.__module__, cls.__name__)
            out.setdefault(key, {})[ck] = (cls, set(c.name for c in mapper.columns))
    return out

pkg = collect("infrastructure.persistence.orm.models")
repo = collect("adapters.outbound.repositories")

def report(label, models):
    ok=[]; drift=[]; notbl=[]
    for k, defs in sorted(models.items()):
        real = dbc.get(k)
        if real is None:
            notbl.append((k, sorted(defs.keys()))); continue
        for ck, (cls, cols) in defs.items():
            miss = cols - real
            (drift if miss else ok).append((k, ck[1], sorted(miss)))
    print("\n--- %s ---" % label)
    print("  一致模型: %d | 漂移: %d | 表不存在: %d" % (len(ok), len(drift), len(notbl)))
    for k, cn, miss in drift:
        print("  [漂移] %s.%s (%s)" % (k[0], k[1], cn))
        print("         DB 无此列: %s" % miss)
    for k, defs in notbl:
        print("  [表不存在] %s.%s  <- %s" % (k[0], k[1], ", ".join(d[1] for d in defs)))
    return drift, notbl

print("="*78); print("A. orm/models 包内模型"); print("="*78)
d1, n1 = report("A. orm/models", pkg)
print("\n" + "="*78); print("B. repository 内联模型（现有门禁盲区）"); print("="*78)
d2, n2 = report("B. repositories", repo)

print("\n" + "="*78); print("C. 同一张表被多个模型定义"); print("="*78)
merged = {}
for k, defs in list(pkg.items()) + list(repo.items()):
    merged.setdefault(k, {}).update(defs)
reals = {k: v for k, v in merged.items() if len(v) > 1}
if not reals: print("  (无)")
for k, defs in sorted(reals.items()):
    colsets = {frozenset(c) for _, c in defs.values()}
    flag = "  ⚠️ 列集合不一致" if len(colsets) > 1 else ""
    print("  %s.%s  (%d 个定义)%s" % (k[0], k[1], len(defs), flag))
    for (mod, cn), (cls, cols) in sorted(defs.items()):
        print("      - %s.%s  [%d 列]" % (mod, cn, len(cols)))
    if len(colsets) > 1:
        inter = set.intersection(*[set(c) for c in colsets])
        union = set.union(*[set(c) for c in colsets])
        print("         仅交集列: %s" % sorted(inter))
        print("         差异列  : %s" % sorted(union - inter))

print("\n" + "="*78)
print("汇总: 包内漂移 %d | 内联漂移 %d | 包内缺表 %d | 内联缺表 %d | 重复定义 %d 张"
      % (len(d1), len(d2), len(n1), len(n2), len(reals)))
print("="*78)
