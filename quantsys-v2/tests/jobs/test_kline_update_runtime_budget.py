"""K线全市场回补必须有墙钟预算（2026-10-21 w-36c3225e）。

事故背景（实测）：kline_update scope=all 要处理 5277 只，按 interval
0.3~0.8s 限速 + 每只一次同步 HTTP，实测约 1.7s/只 ⇒ **单次约 2.5 小时**。
后果：① 进程重启后从头再来；② 长时间占住 worker 线程与 DB 连接；
③ 上游中途限流则本次成果全部作废。

修复：加 `max_runtime_sec` 墙钟预算（默认 1800s），到点收工并**如实**报
`budget_exhausted=True` + `attempted=N`（部分完成），下一轮按陈旧度续跑。

本文件守三件事：
  1. 预算到点即停（不再无限跑）；
  2. 部分完成**如实上报**（不报成"全量完成"的假成功）；
  3. 不传预算 / 传 0 时行为不变（不限时，调试用）。
"""
import time

import pytest

from qs_ops.infrastructure.jobs import kline_update_job as kuj


class _FakeRepo:
    """KlineSyncRepository 的最小替身。"""

    def __init__(self, universe):
        self._universe = universe
        self.upserts = []

    def select_sync_universe(self, scope, symbols, batch_size):
        return list(self._universe)

    def upsert_fetched_klines(self, symbol, klines):
        self.upserts.append(symbol)
        return len(klines)

    # 下面这些自检方法在预算到点的早退路径上也会被调用，必须给得出结果
    def count_missing_amount(self, trade_date):
        return 0

    def detect_amount_scale_anomalies(self, trade_date):
        return []

    def detect_volume_unit_anomalies(self, trade_date):
        return []


class _FakeKline:
    def __init__(self, date):
        self.date = date
        self.open = self.high = self.low = self.close = 1.0
        self.volume = 100.0
        self.amount = 100.0
        self.source = "fake"


@pytest.fixture
def patched(monkeypatch):
    """把 update_gem_klines 的外部依赖全部替掉，只测循环与预算逻辑。"""
    universe = [(f"{600000 + i:06d}", f"S{i}") for i in range(60)]

    repo = _FakeRepo(universe)
    monkeypatch.setattr(kuj, "KlineSyncRepository", lambda: repo)

    class _FakeManager:
        def get_klines(self, symbol, period, start_date, end_date):
            # 每只故意慢一点，确保预算能在有限只数内触发
            time.sleep(0.02)
            return {"success": True, "data": [_FakeKline("2026-10-21")]}

    monkeypatch.setattr(kuj, "DataProviderManager", lambda: _FakeManager())

    # 交易日语境：让 target_date 落在 2026-10-21
    class _Guard:
        @staticmethod
        def is_trading_day(d):
            return True

    monkeypatch.setattr(
        "qs_ops.application.services.trading_day_guard.TradingDayGuard", _Guard
    )
    return repo


# ==================== 预算生效 ====================


def test_budget_stops_the_run_and_reports_partial(patched):
    """预算到点即停，并如实报 budget_exhausted / attempted。"""
    result = kuj.update_gem_klines(
        scope="all", days=5, interval_seconds=0, max_runtime_sec=0.3
    )

    assert result["status"] == "success"
    assert result["budget_exhausted"] is True, "预算到点必须如实标记"
    assert result["attempted"] < 60, f"应在跑完 60 只之前收工，实际 {result['attempted']}"
    assert result["attempted"] > 0, "至少应处理过几只"
    assert "部分完成" in result["message"]


def test_budget_does_not_trigger_when_time_is_sufficient(patched):
    """预算充足时正常跑完，不误报部分完成。"""
    result = kuj.update_gem_klines(
        scope="all", days=5, interval_seconds=0, max_runtime_sec=600
    )

    assert result["budget_exhausted"] is False
    assert result["attempted"] == 60
    assert result["success"] == 60


def test_zero_budget_means_unlimited(patched):
    """传 0 = 不限时（调试口径），行为与旧版一致。"""
    result = kuj.update_gem_klines(
        scope="all", days=5, interval_seconds=0, max_runtime_sec=0
    )

    assert result["budget_exhausted"] is False
    assert result["attempted"] == 60


def test_default_budget_is_applied_when_not_given(patched):
    """不传 max_runtime_sec 时用默认常量（与 data_quality_check 同口径）。"""
    assert kuj.DEFAULT_MAX_RUNTIME_SEC == 1800
    result = kuj.update_gem_klines(scope="all", days=5, interval_seconds=0)

    assert result["max_runtime_sec"] == kuj.DEFAULT_MAX_RUNTIME_SEC
    assert result["budget_exhausted"] is False  # 60 只跑得完


# ==================== 故障注入护栏 ====================
#
# 若有人把预算检查删掉，test_budget_stops_the_run_and_reports_partial 会失败
# （assert result["budget_exhausted"] is True）。这里再补一条"时间确实被
# 尊重"的断言，确保不是靠别的巧合让测试通过。


def test_budget_actually_bounds_wall_clock(patched):
    """墙钟预算必须真的约束执行时长（不是只报个标记）。"""
    t0 = time.monotonic()
    result = kuj.update_gem_klines(
        scope="all", days=5, interval_seconds=0, max_runtime_sec=0.3
    )
    elapsed = time.monotonic() - t0

    assert result["budget_exhausted"] is True
    # 超支窗口 = 检查粒度 × 单只耗时（实测单只约 0.09s，粒度 10 ⇒ ≤0.9s）。
    # 预算 0.3s 很小，绝对阈值只能取"跑完全部 60 只"的零头才有意义：
    # 全部跑完约 5.3s，故 2.5s 是个能区分"预算生效"与"预算失效"的中间线。
    assert elapsed < 2.5, f"预算未真正生效，耗时 {elapsed:.2f}s（跑完 60 只约需 5.3s）"


def test_budget_overshoot_is_bounded_by_check_granularity(patched):
    """超支窗口必须与检查粒度相称（防止"预算形同虚设"）。

    固定按 25 只检查时，超支可达 25 × 单只耗时 ≈ 2.2s——对 0.3s 的预算是
    7 倍超支，等于没有约束。本用例把这条约束钉住。
    """
    t0 = time.monotonic()
    result = kuj.update_gem_klines(
        scope="all", days=5, interval_seconds=0, max_runtime_sec=0.3
    )
    elapsed = time.monotonic() - t0

    assert result["budget_exhausted"] is True
    # 允许的超支 = 粒度 × 单只实测耗时 + 余量。粒度取 10，单只 ~0.09s
    # ⇒ 理论超支 ≤0.9s，留 0.6s 余量做断言上限。
    assert elapsed <= 0.3 + 1.5, (
        f"超支 {elapsed - 0.3:.2f}s 远超检查粒度允许的窗口——预算形同虚设"
    )
