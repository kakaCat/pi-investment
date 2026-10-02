#!/usr/bin/env python
"""补齐 ORM 声明而库中缺失的列（漂移门禁报出的 4 处）

## 为什么需要它

`tests/test_orm_db_drift.py`（ORM ↔ 库 schema 漂移门禁）报出 5 列「模型有、库没有」：

    quant.simulation_account.account_type
    quant.simulation_order.submitted_by
    quant.simulation_pending_orders.submitted_by
    quant.agent_decisions.score
    quant.agent_decisions.score_band

这类漂移不是"看着不整齐"——SQLAlchemy 的 INSERT/UPDATE 会带上**模型声明的全部列**，
库里缺列就是 `column "x" does not exist`，属**必炸**。实测其中三列**生产代码正在写**：

- `submitted_by`：`account_trading_service.py` 传参、`simulation_async.py` 从 API 取；
- `score` / `score_band`：`decision_score_service.py` 的 `update_score()`，
  而它挂在 **`daily_orchestrator.py` 的 review_phase（每日自动跑）**上。

## 用法

    python .../20261002_orm_drift_missing_columns.py                     # dry-run（默认）
    python .../20261002_orm_drift_missing_columns.py --apply
    python .../20261002_orm_drift_missing_columns.py --apply \
        --dsn postgresql://user@127.0.0.1:5432/quant_test                # 补测试库镜像

## 约定（与本仓既有迁移一致）

- **默认 dry-run**，加 `--apply` 才写；
- `ADD COLUMN IF NOT EXISTS` 幂等；
- **带 `lock_timeout` / `statement_timeout`**：2026-10-02 实测测试库常有 `idle in transaction`
  连接持锁，无上限的 DDL 会**无限等锁**（漂移门禁曾因此让整套测试停摆）。
  这里等不到锁就报错退出，而不是挂死。
- 退出码：0 = 已补或无需补；2 = 应用失败。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import create_engine, text  # noqa: E402


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


# (表, 列, 类型, 注释) —— 类型与注释取自 ORM 模型声明
COLUMNS = [
    ('simulation_account', 'account_type', 'varchar(30)',
     '账户自动化类型: strategy=策略自动/agent=Agent驱动/user=用户主仓/legacy=历史冻结'),
    ('simulation_order', 'submitted_by', 'varchar(50)',
     '下单窗口编码（如 w-64c01af2）'),
    ('simulation_pending_orders', 'submitted_by', 'varchar(50)',
     '下单窗口编码（如 w-64c01af2）'),
    ('agent_decisions', 'score', 'double precision',
     '决策打分 [-1,1]（P0a，2026-08-07）'),
    ('agent_decisions', 'score_band', 'varchar(20)',
     'big_win/small_win/neutral/small_loss/big_loss'),
    # ── 2026-10-02 追加：对**生产库**扫出的反向漂移（测试库有、生产没有 → 查测试库的门禁看不见）──
    # 代码确实在写这 5 列：simulation_repository.py:462 写 decision_at、
    # account_trading_service.py:295 传 decision_price/price_source、
    # execution_service.py:210 算 slippage_bps（撮合后回填 fill_price）。
    # 类型取自 ORM 模型声明，与测试库现有定义逐一致。
    ('simulation_pending_orders', 'decision_price', 'numeric(10,2)', '决策时价（滑点基准）'),
    ('simulation_pending_orders', 'decision_at', 'timestamptz', '决策时刻'),
    ('simulation_pending_orders', 'price_source', 'text', '决策价来源（R-013 可追溯）'),
    ('simulation_pending_orders', 'fill_price', 'numeric(10,2)', '实际成交价'),
    ('simulation_pending_orders', 'slippage_bps', 'numeric(10,2)', '滑点基点（正=买贵/卖便宜=成本）'),
]

# 先设上限再动手：等不到锁就报错，不挂死（见模块 docstring 的约定说明）
GUARDS = [
    "SET lock_timeout = '30s'",
    "SET statement_timeout = '120s'",
]


def _ddl(table: str, column: str, coltype: str, comment: str) -> list[str]:
    return [
        f"ALTER TABLE quant.{table} ADD COLUMN IF NOT EXISTS {column} {coltype}",
        f"COMMENT ON COLUMN quant.{table}.{column} IS '{comment}'",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description='补齐漂移门禁报出的缺失列')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库）')
    args = ap.parse_args()

    engine = _engine(args.dsn)
    with engine.begin() as conn:
        for g in GUARDS:
            conn.execute(text(g))

        have = {(r[0], r[1]) for r in conn.execute(text(
            "select table_name, column_name from information_schema.columns "
            "where table_schema='quant'"))}
        missing = [(t, c, ty, cm) for (t, c, ty, cm) in COLUMNS if (t, c) not in have]
        print(f"[现状] 目标列 {len(COLUMNS)} 个；缺失 {[(t, c) for t, c, _, _ in missing] or '无'}")
        if not missing:
            print("[跳过] 均已存在（幂等）")
            return 0

        if not args.apply:
            for t, c, ty, cm in missing:
                for stmt in _ddl(t, c, ty, cm):
                    print(f"[dry-run] {stmt}")
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0

        for t, c, ty, cm in missing:
            for stmt in _ddl(t, c, ty, cm):
                conn.execute(text(stmt))
                print(f"[apply] {stmt}")

        # 复核：逐列回读（空表也要能跑——本仓 20261002 那支曾在空表上 row[0] 抛 TypeError）
        after = {(r[0], r[1]) for r in conn.execute(text(
            "select table_name, column_name from information_schema.columns "
            "where table_schema='quant'"))}
        still = [(t, c) for t, c, _, _ in COLUMNS if (t, c) not in after]
        if still:
            print(f"[verify] ❌ 仍缺: {still}")
            return 2
        print(f"[verify] ✅ {len(COLUMNS)} 列均已就位")

    print("[完成] ORM 模型与库表漂移已消除")
    return 0


if __name__ == '__main__':
    sys.exit(main())
