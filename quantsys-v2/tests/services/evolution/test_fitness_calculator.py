"""双侧捕获适应度纯函数测试——合成行情，不碰 DB"""
import pytest

from application.services.evolution.fitness_calculator import (
    compute_capture, SIDEWAYS_THRESHOLD, MIN_SAMPLE_DAYS,
)


def _bench(days):
    """{date: bench_return}，days 为 [(day_int, return)]"""
    return {f'2026-07-{d:02d}': r for d, r in days}


class TestDayClassification:
    def test_up_down_sideways_split(self):
        # 10 涨日(+1%)、7 跌日(-1%)、3 横盘(±0.1%)
        days = [(i, 0.01) for i in range(1, 11)] + \
               [(i, -0.01) for i in range(11, 18)] + \
               [(i, 0.001) for i in range(18, 21)]
        bench = _bench(days)
        acct = {d: 0.012 for d in bench}  # 每天都挣 1.2%
        result = compute_capture(acct, bench, has_trades=True)
        assert result['status'] == 'ok'
        assert result['up_days'] == 10
        assert result['down_days'] == 7
        assert result['up_capture'] == pytest.approx(1.2)
        # 跌日账户也挣 1.2%（分母为负）→ down_capture = 0.012 / -0.01 = -1.2
        assert result['down_capture'] == pytest.approx(-1.2)
        assert result['fitness'] == pytest.approx(2.4)


class TestCaptureSemantics:
    def test_good_defense_beats_bad_offense(self):
        # 账户A：涨日跟上(1.0x)，跌日只亏一半(0.5x) → fitness = 1.0-0.5 = 0.5
        # 账户B：涨日冲 1.3x，跌日亏 1.6x → fitness = 1.3-1.6 = -0.3
        days = [(i, 0.01) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)]
        bench = _bench(days)
        a = compute_capture({d: (0.01 if r > 0 else -0.005) for d, r in bench.items()},
                            bench, has_trades=True)
        b = compute_capture({d: (0.013 if r > 0 else -0.016) for d, r in bench.items()},
                            bench, has_trades=True)
        assert a['fitness'] > b['fitness']

    def test_missing_account_days_skipped(self):
        # 账户缺 2 天 snapshot：只在交集上计算，样本计数随之减少
        days = [(i, 0.01) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)]
        bench = _bench(days)
        acct = {d: 0.01 for d, r in bench.items() if d not in ('2026-07-01', '2026-07-11')}
        result = compute_capture(acct, bench, has_trades=True)
        assert result['up_days'] == 9
        assert result['down_days'] == 6


class TestBoundaryStatus:
    def test_insufficient_sample_when_few_down_days(self):
        # 单边市：15 涨日 + 3 跌日（< MIN_SAMPLE_DAYS=5）
        days = [(i, 0.01) for i in range(1, 16)] + [(i, -0.01) for i in range(16, 19)]
        bench = _bench(days)
        result = compute_capture(bench, bench, has_trades=True)
        assert result['status'] == 'insufficient_sample'
        assert result['fitness'] is None
        assert result['down_days'] == 3

    def test_no_trades_account_excluded(self):
        days = [(i, 0.01) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)]
        bench = _bench(days)
        acct = {d: 0.0 for d in bench}  # 空仓收益恒 0
        result = compute_capture(acct, bench, has_trades=False)
        assert result['status'] == 'no_trades'
        assert result['fitness'] is None

    def test_sideways_threshold_boundary(self):
        assert abs(SIDEWAYS_THRESHOLD - 0.003) < 1e-9
        # +0.3% 恰为涨日，+0.29% 为横盘
        days = [(i, 0.003) for i in range(1, 11)] + [(i, -0.01) for i in range(11, 18)] + \
               [(18, 0.0029)]
        bench = _bench(days)
        acct = {d: 0.003 for d in bench}
        result = compute_capture(acct, bench, has_trades=True)
        assert result['up_days'] == 10

    def test_min_sample_days_constant(self):
        assert MIN_SAMPLE_DAYS == 5
