#!/usr/bin/env python3
"""多账户域迁移（2026-07-20）—— 幂等

1. 列改名/加列（account/positions/trades）
2. 建 3 张新表（order/cash_flow/equity_snapshot）
3. default → v13_simulation（三表）
4. 补建 v15_simulation 账户
5. 回填 initial_capital / 资金流水 / 当日快照
"""
import structlog
from sqlalchemy import text

from infrastructure.persistence.database.engine import get_engine
from infrastructure.persistence.orm import models  # noqa: F401 确保全部模型注册到 metadata
from infrastructure.persistence.orm.base import Base  # 模型实际使用的 Base（非 orm.config.Base）

logger = structlog.get_logger(__name__)


def _column_exists(conn, table, column):
    row = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='quant' AND table_name=:t AND column_name=:c"
    ), {'t': table, 'c': column}).fetchone()
    return row is not None


def _rename_column(conn, table, old, new):
    if _column_exists(conn, table, old) and not _column_exists(conn, table, new):
        conn.execute(text(f'ALTER TABLE quant.{table} RENAME COLUMN {old} TO {new}'))
        logger.info("column_renamed", table=table, old=old, new=new)


def run_migration():
    engine = get_engine()
    # 1) 新表（ORM metadata，幂等 checkfirst）
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        # 2) 列改名
        _rename_column(conn, 'simulation_account', 'cash', 'cash_available')
        _rename_column(conn, 'simulation_positions', 'shares', 'shares_total')
        _rename_column(conn, 'simulation_positions', 'avg_price', 'avg_cost')
        _rename_column(conn, 'simulation_positions', 'profit', 'profit_total')
        _rename_column(conn, 'simulation_positions', 'profit_rate', 'profit_total_rate')

        # 3) 加列
        ddls = [
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS cash_frozen NUMERIC(15,2) NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS position_value NUMERIC(15,2) NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS initial_capital NUMERIC(15,2) NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS display_name VARCHAR(100)",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(50)",
            "ALTER TABLE quant.simulation_account ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'active'",
            "ALTER TABLE quant.simulation_positions ADD COLUMN IF NOT EXISTS shares_available INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE quant.simulation_positions ADD COLUMN IF NOT EXISTS profit_today NUMERIC(15,2)",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS order_id INTEGER",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS transfer_fee NUMERIC(10,2) DEFAULT 0",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS realized_pnl NUMERIC(15,2)",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS realized_pnl_rate NUMERIC(10,4)",
            "ALTER TABLE quant.simulation_trades ADD COLUMN IF NOT EXISTS reason VARCHAR(500)",
        ]
        for ddl in ddls:
            conn.execute(text(ddl))

        # 历史持仓均已过 T+1：available = total
        conn.execute(text(
            "UPDATE quant.simulation_positions SET shares_available = shares_total "
            "WHERE shares_available = 0 AND shares_total > 0"
        ))

        # 4) default → v13_simulation（幂等：无 default 行时为零操作）
        for table in ('simulation_account', 'simulation_positions', 'simulation_trades'):
            conn.execute(text(
                f"UPDATE quant.{table} SET account_name='v13_simulation' "
                "WHERE account_name='default'"
            ))
        conn.execute(text(
            "UPDATE quant.simulation_account SET display_name='V13 多因子模拟仓', "
            "strategy_name='v13' WHERE account_name='v13_simulation'"
        ))
        conn.execute(text(
            "UPDATE quant.simulation_account SET display_name='V14 模拟仓', "
            "strategy_name='v14' WHERE account_name='v14_simulation'"
        ))

        # 5) 回填 initial_capital（用累计收益率反推，仅一次）
        conn.execute(text(
            "UPDATE quant.simulation_account SET initial_capital = "
            "CASE WHEN cumulative_return IS NOT NULL AND cumulative_return <> 0 "
            "THEN total_value / (1 + cumulative_return) ELSE total_value END "
            "WHERE initial_capital IS NULL OR initial_capital = 0"
        ))

        # 6) 补建策略账户（幂等；生产库 v13/v14 通常已由改名/历史数据存在）
        for acc, disp, strat in (
            ('v13_simulation', 'V13 多因子模拟仓', 'v13'),
            ('v14_simulation', 'V14 模拟仓', 'v14'),
            ('v15_simulation', 'V15 深度学习模拟仓', 'v15'),
        ):
            conn.execute(text(
                "INSERT INTO quant.simulation_account "
                "(account_name, display_name, strategy_name, initial_capital, "
                " cash_available, cash_frozen, position_value, total_value, peak_value, "
                " cumulative_return, max_drawdown, status) "
                "VALUES (:acc, :disp, :strat, 100000, "
                " 100000, 0, 0, 100000, 100000, 0, 0, 'active') "
                "ON CONFLICT (account_name) DO NOTHING"
            ), {'acc': acc, 'disp': disp, 'strat': strat})

        # 7) 回填资金流水（仅当流水表为空时，逐账户重放交易）
        flow_count = conn.execute(text("SELECT count(*) FROM quant.simulation_cash_flow")).scalar()
        if flow_count == 0:
            accounts = conn.execute(text(
                "SELECT account_name, initial_capital FROM quant.simulation_account"
            )).fetchall()
            for acc_name, init_cap in accounts:
                balance = float(init_cap or 0)
                conn.execute(text(
                    "INSERT INTO quant.simulation_cash_flow "
                    "(account_name, flow_type, amount, balance_after) "
                    "VALUES (:a, 'deposit', :amt, :bal)"
                ), {'a': acc_name, 'amt': balance, 'bal': balance})
                trades = conn.execute(text(
                    "SELECT id, action, amount, commission, stamp_duty "
                    "FROM quant.simulation_trades WHERE account_name=:a "
                    "ORDER BY trade_time, id"
                ), {'a': acc_name}).fetchall()
                for t_id, action, amount, commission, stamp_duty in trades:
                    amt = float(amount or 0)
                    fees = float(commission or 0) + float(stamp_duty or 0)
                    net = -(amt + fees) if action.lower() == 'buy' else (amt - fees)
                    ftype = 'buy_debit' if action.lower() == 'buy' else 'sell_credit'
                    balance += net
                    conn.execute(text(
                        "INSERT INTO quant.simulation_cash_flow "
                        "(account_name, flow_type, amount, balance_after, ref_trade_id) "
                        "VALUES (:a, :t, :amt, :bal, :tid)"
                    ), {'a': acc_name, 't': ftype, 'amt': net, 'bal': balance, 'tid': t_id})
                # 对账：流水终值 vs 账户余额，有差额写 adjustment 流水强制不变式成立
                cash_row = conn.execute(text(
                    "SELECT cash_available + cash_frozen FROM quant.simulation_account "
                    "WHERE account_name=:a"
                ), {'a': acc_name}).fetchone()
                if cash_row is not None:
                    drift = float(cash_row[0]) - balance
                    if abs(drift) > 0.01:
                        balance += drift
                        conn.execute(text(
                            "INSERT INTO quant.simulation_cash_flow "
                            "(account_name, flow_type, amount, balance_after) "
                            "VALUES (:a, 'adjustment', :amt, :bal)"
                        ), {'a': acc_name, 'amt': drift, 'bal': balance})
                        logger.warning("cash_flow_reconcile_adjustment",
                                       account=acc_name, drift=round(drift, 2))

        # 8) 当日快照（每账户一条，历史曲线由 /performance fallback 重放提供）
        conn.execute(text(
            "INSERT INTO quant.simulation_equity_snapshot "
            "(account_name, snapshot_date, cash, position_value, total_value, "
            " cumulative_return, drawdown) "
            "SELECT account_name, CURRENT_DATE, cash_available + cash_frozen, "
            "       position_value, total_value, cumulative_return, "
            "       CASE WHEN peak_value > 0 THEN total_value / peak_value - 1 ELSE 0 END "
            "FROM quant.simulation_account "
            "ON CONFLICT (account_name, snapshot_date) DO NOTHING"
        ))

    logger.info("multi_account_migration_done")


if __name__ == '__main__':
    run_migration()
