"""投资评价只读仓储（A 项）。

只读取既有事实表，不创建派生事实、不回写评分。所有方法显式接收账户，
避免把全局信号或其他账户成交混入本账户经济结果。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from qs_kernel.infrastructure.persistence.database.engine import get_engine


class InvestmentEvaluationRepository:
    def __init__(self, engine=None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            self._engine = get_engine()
        return self._engine

    def _fetch(self, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
            return [dict(row) for row in rows]

    @staticmethod
    def _date_clause(start_date: Optional[str], end_date: Optional[str], column: str) -> str:
        clauses = []
        if start_date:
            clauses.append(f"AND {column} >= :start_date")
        if end_date:
            clauses.append(f"AND {column} <= :end_date")
        return "\n".join(clauses)

    def get_account(self, account_name: str) -> Optional[Dict[str, Any]]:
        rows = self._fetch(
            """
            SELECT account_name, cash_available, cash_frozen, position_value,
                   total_value, initial_capital, account_type, status, updated_at
            FROM quant.simulation_account
            WHERE account_name = :account_name
            """,
            {"account_name": account_name},
        )
        return rows[0] if rows else None

    def get_trades(
        self, account_name: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"account_name": account_name, "start_date": start_date, "end_date": end_date}
        date_clause = self._date_clause(start_date, end_date, "t.trade_date")
        return self._fetch(
            f"""
            SELECT t.id, t.account_name, t.symbol, t.action, t.shares,
                   t.price, t.filled_price, t.amount,
                   COALESCE(t.commission, 0) AS commission,
                   COALESCE(t.stamp_duty, 0) AS stamp_duty,
                   COALESCE(t.transfer_fee, 0) AS transfer_fee,
                   t.total_cost, t.total_revenue, t.order_id,
                   t.realized_pnl, t.realized_pnl_rate, t.reason,
                   t.trade_date, t.trade_time, t.plan_id, t.plan_version, t.item_id,
                   o.signal_id, o.strategy_name, o.submitted_by,
                   o.decision_price AS order_decision_price,
                   o.decision_at AS order_decision_at,
                   p.id AS pending_order_id, p.decision_price AS pending_decision_price,
                   p.decision_at AS pending_decision_at, p.slippage_bps,
                   p.created_at AS pending_created_at
            FROM quant.simulation_trades t
            LEFT JOIN quant.simulation_order o ON o.id = t.order_id
            LEFT JOIN quant.simulation_pending_orders p ON p.executed_trade_id = t.id
            WHERE t.account_name = :account_name
            {date_clause}
            ORDER BY t.trade_time, t.id
            """,
            params,
        )

    def get_snapshots(
        self, account_name: str, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"account_name": account_name, "end_date": end_date}
        end_clause = "AND snapshot_date <= :end_date" if end_date else ""
        return self._fetch(
            f"""
            SELECT account_name, snapshot_date, cash, position_value, total_value,
                   is_synthetic, created_at
            FROM quant.simulation_equity_snapshot
            WHERE account_name = :account_name
            {end_clause}
            ORDER BY snapshot_date
            """,
            params,
        )

    def get_external_flows(
        self, account_name: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"account_name": account_name, "start_date": start_date, "end_date": end_date}
        date_clause = self._date_clause(start_date, end_date, "created_at::date")
        return self._fetch(
            f"""
            SELECT id, account_name, flow_type, amount, balance_after,
                   ref_order_id, ref_trade_id, created_at
            FROM quant.simulation_cash_flow
            WHERE account_name = :account_name
              AND flow_type IN ('deposit', 'withdraw')
            {date_clause}
            ORDER BY created_at, id
            """,
            params,
        )

    def get_positions(self, account_name: str) -> List[Dict[str, Any]]:
        return self._fetch(
            """
            SELECT account_name, symbol, shares_total, shares_available, avg_cost,
                   current_price, market_value, cost, profit_total, profit_total_rate,
                   created_at, updated_at
            FROM quant.simulation_positions
            WHERE account_name = :account_name AND shares_total > 0
            ORDER BY symbol
            """,
            {"account_name": account_name},
        )

    def get_signals(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {"start_date": start_date, "end_date": end_date}
        date_clause = self._date_clause(start_date, end_date, "signal_date")
        return self._fetch(
            f"""
            SELECT id, signal_date, symbol, grade, source, price, reason,
                   price_5d, price_10d, price_20d,
                   return_5d, return_10d, return_20d,
                   hit_5d, hit_10d, hit_20d, created_at, updated_at
            FROM quant.signal_tracking
            WHERE TRUE
            {date_clause}
            ORDER BY signal_date, symbol, source, id
            LIMIT 5000
            """,
            params,
        )

    def get_decision_summary(self, account_name: str) -> Dict[str, Any]:
        rows = self._fetch(
            """
            SELECT COUNT(*) AS decision_count,
                   COUNT(*) FILTER (WHERE score IS NOT NULL) AS scored_count,
                   COUNT(*) FILTER (
                       WHERE LOWER(decision_type) IN ('trade_buy', 'trade_sell')
                   ) AS trade_decision_count,
                   MAX(created_at) AS latest_decision_at
            FROM quant.agent_decisions
            WHERE context->>'account' = :account_name
            """,
            {"account_name": account_name},
        )
        return rows[0] if rows else {
            "decision_count": 0,
            "scored_count": 0,
            "trade_decision_count": 0,
            "latest_decision_at": None,
        }
