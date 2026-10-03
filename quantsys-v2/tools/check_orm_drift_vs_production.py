#!/usr/bin/env python3
"""ORM ↔ **生产库** 漂移检查器（2026-10-02 · REQ-261001145152-3982 P1-7 治本项）。

## 为什么需要（本次审查补上的盲区）

`tests/test_orm_db_drift.py` 只查一个方向：**模型声明了、测试库没有**。
**生产库**的反向漂移**没有任何守卫** —— 于是攒出 4 张「ORM 有模型、生产库没表」的对象
（`event_calendar` / `chip_distribution_state` / `chip_metrics` / `memory_entries`），
其中两张直接造成线上故障：

    POST /api/memory              → 500 UndefinedTable（记忆写入全挂）
    event_calendar_check（每日）  → 报错被吞 → 假成功 → **毒化共享会话** →
                                    终态记账失败 → 台账假失败（链条见审计报告 §W）

## 为什么不放进 pytest

本仓有**三层防护**阻止测试连生产库（根 conftest + 同步/异步仓储运行时校验，
库名不以 `_test` 结尾即拒绝）。把"查生产"塞进测试套件会**破坏这套安全设计** ×。
故做成**独立命令**：人工/巡检显式调用，只读，不参与 `pytest`。

## 用法

    python tools/check_orm_drift_vs_production.py                 # 查生产（默认）
    python tools/check_orm_drift_vs_production.py --dsn postgresql://…   # 查指定库
    python tools/check_orm_drift_vs_production.py --strict        # 有漂移即退出码 2

退出码：0 = 无漂移；2 = 有漂移（且 --strict）；3 = 检查器自身出错。
"""
from __future__ import annotations

import argparse
import sys

SCHEMA = 'quant'


def _models_metadata():
    """触发全部 ORM 模型注册，返回 metadata。"""
    import importlib
    import pkgutil

    import infrastructure.persistence.orm.models as models_pkg

    for m in pkgutil.iter_modules(models_pkg.__path__):
        try:
            importlib.import_module(f'{models_pkg.__name__}.{m.name}')
        except Exception:  # noqa: BLE001 - 单个模型导入失败不应中断整体扫描
            pass
    from infrastructure.persistence.orm.base import Base
    return Base.metadata


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dsn', default=None, help='目标库 DSN（默认取 settings，即生产）')
    ap.add_argument('--strict', action='store_true', help='有漂移时退出码 2')
    args = ap.parse_args()

    try:
        from sqlalchemy import create_engine, text

        if args.dsn:
            engine = create_engine(args.dsn)
        else:
            from infrastructure.persistence.database.engine import get_engine
            engine = get_engine()
        metadata = _models_metadata()
    except Exception as e:  # noqa: BLE001
        print(f'❌ 初始化失败: {e}', file=sys.stderr)
        return 3

    print(f'  目标库: {engine.url.database}（**只读**）')
    missing_tables: list[tuple[str, int]] = []
    missing_cols: list[tuple[str, str]] = []

    with engine.connect() as conn:
        for table in metadata.sorted_tables:
            if table.schema not in (None, SCHEMA):
                continue
            name = table.name
            exists = conn.execute(text(
                "select count(*) from information_schema.tables "
                "where table_schema=:s and table_name=:t"),
                {'s': SCHEMA, 't': name}).scalar()
            if not exists:
                missing_tables.append((name, len(table.columns)))
                continue
            db_cols = {r[0] for r in conn.execute(text(
                "select column_name from information_schema.columns "
                "where table_schema=:s and table_name=:t"),
                {'s': SCHEMA, 't': name})}
            for col in table.columns:
                if col.name not in db_cols:
                    missing_cols.append((name, col.name))

    print(f'  ── 模型声明、库中缺失的**表** ──')
    if not missing_tables:
        print('    （无）')
    for name, ncol in missing_tables:
        print(f'    ❌ {SCHEMA}.{name:<34} 模型声明 {ncol} 列，库中无此表')

    print(f'  ── 模型声明、库中缺失的**列** ──')
    if not missing_cols:
        print('    （无）')
    for tname, cname in missing_cols[:30]:
        print(f'    ❌ {SCHEMA}.{tname}.{cname}')
    if len(missing_cols) > 30:
        print(f'    …另外 {len(missing_cols) - 30} 列')

    total = len(missing_tables) + len(missing_cols)
    print(f'\n  合计漂移: {total} 处（缺表 {len(missing_tables)} / 缺列 {len(missing_cols)}）')
    if total:
        print('  ⚠️ 生产库缺这些对象 ⇒ 对应用例会报 UndefinedTable / UndefinedColumn。')
        print('     修法：按模型生成 DDL 的迁移（例：'
              'infrastructure/persistence/migrations/20261002_create_missing_orm_tables.py）。')
    if total and args.strict:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
