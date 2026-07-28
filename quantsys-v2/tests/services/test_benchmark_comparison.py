"""benchmark_comparison 纯计算测试"""
from application.services.benchmark_comparison import compute_benchmark_comparison


class TestComputeBenchmarkComparison:
    def setup_method(self):
        # 账户日收益（升序）：+1%、0%、-1%
        self.account = [
            ("2026-07-01", 0.01, 101000.0),
            ("2026-07-02", 0.0, 101000.0),
            ("2026-07-03", -0.01, 99990.0),
        ]
        # 基准收盘：100 → 101（+1%）→ 100（≈-0.99%）
        self.bench = [
            {"date": "2026-06-30", "close": 100.0},
            {"date": "2026-07-01", "close": 100.0},
            {"date": "2026-07-02", "close": 101.0},
            {"date": "2026-07-03", "close": 100.0},
        ]

    def test_account_and_benchmark_returns(self):
        r = compute_benchmark_comparison(self.account, self.bench)
        assert r is not None
        # 账户区间收益：(1.01*1.0*0.99)-1 ≈ -0.0001
        assert abs(r["account_return_1m"] - (-0.0001)) < 1e-6
        # 基准同期收益：100→100 = 0（用窗口首末收盘）
        assert abs(r["benchmark_return_1m"] - 0.0) < 1e-6
        # 超额 = 账户 - 基准
        assert abs(r["excess_return_1m"] - (r["account_return_1m"] - r["benchmark_return_1m"])) < 1e-9

    def test_alpha_beta_sharpe_present_with_enough_data(self):
        account = [(f"2026-07-{d:02d}", 0.001 * (d % 3 - 1), 100000.0) for d in range(1, 11)]
        bench = [{"date": f"2026-07-{d:02d}", "close": 100.0 + d * 0.1} for d in range(0, 11)]
        r = compute_benchmark_comparison(account, bench)
        assert r["alpha"] is not None
        assert r["beta"] is not None
        assert r["sharpe"] is not None
        assert r["aligned_days"] >= 5

    def test_metrics_none_when_too_few_aligned_days(self):
        account = [("2026-07-01", 0.01, 101000.0), ("2026-07-02", 0.0, 101000.0)]
        bench = [{"date": "2026-07-01", "close": 100.0}, {"date": "2026-07-02", "close": 101.0}]
        r = compute_benchmark_comparison(account, bench)
        assert r is not None
        assert r["alpha"] is None
        assert r["sharpe"] is None

    def test_returns_none_when_no_overlap(self):
        account = [("2026-07-01", 0.01, 101000.0)]
        bench = [{"date": "2025-01-01", "close": 100.0}]
        assert compute_benchmark_comparison(account, bench) is None

    def test_benchmark_klines_unordered_input_ok(self):
        shuffled = [self.bench[2], self.bench[0], self.bench[3], self.bench[1]]
        r = compute_benchmark_comparison(self.account, shuffled)
        assert r is not None
        assert abs(r["benchmark_return_1m"] - 0.0) < 1e-6
