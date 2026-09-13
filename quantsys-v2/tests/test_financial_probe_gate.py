"""财报源探活门控 + 失败日志聚合 回归（2026-09-13，w-32314d00，错误事件 d9adc934）

事故：2026-09-12 20:03 ~ 09-13 00:28 数据源全面不可用期间，financial_statement_update_job
仍对 367 只标的逐个硬试 → 186 只失败、263 条 "XXX: 财报抓取失败" 日志，在 error_events 里
聚成一条 263 次的噪声事件（msg 取首行 003021）。既拿不到数据，也会加重源侧限流/WAF。

修复：①开跑前探活参考标的（600519/000001），全失败即判源不可用 → 快速失败、不做 N 次无效请求；
②逐只失败日志改为循环后**一条聚合汇总**（数量 + 样例 + 首个原因）。
"""
import logging
from types import SimpleNamespace

import pytest

from infrastructure.jobs import financial_statement_update_job as job


class _Result:
    def __init__(self, ok: bool, rows: int = 1):
        self.ok = ok
        self.rows = rows


class _SvcAllDown:
    """所有标的都取不到（模拟源全面不可用）。"""
    def __init__(self):
        self.calls = []

    def get_financial_data(self, symbol, statement_type="income", periods=4):
        self.calls.append(symbol)
        raise Exception(f'All providers failed for {symbol}')


class _SvcProbeOkTargetFail:
    """参考标的可取（探活通过），业务标的失败。"""
    def __init__(self):
        self.calls = []

    def get_financial_data(self, symbol, statement_type="income", periods=4):
        self.calls.append(symbol)
        if str(symbol) in job.PROBE_SYMBOLS:
            return SimpleNamespace(income_statement=[{"报告日": "20260630", "营业总收入": 1.0}],
                                   balance_sheet=[])
        raise Exception(f'All providers failed for {symbol}')


class _Repo:
    def upsert_income_statements(self, records):
        return len(records)

    def upsert_balance_sheets(self, records):
        return 0


def _patch(monkeypatch, svc):
    import application.services.financial_data_service_adapter as ad
    import adapters.outbound.repositories.financial_repository as fr
    monkeypatch.setattr(ad, "FinancialDataServiceAdapter", lambda *a, **k: svc)
    monkeypatch.setattr(fr, "FinancialORMRepository", lambda *a, **k: _Repo())


def test_probe_returns_false_when_all_probes_fail():
    svc = _SvcAllDown()
    assert job._probe_financial_sources(svc) is False
    assert svc.calls == list(job.PROBE_SYMBOLS)   # 探活只试参考标的，不碰全宇宙


def test_probe_returns_true_on_first_success():
    svc = _SvcProbeOkTargetFail()
    assert job._probe_financial_sources(svc) is True
    assert svc.calls == [job.PROBE_SYMBOLS[0]]    # 首个成功即收工


def test_execute_aborts_early_when_sources_down(monkeypatch):
    """源不可用 → 快速失败：不迭代业务标的（否则 367 次无效请求 + 上百条噪声日志）。"""
    svc = _SvcAllDown()
    _patch(monkeypatch, svc)
    res = job.execute(symbols=["003021", "600600", "000983"], periods=1)
    assert res["success"] is False and res.get("probe_failed") is True
    # 只调用过探活的两个参考标的，业务标的零调用
    assert svc.calls == list(job.PROBE_SYMBOLS)


def test_failures_are_logged_once_as_summary(monkeypatch, caplog):
    """逐只失败必须有且只有一条聚合日志（防止再造 263 条噪声）。"""
    svc = _SvcProbeOkTargetFail()
    _patch(monkeypatch, svc)
    symbols = ["003021", "600600", "000983", "688322"]
    with caplog.at_level(logging.WARNING, logger=job.__name__):
        res = job.execute(symbols=symbols, periods=1)
    fails = [r for r in caplog.records if "财报抓取失败" in r.getMessage()]
    assert len(fails) == 1, [r.getMessage() for r in fails]
    msg = fails[0].getMessage()
    assert "4/4" in msg and "003021" in msg        # 数量 + 样例
    assert res["failed"] == 4
