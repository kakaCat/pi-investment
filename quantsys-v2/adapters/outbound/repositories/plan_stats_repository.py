"""计划统计与被拦信号统计（t9 · IF-14/IF-16）

口径：
- 计划内盈亏 = simulation_trades.plan_id = 计划 id 的成交（realized_pnl 只在 SELL 有价值）；
- 计划外 = 同账户 plan_id IS NULL 的成交（只计数，不计入计划盈亏）；
- 被拦信号 = watch_triggers.suppressed = true 且已回填收盘价的样本：
    expected_direction=up 且后续上涨 → 拦错（该做没做）；=down 且下跌 → 拦对。
  方向缺失的样本记 undecidable，不进分子分母（不凑数）。
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

from qs_kernel.infrastructure.persistence.database.engine import get_engine


def _conn():
    return get_engine().connect()


def plan_stats(plan_id: int, account: str = '') -> Dict[str, Any]:
    with _conn() as conn:
        rows = conn.execute(text(
            "SELECT count(*) AS n, "
            "count(*) FILTER (WHERE action='BUY') AS buys, "
            "count(*) FILTER (WHERE action='SELL') AS sells, "
            "coalesce(sum(realized_pnl) FILTER (WHERE action='SELL'),0) AS pnl, "
            "count(*) FILTER (WHERE action='SELL' AND coalesce(realized_pnl,0) > 0) AS wins, "
            "count(*) FILTER (WHERE action='SELL' AND coalesce(realized_pnl,0) < 0) AS losses "
            "FROM quant.simulation_trades WHERE plan_id = :p"), {'p': plan_id}).mappings().first()
        versions = conn.execute(text(
            "SELECT count(*) FROM quant.trading_plan_versions WHERE plan_id = :p"),
            {'p': plan_id}).scalar()
        outside = 0
        if account:
            outside = conn.execute(text(
                "SELECT count(*) FROM quant.simulation_trades "
                "WHERE plan_id IS NULL AND account_name = :a"), {'a': account}).scalar()
    sells = int(rows['sells'] or 0)
    wins = int(rows['wins'] or 0)
    losses = int(rows['losses'] or 0)
    return {
        'plan_id': plan_id,
        'trades': {
            'total': int(rows['n'] or 0), 'buys': int(rows['buys'] or 0),
            'sells': sells,
        },
        'pnl': float(rows['pnl'] or 0),
        'win_rate': round(wins / sells, 4) if sells else None,
        'wins': wins, 'losses': losses,
        'versions': int(versions or 0),
        'outside_trades': int(outside or 0),
    }


def blocked_stats(since_days: int = 30, horizon: int = 5) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, int(since_days)))
    with _conn() as conn:
        rows = conn.execute(text(
            "SELECT c.expected_direction AS dir, c.pct_change AS pct "
            "FROM quant.watch_outcome_checks c "
            "JOIN quant.watch_triggers t ON t.id = c.trigger_id "
            "WHERE t.suppressed = true AND c.horizon_td = :h AND t.triggered_at >= :since"),
            {'h': int(horizon), 'since': since}).mappings().all()
    right = wrong = undecidable = 0
    pcts = []
    for r in rows:
        direction = (r['dir'] or '').lower()
        pct = r['pct']
        if pct is None or direction not in ('up', 'down'):
            undecidable += 1
            continue
        pcts.append(float(pct))
        if (direction == 'up' and pct > 0) or (direction == 'down' and pct < 0):
            wrong += 1   # 拦错了：本该发生的行情被拦掉
        else:
            right += 1   # 拦对了：拦掉后行情反向
    decided = right + wrong
    return {
        'horizon_td': int(horizon), 'since_days': int(since_days),
        'samples': len(rows), 'decided': decided,
        'blocked_right': right, 'blocked_wrong': wrong,
        'undecidable': undecidable,
        'wrong_rate': round(wrong / decided, 4) if decided else None,
        'avg_pct': round(sum(pcts) / len(pcts), 4) if pcts else None,
        'note': '拦错 = 被拦信号后续走势与预期同向（该做没做）；方向不可判的样本不计入分母',
    }
