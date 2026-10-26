"""ReflectionPackService：反思材料包组装（t10 · FR-5 · D-4 四输入）

固定四段（缺数据 → 该段 status=missing，不用空数组冒充）：
  1. modifications 计划修改历史（版本行：改了什么/理由/观察窗）
  2. missed        错过机会（被拦/抑制触发的后续走势）
  3. wins          盈利成交（计划内 SELL 且 pnl>0）
  4. losses        亏损成交（计划内 SELL 且 pnl<0，含止损后走势数据指针）
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

MISSING = 'missing'


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReflectionPackService:
    def __init__(self, plan_repo, stats_repo=None, trades_provider=None,
                 now_fn: Callable[[], datetime] = _utcnow):
        self.repo = plan_repo
        self.stats_repo = stats_repo
        self._trades = trades_provider
        self._now = now_fn

    def build(self, plan_id: int) -> Dict[str, Any]:
        plan = self.repo.get_plan(plan_id)
        if plan is None:
            raise LookupError('计划不存在：%s' % plan_id)
        pack: Dict[str, Any] = {
            'plan_id': plan_id, 'period': self._now().date().isoformat(),
            'built_at': self._now().isoformat(),
        }
        pack['modifications'] = self._modifications(plan_id)
        pack['missed'] = self._missed(plan)
        wins, losses = self._pnl_split(plan_id)
        pack['wins'] = wins
        pack['losses'] = losses
        pack['inputs_ready'] = [k for k in ('modifications', 'missed', 'wins', 'losses')
                                if pack[k].get('status') != MISSING]
        return pack

    # ── 四段 ──────────────────────────────────────────────
    def _modifications(self, plan_id: int) -> Dict[str, Any]:
        versions = self.repo.list_versions(plan_id, limit=10) or []
        rows = [{
            'version': v.version,
            'change_reason': v.change_reason,
            'window_ends_at': (v.window_ends_at.isoformat()
                               if getattr(v, 'window_ends_at', None) else None),
            'baseline': getattr(v, 'baseline', None),
        } for v in versions]
        if not rows:
            return {'status': MISSING, 'reason': '计划暂无版本记录'}
        return {'status': 'ok', 'versions': rows}

    def _missed(self, plan) -> Dict[str, Any]:
        if self.stats_repo is None:
            return {'status': MISSING, 'reason': '统计源未接入'}
        try:
            stats = self.stats_repo.blocked_stats(since_days=30, horizon=5)
        except Exception as e:  # noqa: BLE001
            return {'status': MISSING, 'reason': '被拦统计读取失败：%s' % e}
        if not stats.get('samples'):
            return {'status': MISSING, 'reason': '近 30 日无被拦样本'}
        return {'status': 'ok', **stats}

    def _pnl_split(self, plan_id: int):
        if self._trades is None:
            empty = {'status': MISSING, 'reason': '成交明细未接入'}
            return empty, dict(empty)
        try:
            rows = self._trades(plan_id)
        except Exception as e:  # noqa: BLE001
            empty = {'status': MISSING, 'reason': '成交明细读取失败：%s' % e}
            return empty, dict(empty)
        wins = [r for r in rows if (r.get('realized_pnl') or 0) > 0]
        losses = [r for r in rows if (r.get('realized_pnl') or 0) < 0]
        def pack(items, label):
            if not items:
                return {'status': MISSING, 'reason': '本周期无%s成交' % label}
            return {'status': 'ok', 'count': len(items),
                    'total_pnl': round(sum(float(r.get('realized_pnl') or 0) for r in items), 2),
                    'items': items[:50] if len(items) > 50 else items,
                    'truncated': len(items) > 50}
        return pack(wins, '盈利'), pack(losses, '亏损')


def trades_provider_from_engine(engine_factory=None):
    """默认成交读取：plan_id 的 SELL 成交（含 pnl 与日期）。"""
    def _provider(plan_id: int) -> List[Dict[str, Any]]:
        from sqlalchemy import text
        eng = (engine_factory or _engine)()
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, symbol, filled_price, realized_pnl, trade_date "
                "FROM quant.simulation_trades WHERE plan_id = :p AND action='SELL' "
                "ORDER BY trade_date DESC LIMIT 200"), {'p': plan_id}).mappings().all()
        return [{'trade_id': r['id'], 'symbol': r['symbol'],
                 'price': float(r['filled_price'] or 0),
                 'realized_pnl': float(r['realized_pnl'] or 0),
                 'trade_date': r['trade_date'].isoformat() if r['trade_date'] else None}
                for r in rows]
    return _provider


def _engine():
    from qs_kernel.infrastructure.persistence.database.engine import get_engine
    return get_engine()
