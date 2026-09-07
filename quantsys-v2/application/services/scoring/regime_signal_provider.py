"""
Regime 连续信号提供者

把 MarketRegimeDetector 的离散判定升级为评分可用的连续信号（0-1）：
- trend_strength: ADX/50 截断        → 驱动技术面权重
- market_risk:    波动率+空头排列+价格位置 → 驱动基本面权重
- liquidity_heat: 指数量能比截断      → 驱动资金面权重

缓存 30 分钟；任何失败回退 DEFAULT_SIGNALS（sideways，不调整），不抛异常。
"""
from typing import Dict, Any, Optional
import logging
import pandas as pd

from application.services.market_regime_detector import MarketRegimeDetector
from infrastructure.cache.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class RegimeSignalProvider:
    """regime 连续信号 + 缓存 + 兜底"""

    NAMESPACE = 'scoring'
    CACHE_KEY = 'regime_signals'
    TTL_SECONDS = 1800  # 30 分钟

    DEFAULT_SIGNALS: Dict[str, Any] = {
        'label': 'sideways',
        'trend_strength': 0.5,
        'market_risk': 0.4,
        'liquidity_heat': 0.5,
    }

    def __init__(self, kline_repo, detector=None, cache=None,
                 index_symbol: str = '000001.SH'):
        self.kline_repo = kline_repo
        self.detector = detector or MarketRegimeDetector()
        self.cache = cache or get_cache_service()
        self.index_symbol = index_symbol

    def get_signals(self, no_cache: bool = False) -> Dict[str, Any]:
        """获取 regime 连续信号（带 30min 缓存，失败兜底 sideways）"""
        if not no_cache:
            cached = self.cache.get(self.NAMESPACE, self.CACHE_KEY)
            if cached is not None:
                return cached
        signals = self._compute()
        if signals != self.DEFAULT_SIGNALS:
            self.cache.set(self.NAMESPACE, self.CACHE_KEY, signals,
                           self.TTL_SECONDS)
        return signals

    def _compute(self) -> Dict[str, Any]:
        try:
            klines_map = self.kline_repo.batch_get_recent_klines(
                [self.index_symbol], days=150)
            klines = klines_map.get(self.index_symbol) or []
            if len(klines) < 120:
                logger.warning(f'指数K线不足({len(klines)}条)，regime 兜底 sideways')
                return dict(self.DEFAULT_SIGNALS)

            df = pd.DataFrame(klines).rename(columns={'trade_date': 'date'})
            for col in ('open', 'high', 'low', 'close', 'volume'):
                df[col] = df[col].astype(float)
            result = self.detector.detect_from_dataframe(df)
            signals = self._to_continuous(result, df)
            return signals
        except Exception as e:
            logger.error(f'regime 信号计算失败: {e}')
            return dict(self.DEFAULT_SIGNALS)

    def _to_continuous(self, result: Dict[str, Any],
                       df: pd.DataFrame) -> Dict[str, Any]:
        s = result.get('signals', {})

        trend_strength = min(float(s.get('adx', 0)) / 50.0, 1.0)

        vol = float(s.get('volatility', 0.20))
        ma = s.get('ma_arrangement', 'mixed')
        ma_risk = {'bearish': 1.0, 'mixed': 0.5}.get(ma, 0.0)
        price_pos = float(s.get('price_position', 0.5))
        market_risk = (0.5 * min(vol / 0.30, 1.0)
                       + 0.3 * ma_risk
                       + 0.2 * (1.0 - price_pos))

        liquidity_heat = self._volume_heat(df)

        return {
            'label': result.get('regime', 'sideways'),
            'trend_strength': round(trend_strength, 4),
            'market_risk': round(min(market_risk, 1.0), 4),
            'liquidity_heat': round(liquidity_heat, 4),
        }

    @staticmethod
    def _volume_heat(df: pd.DataFrame) -> float:
        """指数量能热度：近 5 日均量 / 前 20 日均量，截断 [0,2] 后 /2"""
        try:
            if len(df) < 25:
                return 0.5
            recent5 = df['volume'].iloc[-5:].mean()
            prev20 = df['volume'].iloc[-25:-5].mean()
            if prev20 <= 0:
                return 0.5
            return min(recent5 / prev20, 2.0) / 2.0
        except Exception:
            return 0.5
