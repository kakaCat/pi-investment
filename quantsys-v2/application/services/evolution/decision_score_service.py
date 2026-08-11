"""决策打分服务（文本参数进化 P0a，2026-08-07）。

每日调度：对 evaluation_status='pending' 的 trade_buy/trade_sell 决策，
满 mature_window 个交易日后用 daily_klines 收盘价 + 沪深300 基准打分回写。
纯计算无判断——分数是裁判 agent 的待解读原料（总设计 §1.2/§3.1）。
依赖注入模式同 EvolutionFitnessService：repo 与 provider 可替换，便于 mock 测试。

窗口口径：future = 交易日之后（严格大于）的 K 线，按日期升序；
需 len(future) >= mature_window 才成熟，参考根为 future[mature_window - 1]
（0 基索引，即满 20 个交易日后按第 20 根收盘价定价）。
"""
import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

from application.services.evolution.score_calculator import compute_trade_score

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL = 'sh000300'
SCORABLE_TYPES = {'trade_buy': 'buy', 'trade_sell': 'sell',
                  'missed_opportunity': 'miss'}


def _as_date(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:19]).date()
        except ValueError:
            return None
    return None


class DecisionScoreService:
    def __init__(self, decision_repo=None, kline_repo=None,
                 bench_klines_provider: Optional[Callable] = None,
                 mature_window: int = 20):
        if decision_repo is None:
            from adapters.outbound.repositories.agent_intelligence_repository import (
                AgentIntelligenceORMRepository,
            )
            decision_repo = AgentIntelligenceORMRepository()
        if kline_repo is None:
            from adapters.outbound.repositories.kline_repository import KlineORMRepository
            kline_repo = KlineORMRepository()
        if bench_klines_provider is None:
            from application.services.benchmark_comparison import fetch_benchmark_klines
            bench_klines_provider = fetch_benchmark_klines
        self.decision_repo = decision_repo
        self.kline_repo = kline_repo
        self.bench_klines_provider = bench_klines_provider
        self.mature_window = mature_window

    def score_mature_decisions(self, pending_days: int = 1) -> Dict[str, Any]:
        """扫描 pending 决策并打分回写，返回计数汇总（供调度 run 记录）。"""
        pending = self.decision_repo.list_pending_evaluations(days=pending_days)
        result = {'scanned': 0, 'scored': 0, 'skipped_unmature': 0,
                  'skipped_invalid': 0, 'errors': 0}
        for decision in pending:
            action = SCORABLE_TYPES.get(decision.get('decision_type'))
            if action is None:
                continue
            result['scanned'] += 1
            try:
                outcome = self._score_one(decision, action)
            except Exception as e:
                logger.error(f"打分失败 {decision.get('decision_id')}: {e}")
                result['errors'] += 1
                continue
            if outcome == 'scored':
                result['scored'] += 1
            elif outcome == 'unmature':
                result['skipped_unmature'] += 1
            else:
                result['skipped_invalid'] += 1
        logger.info(f"决策打分完成: {result}")
        return result

    def _score_one(self, decision: Dict[str, Any], action: str) -> str:
        """单条决策打分。返回 'scored' | 'unmature' | 'invalid'。"""
        params = decision.get('parameters') or {}
        symbol = params.get('symbol')
        trade_price = params.get('price')
        trade_date = _as_date(decision.get('created_at'))
        if not symbol or not trade_price or trade_date is None:
            return 'invalid'

        today = date.today()
        df = self.kline_repo.get_daily_klines(
            symbol, start_date=trade_date.isoformat(), end_date=today.isoformat())
        if df is None or df.height == 0:
            return 'invalid'
        future = [r for r in df.iter_rows(named=True)
                  if _as_date(r['trade_date']) is not None
                  and _as_date(r['trade_date']) > trade_date]
        if len(future) < self.mature_window:
            return 'unmature'
        ref = future[self.mature_window - 1]
        ref_price = float(ref['close'])
        ref_date = _as_date(ref['trade_date'])

        bench_return, bench_missing = self._bench_return(trade_date, ref_date)
        scored = compute_trade_score(action, float(trade_price), ref_price, bench_return)

        detail = {
            'scorer': 'decision_score_p0a',
            'window_trading_days': self.mature_window,
            'trade_date': trade_date.isoformat(),
            'ref_date': ref_date.isoformat(),
            'trade_price': float(trade_price),
            'ref_price': ref_price,
            'benchmark': BENCHMARK_SYMBOL,
            'benchmark_missing': bench_missing,
            **scored,
        }
        written = self.decision_repo.update_score(
            decision['decision_id'], scored['score'], scored['band'], detail)
        if written is None:
            raise RuntimeError(f"打分回写失败: {decision['decision_id']}")
        return 'scored'

    def _bench_return(self, start: date, end: date):
        """基准区间收益。klines 为 akshare 风格 [{'date','close'}]；缺失降级 (0.0, True)。"""
        klines = self.bench_klines_provider(
            symbol=BENCHMARK_SYMBOL, start_date=start.isoformat(), end_date=end.isoformat())
        window = [k for k in klines
                  if _as_date(k.get('date')) is not None
                  and start <= _as_date(k.get('date')) <= end]
        if len(window) < 2:
            return 0.0, True
        return float(window[-1]['close']) / float(window[0]['close']) - 1.0, False
