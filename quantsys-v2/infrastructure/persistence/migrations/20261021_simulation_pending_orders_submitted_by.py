#!/usr/bin/env python
"""quant.simulation_pending_orders 补齐 ORM 模型声明的 submitted_by 列（2026-10-21 · S11 风险面补证遗留）

## 背景（实测取证）

`tests/test_orm_db_drift.py`（2026-10-20 重启后风险面全覆盖 459P/21F/13E 批次遗留、
原判定"并行会话 simulation 仓储批次缺失 migration，待其收敛"——现其批已落地提交而
迁移仍未到位，故本卡补上）：

```
assert not ['quant.simulation_pending_orders.submitted_by']
```

- `infrastructure/persistence/orm/models/simulation.py` 的 `SimulationPendingOrder`
  （`__tablename__='simulation_pending_orders'`，:523）声明了
  `submitted_by = Column(String(50), comment='下单窗口编码（如 w-64c01af2）')`；
- 生产库 `quant.simulation_pending_orders` **已有**该列（orders_archived /
  simulation_order / orders_legacy_archived_20260825 / simulation_pending_orders 四表
  均已具备）；
- 测试库 `quant_test` 的 `simulation_pending_orders` **缺**该列——ORM 任何写/读
  （`to_dict` :556 也带）在测试环境均可能 UndefinedColumn。

## 幂等

`ADD COLUMN IF NOT EXISTS` + `COMMENT ON COLUMN`；既有行该列留 NULL（下单窗口编码
属可选溯源字段，NULL = 无窗口信息，不改变任何既有行语义）。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. PGDATABASE=quant_test ./venv/bin/python infrastructure/persistence/migrations/20261021_simulation_pending_orders_submitted_by.py            # dry-run
    PYTHONPATH=. PGDATABASE=quant_test ./venv/bin/python infrastructure/persistence/migrations/20261021_simulation_pending_orders_submitted_by.py --apply
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, text  # noqa: E402


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


DDL = [
    "ALTER TABLE quant.simulation_pending_orders ADD COLUMN IF NOT EXISTS submitted_by varchar(50)",
    "COMMENT ON COLUMN quant.simulation_pending_orders.submitted_by IS '下单窗口编码（如 w-64c01af2）'",
]

VERIFY = "select submitted_by from quant.simulation_pending_orders limit 1"


def main() -> int:
    ap = argparse.ArgumentParser(description='补齐 simulation_pending_orders.submitted_by 缺失列')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库）')
    args = ap.parse_args()

    engine = _engine(args.dsn)
    with engine.begin() as conn:
        have = {r[0] for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema='quant' and table_name='simulation_pending_orders'"))}
        if 'submitted_by' in have:
            print("[跳过] submitted_by 已存在（幂等）")
            return 0
        if not args.apply:
            for stmt in DDL:
                print(f"[dry-run] {stmt}")
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0
        for stmt in DDL:
            conn.execute(text(stmt))
            print(f"[apply] {stmt}")
        print("[verify] 列已就位（NULL 语义 = 无下单窗口信息）")
    print("[完成] simulation_pending_orders 已与 ORM 模型一致")
    return 0


if __name__ == '__main__':
    sys.exit(main())
