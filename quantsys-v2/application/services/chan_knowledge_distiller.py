"""缠论信号胜率蒸馏器

每周运行：取 [今-lookback, 今-window] 区间内的缠论信号（留 window 日验证窗），
对照 signal_date 后 window 个自然日附近实际收盘价，按 verify_judgments 一致规则
判定对错（buy & 涨 = 胜），按策略聚合成 agent_knowledge。

confidence 爬坡：<10 样本 → 0.3；10-30 → 0.5；>30 → 0.7。
"""
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import structlog
from pandas import Timestamp as pd_timestamp

from adapters.outbound.repositories.signal_repository import SignalORMRepository
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories.agent_knowledge_repository import AgentKnowledgeORMRepository

logger = structlog.get_logger(__name__)


def _confidence_for(samples: int) -> float:
    if samples < 10:
        return 0.3
    if samples <= 30:
        return 0.5
    return 0.7


class ChanKnowledgeDistiller:
    """缠论信号胜率 → agent_knowledge"""

    def __init__(self, window_days: int = 20, lookback_days: int = 90):
        # 依赖模块顶部 import（同 ChanScanService，保证可 patch）
        self._signal_repo = SignalORMRepository()
        self._kline_repo = KlineORMRepository()
        self._knowledge_repo = AgentKnowledgeORMRepository()
        self._window = window_days
        self._lookback = lookback_days

    def _future_return(self, symbol: str, signal_date: date) -> Optional[float]:
        """signal_date 收盘 → signal_date+window 附近收盘的收益率；数据不足返回 None"""
        end = signal_date + timedelta(days=self._window + 10)  # 余量覆盖非交易日
        df = self._kline_repo.get_daily_klines(
            symbol=symbol,
            start_date=signal_date.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
        )
        if df.is_empty() or df.height < 2:
            return None
        pdf = df.to_pandas()
        date_col = 'date' if 'date' in pdf.columns else 'trade_date'
        pdf = pdf.sort_values(date_col)
        base_close = float(pdf.iloc[0]['close'])
        target = pdf[pdf[date_col] >= pd_timestamp(signal_date + timedelta(days=self._window))]
        if target.empty:
            return None  # 验证窗还没走完
        future_close = float(target.iloc[0]['close'])
        if base_close == 0:
            return None
        return (future_close - base_close) / base_close

    def distill(self) -> Dict[str, Any]:
        today = date.today()
        start = (today - timedelta(days=self._lookback)).strftime('%Y-%m-%d')
        end = (today - timedelta(days=self._window)).strftime('%Y-%m-%d')

        all_signals = self._signal_repo.get_signals_by_date_range(start, end)
        chan_signals = [s for s in all_signals
                        if str(s.get('strategy_id', '')).startswith('chan_')
                        and s.get('action') == 'buy']

        stats: Dict[str, Dict[str, Any]] = {}
        excluded = 0
        for s in chan_signals:
            sig_date = s['signal_date']
            if isinstance(sig_date, str):
                sig_date = datetime.strptime(sig_date[:10], '%Y-%m-%d').date()
            ret = self._future_return(s['symbol'], sig_date)
            if ret is None:
                excluded += 1
                continue
            st = stats.setdefault(s['strategy_id'], {'wins': 0, 'returns': []})
            st['returns'].append(ret)
            if ret > 0:  # buy & 涨 = 胜（与 verify_judgments 一致；0 不计胜）
                st['wins'] += 1

        for strategy_id, st in stats.items():
            samples = len(st['returns'])
            win_rate = st['wins'] / samples
            avg_return = sum(st['returns']) / samples
            self._knowledge_repo.upsert_knowledge(
                knowledge_id=f"chan_{strategy_id}_{self._window}d",
                domain='chan_theory',
                knowledge_type='signal_effectiveness',
                content={
                    'strategy': strategy_id,
                    'window': self._window,
                    'win_rate': round(win_rate, 4),
                    'avg_return': round(avg_return, 4),
                    'samples': samples,
                    'period_start': start,
                    'period_end': end,
                    'note': '样本不足，参考意义弱' if samples < 10 else '',
                },
                confidence=_confidence_for(samples),
                validation_count=samples,
                success_count=st['wins'],
            )
            logger.info(f"蒸馏 {strategy_id}: 胜率 {win_rate:.1%}（{samples} 样本）")

        return {
            'strategies_distilled': len(stats),
            'signals_total': len(chan_signals),
            'signals_excluded': excluded,
        }
