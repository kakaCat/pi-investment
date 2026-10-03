#!/usr/bin/env python
"""生产库补齐 4 张「模型声明了、库表不存在」的表（2026-10-02 · REQ-261001145152-3982 P1-7）

## 背景：**漂移门禁的盲区**

`tests/test_orm_db_drift.py` 只比对「**模型声明、测试库没有**」这一个方向，
而**生产库**的反向漂移一直无人看守 —— 于是攒出下面 4 张「ORM 有模型、库里没表」的对象。

## 实证（不是推测）

**① 生产库实查（`information_schema`，建表前）**：

    event_calendar 存在=0 ｜ chip_distribution_state 存在=0
    chip_metrics   存在=0 ｜ memory_entries         存在=0

**② 线上/日志里可见的后果**：

| 缺表 | 谁在用 | 实测后果 |
|---|---|---|
| `quant.memory_entries` | `POST /api/memory` | `500 UndefinedTable`（线上 curl 实测）；日志出现 272/137 次 |
| `quant.event_calendar` | `_job_event_calendar_check`（每日 16:45） | 查询报错被吞 → 记 `no_event`（假成功）→ **并毒化共享会话** → 随后的终态记账报 `InFailedSqlTransaction` → 台账落成 **failed**（假失败）。完整链条见审计报告 §W |
| `quant.chip_distribution_state` / `quant.chip_metrics` | 筹码分布计算/查询 | 功能不可用（日志 2 次 `UndefinedTable`） |

**③ 为什么"表里到底该有哪些列"不用猜**：4 张表**都有 ORM 模型** ——
`EventCalendar` / `ChipState` / `ChipMetrics` / `MemoryEntryModel`。
本迁移的 DDL 由 `sqlalchemy.schema.CreateTable`（postgresql dialect）**从模型生成**，
并与**测试库中由 `create_all` 建出的同名表逐列校对一致**（类型、可空性、默认值全同）。

## 幂等与安全

- 只 **CREATE 缺失的表**：已存在则跳过（不 DROP、不 ALTER 任何现有对象）；
- 默认 **dry-run**，加 `--apply` 才执行；
- 执行前后各打印一次「存在与否 + 行数」。

## 用法（注意 DSN —— 别指望 `PGDATABASE` 覆盖）

```bash
# 生产（默认取 settings 里的库）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261002_create_missing_orm_tables.py --apply

# 测试库（显式 DSN；测试库通常已由 create_all 建好，本迁移会是 no-op）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261002_create_missing_orm_tables.py \
    --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test
```

## 回滚

    4 张表在建表前**都不存在**（见上），故回滚即 `DROP TABLE`：
    DROP TABLE IF EXISTS quant.event_calendar, quant.chip_distribution_state,
                         quant.chip_metrics, quant.memory_entries CASCADE;
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql

TABLES = ('event_calendar', 'chip_distribution_state', 'chip_metrics', 'memory_entries')


def _models():
    from adapters.outbound.repositories.event_calendar_repository import EventCalendar
    from adapters.outbound.repositories.chip_repository import ChipState, ChipMetrics
    from adapters.outbound.repositories.memory_repository import MemoryEntryModel

    models = (EventCalendar, ChipState, ChipMetrics, MemoryEntryModel)
    for m in models:
        if m.__table__.schema is None:
            m.__table__.schema = 'quant'
    return models


def _ddl_for(model) -> list[str]:
    pg = postgresql.dialect()
    stmts = [str(CreateTable(model.__table__).compile(dialect=pg)).strip()]
    stmts += [str(CreateIndex(i).compile(dialect=pg)).strip() for i in model.__table__.indexes]
    return stmts


def main() -> int:
    ap = argparse.ArgumentParser(description='补齐 4 张「模型有、库表无」的表')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库；别指望 PGDATABASE）')
    args = ap.parse_args()

    from sqlalchemy import create_engine, text

    if args.dsn:
        engine = create_engine(args.dsn)
    else:
        from infrastructure.persistence.database.engine import get_engine
        engine = get_engine()

    with engine.connect() as conn:
        print(f'  目标库: {engine.url.database}')
        missing = []
        for name in TABLES:
            n = conn.execute(text(
                "select count(*) from information_schema.tables "
                "where table_schema='quant' and table_name=:t"), {'t': name}).scalar()
            rows = conn.execute(text(f'select count(*) from quant."{name}"')).scalar() if n else 'n/a'
            print(f'    {name:<28} 存在={n} 行数={rows}')
            if not n:
                missing.append(name)

        if not missing:
            print('  ✅ 4 张表都已存在，无需执行（幂等 no-op）')
            return 0

        print(f'  待建: {missing}')
        for model in _models():
            if model.__table__.name not in missing:
                continue
            for stmt in _ddl_for(model):
                if args.apply:
                    conn.execute(text(stmt))
                else:
                    print(f'    [dry-run] {stmt.splitlines()[0]} …')
        if args.apply:
            conn.commit()
            print('  ✅ 已提交')
        else:
            print('  [dry-run] 未做任何写入。加 --apply 执行。')

    if args.apply:
        with engine.connect() as conn:
            for name in missing:
                n = conn.execute(text(
                    "select count(*) from information_schema.columns "
                    "where table_schema='quant' and table_name=:t"), {'t': name}).scalar()
                print(f'    复核 {name:<28} 列数={n}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
