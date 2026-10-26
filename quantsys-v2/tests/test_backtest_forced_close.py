"""
REQ-261020014122-d659 FR-1/FR-2/FR-4：回测窗口末强制平仓计账与判据口径字段

缺陷背景（连续 4 周复现）：run_backtest_from_signals 的 trades 只在 SELL 分支 append，
窗口结束不强制平仓 → 「开仓未平仓」的回测 total_trades=0 → 进化判据 MIN_TRADES=1
误读为「窗口无信号」。实证：策略 202/002007 一年窗 equity 1000000→768184（仍持仓），
totalTrades=0。

用例（design/test-cases.md）：
- C1 故障注入·开窗未平仓：断言强制平仓计账与口径字段
- C2 回归·真无信号：判据对真空窗仍降级，语义不被稀释
- C3 回归·正常往返：旧字段形状不变（普通条目无 forced_close 键）

构造方式：直接构造 signals_df，不依赖数据库与行情源。
"""
import pandas as pd
import pytest

from qs_strategy.application.services.strategy_backtest_service import StrategyBacktestService


def _make_df(closes, buy_days=(), sell_days=(), buy_pct=0.5, sell_pct=1.0):
    """构造信号 DataFrame：closes 为收盘价序列，buy_days/sell_days 为触发下标。"""
    n = len(closes)
    dates = [f'2026-01-{i + 1:02d}' for i in range(n)]
    df = pd.DataFrame({
        'trade_date': dates,
        'close': closes,
        'buy_tier1': [i in buy_days for i in range(n)],
        'buy_tier1_pct': [buy_pct if i in buy_days else 0.0 for i in range(n)],
        'sell_tier1': [i in sell_days for i in range(n)],
        'sell_tier1_pct': [sell_pct if i in sell_days else 0.0 for i in range(n)],
    })
    return df


@pytest.fixture
def service():
    return StrategyBacktestService()


class TestForcedCloseAtWindowEnd:
    """C1 故障注入：开仓后窗口结束仍未平仓"""

    def test_open_position_force_closed_and_counted(self, service):
        closes = [10.0, 10.5, 11.0, 10.8, 11.2, 11.5]
        df = _make_df(closes, buy_days={0}, buy_pct=0.5)

        metrics = service.run_backtest_from_signals(df, initial_cash=1000000)

        assert metrics['total_trades'] == 1
        assert metrics['forced_closes'] == 1
        assert metrics['open_position_at_end'] is True

        trade = metrics['trades'][0]
        assert trade['forced_close'] is True
        assert trade['exit_price'] == pytest.approx(11.5)  # 末日收盘价
        assert trade['exit_date'] == '2026-01-06'          # 末日日期
        assert trade['entry_date'] == '2026-01-01'
        assert trade['shares'] > 0
        # pnl 口径：不计卖出费，与权益曲线口径一致
        expected_pnl = trade['shares'] * (trade['exit_price'] - trade['entry_price'])
        assert trade['pnl'] == pytest.approx(expected_pnl, rel=1e-9)

        # 流水同样带标记
        forced_records = [r for r in metrics['trade_records'] if r.get('forced_close')]
        assert len(forced_records) == 1
        assert forced_records[0]['action'] == 'sell'

    def test_c2_no_signal_stays_zero(self, service):
        """C2 回归·真无信号：判据语义不被新逻辑稀释"""
        df = _make_df([10.0, 10.1, 10.2, 10.3, 10.4])

        metrics = service.run_backtest_from_signals(df, initial_cash=1000000)

        assert metrics['total_trades'] == 0
        assert metrics['forced_closes'] == 0
        assert metrics['open_position_at_end'] is False
        assert metrics['trades'] == []

    def test_c3_normal_roundtrip_unchanged(self, service):
        """C3 回归·正常往返：total_trades 语义不变，普通条目无 forced_close 键"""
        closes = [10.0, 10.5, 11.0, 10.8, 11.2]
        df = _make_df(closes, buy_days={0}, sell_days={2}, buy_pct=1.0, sell_pct=1.0)

        metrics = service.run_backtest_from_signals(df, initial_cash=1000000)

        assert metrics['total_trades'] == 1
        assert metrics['forced_closes'] == 0
        assert metrics['open_position_at_end'] is False
        assert 'forced_close' not in metrics['trades'][0]
        assert metrics['trades'][0]['exit_date'] == '2026-01-03'
