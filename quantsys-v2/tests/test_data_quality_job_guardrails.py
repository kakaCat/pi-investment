"""任务 232（每日数据质量检查）护栏测试 — 2026-09-11 w-23c70356

覆盖三类已实证缺陷：
1. 参数键漂移：配置 days/stock_limit 与实现 check_days/symbols_limit 不一致，配置静默失效
   （run 3527 日志 "日期范围 30 天 / 股票限制 全部"，配置的 365 天与 100 只均未生效）
2. 无墙钟预算：run 3391 空转 2.8 小时（backfill 失败率 100% 仍重试）
3. 回填全灭未如实标注：run 3480/3504 失败 98%/100%，调度器仍记 success
"""
import pytest

from infrastructure.jobs import data_quality_check_job as job
from application.services.data_quality_service import DataQualityService, RETRY_SKIP_FAIL_RATE


# ── 参数归一 ──────────────────────────────────────────────────────────────

def test_param_alias_days_and_stock_limit():
    eff, notes = job._normalize_params({"days": 365, "stock_limit": 100})
    assert eff["check_days"] == job.MAX_CHECK_DAYS, "365 天须被钳制到上限"
    assert eff["symbols_limit"] == 100
    assert any("days=365" in n for n in notes)
    assert any("stock_limit=100" in n for n in notes)
    assert any("钳制" in n for n in notes)


def test_param_defaults_when_empty():
    eff, notes = job._normalize_params({})
    assert eff["check_days"] == job.DEFAULT_CHECK_DAYS == 30
    assert eff["symbols_limit"] is None
    assert eff["auto_backfill"] is False
    assert eff["max_runtime_sec"] == job.DEFAULT_MAX_RUNTIME_SEC
    assert notes == []


def test_check_all_stocks_overrides_symbols_limit():
    eff, notes = job._normalize_params({"check_all_stocks": True, "stock_limit": 100})
    assert eff["symbols_limit"] is None
    assert any("check_all_stocks" in n for n in notes)


def test_invalid_values_fall_back_with_notes():
    eff, notes = job._normalize_params({"check_days": "abc", "max_runtime_sec": "xyz"})
    assert eff["check_days"] == job.DEFAULT_CHECK_DAYS
    assert eff["max_runtime_sec"] == job.DEFAULT_MAX_RUNTIME_SEC
    assert len(notes) >= 2


# ── 预算 / 额度 / 诚实标注（fake service，无网络无 DB）─────────────────────

class FakeService:
    """记录调用参数的假服务：模拟 10 只问题股票，回填结果可控"""

    def __init__(self, issues=None, backfill_summary=None, retry_skipped=None,
                 check_truncated=False):
        self.check_truncated = check_truncated
        self.check_kwargs = {}
        self.issues = issues if issues is not None else [
            {"symbol": f"60000{i}", "missing_days_count": i} for i in range(1, 11)
        ]
        self.backfill_summary = backfill_summary or {
            "total_stocks": 3, "success_count": 3, "failed_count": 0,
            "total_days_filled": 9, "elapsed_time": 1.0,
        }
        self.retry_skipped = retry_skipped
        self.backfill_symbols = None

    def _get_hot_stocks(self, limit=None):
        return ["600000", "000001", "600519"]

    def check_data_quality(self, symbols=None, start_date=None, end_date=None,
                           include_report=False, deadline=None):
        self.check_kwargs = {"deadline": deadline, "include_report": include_report}
        summary = {
            "total_stocks": len(symbols or []),
            "stocks_with_issues": len(self.issues),
            "total_missing_days": 55,
            "avg_coverage_rate": 70.0,
            "data_quality_score": 82.41,
            "checked_stocks": len(symbols or []),
            "skipped_stocks": 0,
            "check_truncated": self.check_truncated,
        }
        return {
            "success": True,
            "summary": summary,
            "stocks_with_issues": self.issues,
        }

    def backfill_missing_data(self, symbols=None, start_date=None, end_date=None, mode="auto", max_workers=8):
        self.backfill_symbols = list(symbols or [])
        return {"success": True, "summary": self.backfill_summary,
                "retry_skipped_reason": self.retry_skipped}


@pytest.fixture
def patch_job(monkeypatch):
    """替换服务与告警（告警会连库），返回注入 fake 的工厂"""
    monkeypatch.setattr(job, "_check_quality_alerts", lambda *a, **k: None)
    holder = {}

    def _install(svc):
        holder["svc"] = svc
        monkeypatch.setattr(job, "DataQualityService", lambda *a, **k: svc)
        return svc

    return _install


def test_budget_insufficient_skips_backfill(patch_job):
    svc = patch_job(FakeService())
    res = job.daily_data_quality_check(
        check_days=5, auto_backfill=True, max_runtime_sec=1
    )
    assert svc.backfill_symbols is None, "预算不足时必须跳过回填"
    assert res["timed_out"] is True
    assert res["backfill_executed"] is False
    assert "剩余预算" in (res["backfill_skip_reason"] or "")


def test_backfill_limited_to_top_missing_and_capped(patch_job):
    svc = patch_job(FakeService())
    res = job.daily_data_quality_check(
        check_days=5, auto_backfill=True, max_backfill_symbols=3, max_runtime_sec=100000
    )
    assert res["budget_limited"] is True
    assert len(svc.backfill_symbols) == 3
    # 缺失天数最多的优先（issues 中 6000010 的 missing_days_count=10）
    assert svc.backfill_symbols[0] == "6000010"
    assert res["effective_params"]["max_backfill_symbols"] == 3


def test_backfill_degraded_flagged_when_all_fail(patch_job):
    svc = patch_job(FakeService(backfill_summary={
        "total_stocks": 5, "success_count": 0, "failed_count": 5,
        "total_days_filled": 0, "elapsed_time": 12.0,
    }))
    res = job.daily_data_quality_check(
        check_days=5, auto_backfill=True, max_runtime_sec=100000
    )
    assert res["backfill_degraded"] is True, "回填全灭必须如实标注，不能伪装成成功"
    assert res["backfill_executed"] is True


def test_result_carries_effective_params_and_runtime(patch_job):
    patch_job(FakeService())
    res = job.daily_data_quality_check(
        days=7, stock_limit=50, auto_backfill=False
    )
    assert res["effective_params"]["check_days"] == 7
    assert res["effective_params"]["symbols_limit"] == 50
    assert res["runtime_sec"] >= 0
    assert any("days=7" in n for n in res["param_notes"])


# ── 回填重试熔断（真实 DataQualityService + 假依赖）────────────────────────

class FakeValidator:
    def __init__(self):
        self.calls = 0

    def detect_duplicates(self, symbol, start_date=None, end_date=None):
        self.calls += 1
        return {"has_duplicates": False, "duplicate_count": 0}

    def detect_anomalies(self, symbol, start_date=None, end_date=None):
        return {"has_anomalies": False, "total_anomalies": 0}

    def get_data_quality_score(self, symbol=None, start_date=None, end_date=None,
                               coverage_rate=None):
        return 90.0


class FakeGapDetector:
    def detect_gaps_batch(self, symbols=None, start_date=None, end_date=None, only_with_gaps=True):
        return {s: {"missing_segments": [{"start": start_date, "end": end_date, "days": 1}],
                    "missing_days_count": 1, "coverage_rate": 90.0}
                for s in (symbols or [])}

    def get_gap_summary(self, gaps=None):
        return {"total_missing_days": len(gaps or {}), "avg_coverage_rate": 90.0}


class FakeBackfiller:
    def __init__(self, fail_ratio=1.0):
        self.fail_ratio = fail_ratio
        self.retry_called = False

    def backfill_batch(self, backfill_tasks=None, max_workers=8):
        total = len(backfill_tasks or {})
        failed = int(total * self.fail_ratio)
        return {
            "total_stocks": total,
            "success_count": total - failed,
            "failed_count": failed,
            "failed_symbols": list(backfill_tasks or {})[:failed],
            "total_days_filled": 0,
            "elapsed_time": 0.5,
        }

    def retry_failed(self, tasks=None, max_retries=5):
        self.retry_called = True
        return {"success_count": 0, "failed_count": len(tasks or {}),
                "total_days_filled": 0, "failed_symbols": list(tasks or {})}


def _make_service(backfiller):
    return DataQualityService(
        kline_repo=object(), calendar=object(),
        gap_detector=FakeGapDetector(), backfiller=backfiller, validator=object(),
    )


def test_backfill_retry_skipped_when_source_dead():
    """故障注入：数据源整体不可用（失败率 100%）时不得再重试 5 轮"""
    backfiller = FakeBackfiller(fail_ratio=1.0)
    svc = _make_service(backfiller)
    res = svc.backfill_missing_data(symbols=["600000", "000001"], mode="auto")
    assert backfiller.retry_called is False, "失败率 >= 阈值必须跳过重试轮"
    assert res["summary"]["failed_count"] == 2
    assert "跳过" in (res.get("retry_skipped_reason") or "")


def test_backfill_retry_still_runs_on_partial_failure():
    """失败率低于阈值时保留原有重试行为（不误伤正常回填）"""
    backfiller = FakeBackfiller(fail_ratio=0.0)
    backfiller.backfill_batch = lambda backfill_tasks=None, max_workers=8: {
        "total_stocks": 10, "success_count": 9, "failed_count": 1,
        "failed_symbols": ["600000"], "total_days_filled": 4, "elapsed_time": 1.0,
    }
    svc = _make_service(backfiller)
    res = svc.backfill_missing_data(symbols=[f"60000{i}" for i in range(10)], mode="auto")
    assert backfiller.retry_called is True
    assert RETRY_SKIP_FAIL_RATE == 0.8


# ── 检查阶段墙钟护栏（真实 service + 假依赖 + 真实日志）──────────────────

def test_job_passes_check_deadline_reserving_backfill_budget(patch_job):
    """检查阶段必须收到截止时间（= 起始 + 预算 - 回填保留），否则"加超时"只盖住回填"""
    import time
    svc = patch_job(FakeService(check_truncated=True))
    t0 = time.monotonic()
    res = job.daily_data_quality_check(
        check_days=5, auto_backfill=True, max_runtime_sec=900
    )
    dl = svc.check_kwargs["deadline"]
    assert dl is not None
    assert t0 + 900 - job.MIN_BACKFILL_BUDGET_SEC <= dl <= time.monotonic() + 900
    assert res["check_truncated"] is True


def test_service_check_truncates_on_deadline(monkeypatch):
    """故障/超预算路径：超出截止即停止逐只扫描，如实标注，且不再写审计"""
    import time
    monkeypatch.setattr(DataQualityService, "_persist_quality_audit", lambda self, **kw: None)
    validator = FakeValidator()
    svc = DataQualityService(kline_repo=object(), calendar=object(),
                             gap_detector=FakeGapDetector(), backfiller=FakeBackfiller(),
                             validator=validator)
    symbols = [f"60000{i}" for i in range(5)]
    res = svc.check_data_quality(symbols=symbols, start_date="2026-09-01",
                                 end_date="2026-09-05", deadline=time.monotonic() - 0.001)
    assert res["success"] is True
    assert res["summary"]["check_truncated"] is True
    assert res["summary"]["checked_stocks"] == 0
    assert res["summary"]["skipped_stocks"] == 5
    assert validator.calls == 0, "超预算后不得继续逐只扫描"


def test_service_check_completes_without_deadline(monkeypatch):
    monkeypatch.setattr(DataQualityService, "_persist_quality_audit", lambda self, **kw: None)
    validator = FakeValidator()
    svc = DataQualityService(kline_repo=object(), calendar=object(),
                             gap_detector=FakeGapDetector(), backfiller=FakeBackfiller(),
                             validator=validator)
    res = svc.check_data_quality(symbols=[f"60000{i}" for i in range(4)],
                                 start_date="2026-09-01", end_date="2026-09-05")
    assert res["summary"]["check_truncated"] is False
    assert res["summary"]["checked_stocks"] == 4
    assert validator.calls == 4


# ── 质量告警外发飞书（CLAUDE.md：必须经 NotificationFacade） ─────────────

class FakeFacade:
    def __init__(self, ok=True, raises=None):
        self.ok = ok
        self.raises = raises
        self.calls = []

    def send_card(self, title=None, content=None, urgency=None):
        self.calls.append({"title": title, "content": content, "urgency": urgency})
        if self.raises:
            raise self.raises
        return self.ok


def _summary():
    return {"total_stocks": 5689, "stocks_with_issues": 5689,
            "data_quality_score": 95.42, "avg_coverage_rate": 92.37}


def test_alert_dispatched_to_feishu_with_high_urgency(monkeypatch):
    """error 级告警（回填全灭）必须以 high 外发，且返回投递结果供 run 记录核验"""
    fake = FakeFacade()
    monkeypatch.setattr(job, "_get_notification_facade", lambda: fake)
    alerts = [{"level": "error", "type": "backfill_degraded", "message": "回填全灭"}]
    out = job._send_quality_alerts(alerts, _summary(), 368, 100.0)
    assert len(fake.calls) == 1, "必须走门面发一次"
    assert fake.calls[0]["urgency"] == "high"
    assert "数据质量告警" in fake.calls[0]["title"]
    assert "368" in fake.calls[0]["content"] and "95.42" in fake.calls[0]["content"]
    assert out["delivered"] is True and out["alert_count"] == 1 and out["urgency"] == "high"


def test_alert_urgency_normal_for_warning_only(monkeypatch):
    fake = FakeFacade()
    monkeypatch.setattr(job, "_get_notification_facade", lambda: fake)
    alerts = [{"level": "warning", "type": "quality_score", "message": "评分偏低"}]
    out = job._send_quality_alerts(alerts, _summary(), 10, 0.0)
    assert fake.calls[0]["urgency"] == "normal"
    assert out["delivered"] is True


def test_alert_dispatch_failure_contained(monkeypatch):
    """门面不可用时只记日志、返回 False，绝不抛出（通知是旁路，不能影响任务结果）"""
    def boom():
        raise RuntimeError("facade down")
    monkeypatch.setattr(job, "_get_notification_facade", boom)
    assert job._dispatch_alert_to_feishu("t", "c", "normal") is False
    out = job._send_quality_alerts([{"level": "error", "type": "x", "message": "m"}], _summary(), 0, 0.0)
    assert out["delivered"] is False


def test_facade_returns_false_is_reported(monkeypatch):
    fake = FakeFacade(ok=False)
    monkeypatch.setattr(job, "_get_notification_facade", lambda: fake)
    out = job._send_quality_alerts([{"level": "error", "type": "x", "message": "m"}], _summary(), 0, 0.0)
    assert out["delivered"] is False

