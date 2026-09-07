#!/usr/bin/env python3
"""action 大小写统一迁移（2026-08-13）—— 幂等

契约：quant.simulation_trades / simulation_order / simulation_pending_orders /
signals 四张表的 action 列一律大写（BUY/SELL[/HOLD]），ORM @validates +
DB CHECK 双重强制（见 infrastructure/persistence/orm/models/action_norm.py）。

背景：61528de 只在 repository 单点规范化，大小写混写导致幽灵持仓（08-12）、
settle_t1 失效、日买入护栏失效（account_trading_service 小写比较）等事故。

步骤（顺序敏感：先清洗数据，再加 CHECK，否则 ADD CONSTRAINT 校验存量失败）：
1. create_all(checkfirst) —— 新环境建表自带 CHECK
2. UPDATE 四表 action 大写化（幂等）
3. pg_constraint 探测后 ADD CHECK ×4（幂等）

回滚：python scripts/migrate_20260813_action_case_unify.py rollback
（DROP CONSTRAINT；数据保持大写——旧代码读取侧的 func.upper()/.lower()
容忍写法不受影响，小写等值比较的代码点在 git 历史中与 CHECK 同进同退）

生产与测试库各跑一次：
    python scripts/migrate_20260813_action_case_unify.py
    PGDATABASE=quant_test python scripts/migrate_20260813_action_case_unify.py
"""
import sys

import structlog
from sqlalchemy import text

from infrastructure.persistence.database.engine import get_engine
from infrastructure.persistence.orm import models  # noqa: F401 确保全部模型注册到 metadata
from infrastructure.persistence.orm.base import Base

logger = structlog.get_logger(__name__)

# (表, CHECK 约束名, 允许值)
_ACTION_CONTRACTS = [
    ('simulation_trades', 'simulation_trades_action_check', "('BUY','SELL')"),
    ('simulation_order', 'simulation_order_action_check', "('BUY','SELL')"),
    ('simulation_pending_orders', 'simulation_pending_orders_action_check', "('BUY','SELL')"),
    ('signals', 'signals_action_check', "('BUY','SELL','HOLD')"),
]


def _constraint_exists(conn, name: str) -> bool:
    row = conn.execute(text(
        "SELECT 1 FROM pg_constraint WHERE conname = :n"
    ), {'n': name}).fetchone()
    return row is not None


def run_migration():
    engine = get_engine()
    # 1) 建表（幂等 checkfirst；新表自带 CHECK）
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        # 2) 数据清洗：action 大写化（幂等；已大写的行零操作）
        for table, _, _ in _ACTION_CONTRACTS:
            result = conn.execute(text(
                f"UPDATE quant.{table} SET action = UPPER(action) "
                f"WHERE action <> UPPER(action)"
            ))
            logger.info("action_uppercased", table=table, rows=result.rowcount)

        # 3) CHECK 约束（先清洗后加，否则存量校验失败）
        for table, constraint, allowed in _ACTION_CONTRACTS:
            if not _constraint_exists(conn, constraint):
                conn.execute(text(
                    f"ALTER TABLE quant.{table} ADD CONSTRAINT {constraint} "
                    f"CHECK (action IN {allowed})"
                ))
                logger.info("check_constraint_added", table=table, constraint=constraint)

        # 4) 核验：四表不应存在非大写 action
        for table, _, allowed in _ACTION_CONTRACTS:
            bad = conn.execute(text(
                f"SELECT count(*) FROM quant.{table} WHERE action NOT IN {allowed}"
            )).scalar()
            if bad:
                raise RuntimeError(f"{table} 仍有 {bad} 行非法 action，迁移未完成")

    logger.info("action_case_unify_migration_done")


def rollback():
    """回滚：仅 DROP CHECK 约束（数据保持大写，无需回退）"""
    engine = get_engine()
    with engine.begin() as conn:
        for table, constraint, _ in _ACTION_CONTRACTS:
            if _constraint_exists(conn, constraint):
                conn.execute(text(
                    f"ALTER TABLE quant.{table} DROP CONSTRAINT {constraint}"
                ))
                logger.info("check_constraint_dropped", table=table, constraint=constraint)
    logger.info("action_case_unify_rollback_done")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback()
    else:
        run_migration()
