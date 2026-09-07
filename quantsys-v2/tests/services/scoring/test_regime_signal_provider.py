"""RegimeSignalProvider 单元测试"""
import pytest
import pandas as pd
from application.services.scoring.regime_signal_provider import RegimeSignalProvider


class FakeCache:
    def __init__(self):
        self.store = {}
    def get(self, ns, key):
        return self.store.get((ns, key))
    def set(self, ns, key, value, ttl=None):
        self.store[(ns, key)] = value
        return True


class FakeKlineRepo:
    def __init__(self, klines):
        self._klines = klines
    def batch_get_recent_klines(self, symbols, days=150):
        return {s: self._klines for s in symbols}


def _uptrend_klines(n=150):
    """稳定上涨序列"""
    return [{'trade_date': f'2026-01-{(i % 28) + 1:02d}', 'open': 100 + i,
             'high': 101 + i, 'low': 99 + i, 'close': 100.5 + i,
             'volume': 1000000 * (1 + i / n)} for i in range(n)]


class TestSignals:
    def test_uptrend_high_trend_strength(self):
        """单边上涨 → 信号在合法范围、label 有效"""
        p = RegimeSignalProvider(FakeKlineRepo(_uptrend_klines()),
                                 cache=FakeCache())
        sig = p.get_signals()
        assert sig['label'] in ('bull', 'bear', 'sideways')
        assert 0 <= sig['trend_strength'] <= 1
        assert 0 <= sig['market_risk'] <= 1
        assert 0 <= sig['liquidity_heat'] <= 1

    def test_insufficient_data_returns_default(self):
        """指数K线不足 → 兜底 sideways 不调整"""
        p = RegimeSignalProvider(FakeKlineRepo([]), cache=FakeCache())
        sig = p.get_signals()
        assert sig == RegimeSignalProvider.DEFAULT_SIGNALS

    def test_error_returns_default(self):
        class BoomRepo:
            def batch_get_recent_klines(self, symbols, days=150):
                raise RuntimeError('db down')
        p = RegimeSignalProvider(BoomRepo(), cache=FakeCache())
        assert p.get_signals() == RegimeSignalProvider.DEFAULT_SIGNALS

    def test_cache_hit_skips_repo(self):
        """第二次调用走缓存，不再查库"""
        repo = FakeKlineRepo(_uptrend_klines())
        cache = FakeCache()
        p = RegimeSignalProvider(repo, cache=cache)
        p.get_signals()
        repo._klines = []  # 改数据，若走缓存结果不变
        sig2 = p.get_signals()
        assert sig2 != RegimeSignalProvider.DEFAULT_SIGNALS

    def test_no_cache_forces_recompute(self):
        repo = FakeKlineRepo(_uptrend_klines())
        cache = FakeCache()
        p = RegimeSignalProvider(repo, cache=cache)
        p.get_signals()
        repo._klines = []
        assert p.get_signals(no_cache=True) == RegimeSignalProvider.DEFAULT_SIGNALS


class TestDetectorDataframeMethod:
    def test_detect_from_dataframe(self):
        """MarketRegimeDetector 新增公共方法：直接接受 DataFrame"""
        from application.services.market_regime_detector import MarketRegimeDetector
        df = pd.DataFrame(_uptrend_klines()).rename(
            columns={'trade_date': 'date'})
        detector = MarketRegimeDetector()
        result = detector.detect_from_dataframe(df)
        assert result['regime'] in ('bull', 'bear', 'sideways')
        assert 'signals' in result
        assert 'adx' in result['signals']
