"""触发走势回填仓储（2026-10-20 P3 预判验证闭环）

quant.watch_outcome_checks 的唯一写入口（Upsert 幂等：(trigger_id, horizon_td) 唯一）。
读侧提供命中率聚合，供复盘/元复核消费。
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from infrastructure.persistence.orm import close_session, get_session
from infrastructure.persistence.orm.models.watch_todo import WatchOutcomeCheck

logger = structlog.get_logger(__name__)


class WatchOutcomeRepository:
    """watch_outcome_checks 仓储（同步 session 口径与其它 watch 仓储一致）"""

    def record(self, *, trigger_id: int, rule_id, symbol: str, horizon_td: int,
               trigger_at=None, trigger_price=None, expected_direction=None,
               check_date=None, close_price=None, pct_change=None,
               hit=None, note=None) -> bool:
        """幂等回填：同 (trigger_id, horizon_td) 已存在则跳过（返回 False）。"""
        try:
            tbl = WatchOutcomeCheck.__table__
            stmt = pg_insert(tbl).values(
                trigger_id=trigger_id, rule_id=rule_id, symbol=symbol,
                horizon_td=horizon_td, trigger_at=trigger_at,
                trigger_price=trigger_price, expected_direction=expected_direction,
                check_date=check_date, close_price=close_price,
                pct_change=pct_change, hit=hit, note=note,
            ).on_conflict_do_nothing(
                index_elements=[tbl.c.trigger_id, tbl.c.horizon_td])
            session = get_session()
            result = session.execute(stmt)
            session.commit()
            return (result.rowcount or 0) > 0
        except Exception as e:
            logger.error('走势回填落库失败', trigger_id=trigger_id,
                         horizon_td=horizon_td, error=str(e))
            try:
                get_session().rollback()
            except Exception:  # noqa: BLE001
                pass
            raise

    def pending_triggers(self, horizon_td: int, due_before: date,
                         since: datetime, limit: int = 500) -> List[Dict[str, Any]]:
        """找出「该回填还没回填」的触发：触发日+horizon 个交易日 ≤ due_before。

        只取 since 以来的触发（回填窗口有界，防全表扫描）；suppressed 样本包含在内
        （「触及未确认」正是盘感样本）。
        """
        from infrastructure.persistence.orm.models.watch_todo import WatchTodo  # noqa: F401
        from sqlalchemy import text as _text
        rows = get_session().execute(_text("""
            SELECT t.id, t.rule_id, t.symbol, t.triggered_at, t.trigger_price,
                   t.condition, r.intent
            FROM quant.watch_triggers t
            LEFT JOIN quant.watch_rules r ON r.id = t.rule_id
            LEFT JOIN quant.watch_outcome_checks o
                   ON o.trigger_id = t.id AND o.horizon_td = :h
            WHERE o.id IS NULL
              AND t.trigger_price IS NOT NULL
              AND t.triggered_at >= :since
              AND t.triggered_at::date <= :due
            ORDER BY t.triggered_at
            LIMIT :lim
        """), {'h': horizon_td, 'since': since, 'due': due_before, 'lim': limit}).fetchall()
        return [
            {'trigger_id': r[0], 'rule_id': r[1], 'symbol': r[2],
             'triggered_at': r[3], 'trigger_price': float(r[4]),
             'condition': r[5], 'intent': r[6]}
            for r in rows
        ]

    def hit_rate(self, rule_id: Optional[int] = None,
                 horizon_td: Optional[int] = None) -> List[Dict[str, Any]]:
        """命中率聚合：按 (rule_id, horizon_td) 分组；hit IS NULL 的行不计入分母。"""
        from sqlalchemy import text as _text
        where, params = [], {}
        if rule_id is not None:
            where.append('rule_id = :rid')
            params['rid'] = rule_id
        if horizon_td is not None:
            where.append('horizon_td = :h')
            params['h'] = horizon_td
        sql = """
            SELECT rule_id, horizon_td,
                   count(*) FILTER (WHERE hit IS NOT NULL) AS judged,
                   count(*) FILTER (WHERE hit) AS hits,
                   round(avg(pct_change)::numeric, 2) AS avg_pct
            FROM quant.watch_outcome_checks
            %s
            GROUP BY rule_id, horizon_td
            ORDER BY rule_id, horizon_td
        """ % ('WHERE ' + ' AND '.join(where) if where else '')
        rows = get_session().execute(_text(sql), params).fetchall()
        return [
            {'rule_id': r[0], 'horizon_td': r[1], 'judged': r[2], 'hits': r[3],
             'hit_rate': (round(r[3] / r[2], 3) if r[2] else None),
             'avg_pct': (float(r[4]) if r[4] is not None else None)}
            for r in rows
        ]
