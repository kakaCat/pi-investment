"""踏空捕获服务（文本参数进化 P0b，2026-08-11）。

每日调度：捕获"信号已发但 agent 未行动"的买入信号，补登为 missed_opportunity
决策（不行动也是决策），满20交易日后由 DecisionScoreService 打分：
信号后涨=负分（踏空），跌=正分（正确观望）。
防奖励投机：agent 无法靠"少交易"逃避评分（总设计 §7）。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from application.services.evolution.decision_score_service import _as_date

logger = logging.getLogger(__name__)

BUY_ACTION = 'buy'
CAPTURABLE_STATUS = ('pending', 'rejected')


def _sig_get(signal, key):
    """Signal 可能是 ORM 对象（SignalORMRepository.get_signals_by_date_range
    返回 List[Signal]）也可能是 dict（同 ChanKnowledgeDistiller 的兼容处理）。"""
    if isinstance(signal, dict):
        return signal.get(key)
    return getattr(signal, key, None)


class MissedOpportunityService:
    """依赖注入同 DecisionScoreService：repo 可替换，便于 mock 测试。"""

    def __init__(self, signal_repo=None, decision_repo=None, kline_repo=None,
                 grace_trading_days: int = 5, daily_cap: int = 5):
        if signal_repo is None:
            from adapters.outbound.repositories.signal_repository import SignalORMRepository
            signal_repo = SignalORMRepository()
        if decision_repo is None:
            from adapters.outbound.repositories.agent_intelligence_repository import (
                AgentIntelligenceORMRepository,
            )
            decision_repo = AgentIntelligenceORMRepository()
        if kline_repo is None:
            from adapters.outbound.repositories.kline_repository import KlineORMRepository
            kline_repo = KlineORMRepository()
        self.signal_repo = signal_repo
        self.decision_repo = decision_repo
        self.kline_repo = kline_repo
        self.grace_trading_days = grace_trading_days
        self.daily_cap = daily_cap

    def capture(self, lookback_days: int = 10, today: Optional[date] = None) -> Dict[str, Any]:
        """滚动捕获最近 lookback_days 内未被行动的买入信号，返回计数汇总。"""
        today = today or date.today()
        start = today - timedelta(days=lookback_days)
        signals = self.signal_repo.get_signals_by_date_range(
            start.isoformat(), today.isoformat())
        result = {'scanned': 0, 'captured': 0, 'skipped_acted': 0,
                  'skipped_duplicate': 0, 'skipped_in_grace': 0,
                  'skipped_invalid': 0, 'errors': 0}

        # 候选：同日同 symbol 只留 confidence 最高的一条
        candidates: Dict[tuple, Any] = {}
        for s in signals or []:
            if str(_sig_get(s, 'action') or '').lower() != BUY_ACTION:
                continue
            if _sig_get(s, 'status') not in CAPTURABLE_STATUS:
                continue
            key = (str(_sig_get(s, 'signal_date'))[:10], _sig_get(s, 'symbol'))
            cur = candidates.get(key)
            if cur is None or (_sig_get(s, 'confidence') or 0) > (_sig_get(cur, 'confidence') or 0):
                candidates[key] = s

        # 每日限量：confidence 降序取前 daily_cap
        by_date: Dict[str, List[Any]] = {}
        for (d, _symbol), s in candidates.items():
            by_date.setdefault(d, []).append(s)
        selected: List[Any] = []
        for d, items in by_date.items():
            items.sort(key=lambda x: _sig_get(x, 'confidence') or 0, reverse=True)
            selected.extend(items[: self.daily_cap])

        for s in selected:
            result['scanned'] += 1
            try:
                outcome = self._capture_one(s, today)
            except Exception as e:
                logger.error(f"踏空捕获失败 signal {_sig_get(s, 'id')}: {e}")
                result['errors'] += 1
                continue
            result[outcome] += 1
        logger.info(f"踏空捕获完成: {result}")
        return result

    def _capture_one(self, signal: Any, today: date) -> str:
        signal_id = _sig_get(signal, 'id')
        decision_id = f"MISS-{signal_id}"
        if self.decision_repo.get_decision(decision_id):
            return 'skipped_duplicate'
        symbol = _sig_get(signal, 'symbol')
        signal_date = _as_date(_sig_get(signal, 'signal_date'))
        if not symbol or signal_date is None:
            return 'skipped_invalid'

        df = self.kline_repo.get_daily_klines(
            symbol, start_date=signal_date.isoformat(), end_date=today.isoformat())
        if df is None or df.height == 0:
            return 'skipped_invalid'
        rows = list(df.iter_rows(named=True))
        later = [r for r in rows
                 if _as_date(r['trade_date']) is not None
                 and _as_date(r['trade_date']) > signal_date]
        if len(later) < self.grace_trading_days:
            return 'skipped_in_grace'

        if self._acted(symbol, signal_date, later):
            return 'skipped_acted'

        price = _sig_get(signal, 'price')
        if price is None:
            price = float(rows[0]['close'])  # 信号日收盘兜底
        strategy_id = _sig_get(signal, 'strategy_id')
        self.decision_repo.create_decision({
            'decision_id': decision_id,
            'decision_type': 'missed_opportunity',
            'context': {
                'source': 'missed_signal_capture',
                'strategy_id': strategy_id,
                'signal_status': _sig_get(signal, 'status'),
                'signal_date': signal_date.isoformat(),
            },
            'parameters': {'symbol': symbol, 'price': float(price),
                           'signal_id': signal_id},
            'reasoning': f"信号未行动捕获（{strategy_id} @ {signal_date.isoformat()}）",
            'created_at': datetime.combine(signal_date, datetime.min.time()),
        })
        return 'captured'

    def _acted(self, symbol: str, signal_date: date, later_rows: List[dict]) -> bool:
        """宽限期内同 symbol 出现 trade_buy 决策 = 已行动。"""
        window_end = _as_date(later_rows[self.grace_trading_days - 1]['trade_date'])
        decisions = self.decision_repo.get_decisions_by_entity('stock', symbol, limit=100)
        for d in decisions:
            if d.get('decision_type') != 'trade_buy':
                continue
            dd = _as_date(d.get('created_at'))
            if dd is not None and signal_date < dd <= window_end:
                return True
        return False
