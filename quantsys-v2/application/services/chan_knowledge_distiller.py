"""缠论信号胜率蒸馏器

每周运行：取 [今-lookback, 今-window] 区间内的缠论信号（留 window 日验证窗），
对照 signal_date 后 window 个自然日附近实际收盘价，按 verify_judgments 一致规则
判定对错（buy & 涨 = 胜），按策略聚合成 agent_knowledge。

confidence 爬坡：<10 样本 → 0.3；10-30 → 0.5；>30 → 0.7。
"""
from domain.ports import IAgentKnowledgeRepository, IKlineRepository, ISignalRepository
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import structlog
from pandas import Timestamp as pd_timestamp, to_datetime as pd_to_datetime


logger = structlog.get_logger(__name__)


def _confidence_for(samples: int) -> float:
    if samples < 10:
        return 0.3
    if samples <= 30:
        return 0.5
    return 0.7


def _sig_get(signal, key):
    """信号字段访问：兼容 dict（测试）与 Signal ORM 对象（生产
    get_signals_by_date_range 返回 List[Signal]）"""
    if isinstance(signal, dict):
        return signal.get(key)
    return getattr(signal, key, None)


class ChanKnowledgeDistiller:
    """缠论信号胜率 → agent_knowledge

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        window_days: int = 20,
        lookback_days: int = 90,
        signal_repo: Optional[ISignalRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        knowledge_repo: Optional[IAgentKnowledgeRepository] = None,
    ):
        """初始化服务

        Args:
            window_days: 验证窗口天数
            lookback_days: 回溯天数
            signal_repo: 信号仓库（可选）
            kline_repo: K线仓库（可选）
            knowledge_repo: 知识仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        # 依赖模块顶部 import（同 ChanScanService，保证可 patch）
        self._signal_repo = signal_repo
        self._kline_repo = kline_repo
        self._knowledge_repo = knowledge_repo
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
        # 生产 kline repo 显式 schema 后日期列恒为 ISO 字符串，先归一为 datetime 再比较
        pdf[date_col] = pd_to_datetime(pdf[date_col])
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
                        if str(_sig_get(s, 'strategy_id') or '').startswith('chan_')
                        and _sig_get(s, 'action') in ('BUY', 'SELL')]  # 大写契约（08-13）

        stats: Dict[str, Dict[str, Any]] = {}
        excluded = 0
        for s in chan_signals:
            sig_date = _sig_get(s, 'signal_date')
            if isinstance(sig_date, str):
                sig_date = datetime.strptime(sig_date[:10], '%Y-%m-%d').date()
            ret = self._future_return(_sig_get(s, 'symbol'), sig_date)
            if ret is None:
                excluded += 1
                continue
            action = _sig_get(s, 'action')
            win = (ret > 0) if action == 'BUY' else (ret < 0)  # SELL & 跌 = 胜（大写契约 08-13）
            st = stats.setdefault(_sig_get(s, 'strategy_id'), {'wins': 0, 'returns': []})
            st['returns'].append(ret)
            if win:
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
