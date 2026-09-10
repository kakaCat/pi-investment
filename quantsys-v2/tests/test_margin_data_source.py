"""AkShare 融资融券明细数据源契约测试 — 2026-09-11 w-8f2c4cc5

背景：board 事件 3cef6bef——adapters/outbound/datasources/margin_data_source.py 旧实现调用
ak.stock_margin_detail_sse(symbol=stock_code)，但 akshare 1.18.x 该接口签名为 stock_margin_detail_sse(date: str)
（按日期取全市场明细），传 symbol 直接 TypeError → 个股融资融券数据长期取不到，静默落到 SimulatedMarginSource
的随机数兜底。本测试锁定修复后的行为契约：

1. 按代码前缀路由到 sse/szse/bse 明细接口，未知市场显式报错（不静默、不伪造）
2. 逐交易日回溯 + 按证券代码过滤 → 输出按日期倒序（data[0]=最新，_calculate_summary 依赖该顺序）
3. 金额元→万元；沪市明细无融券余额列时 has_margin_balance=False（不把「缺失」伪装成「真实 0」）
4. 「当日未发布」的 akshare ValueError(Length mismatch) 与真实故障区分：前者跳过不重试，后者连续 3 日失败即报错
5. 聚合层降级到模拟源时 source=simulated 明确标注（调用方可识别数据为模拟）
"""
import sys
import types

import pandas as pd
import pytest

from adapters.outbound.datasources.margin_data_source import (
    AkShareMarginSource,
    MarginDataSource,
)
from domain.ports.datasource_ports import DataSourceError


def _sse_frame(date_str: str, code: str = "600887") -> pd.DataFrame:
    """沪市明细真实列名（akshare 1.18.81 实测：无「融券余额」列，代码列名为「标的证券代码」）。"""
    return pd.DataFrame([
        {"信用交易日期": date_str, "标的证券代码": code, "标的证券简称": "伊利股份",
         "融资余额": 2454463005, "融资买入额": 53617293, "融资偿还额": 86815340,
         "融券余量": 8431400, "融券卖出量": 389500, "融券偿还量": 19500},
        {"信用交易日期": date_str, "标的证券代码": "600519", "标的证券简称": "贵州茅台",
         "融资余额": 111, "融资买入额": 22, "融资偿还额": 33,
         "融券余量": 44, "融券卖出量": 55, "融券偿还量": 66},
    ])


def _szse_frame(date_str: str, code: str = "300677") -> pd.DataFrame:
    """深市明细真实列名（含「融券余额」与「融资融券余额」）。"""
    return pd.DataFrame([
        {"证券代码": code, "证券简称": "英科医疗", "融资买入额": 16477893, "融资余额": 334883164,
         "融券卖出量": 9100, "融券余量": 135240, "融券余额": 7274560, "融资融券余额": 342157724},
    ])


def _install_stub_akshare(monkeypatch, sse=None, szse=None, bse=None, calls=None):
    """把假 akshare 注入 sys.modules（fetch 内部是延迟 import，故此处可拦截）。"""
    stub = types.ModuleType("akshare")

    def _wrap(fn, market):
        def _inner(date=None):
            if calls is not None:
                calls.append((market, date))
            return fn(date) if fn else pd.DataFrame()
        return _inner

    stub.stock_margin_detail_sse = _wrap(sse, "sse")
    stub.stock_margin_detail_szse = _wrap(szse, "szse")
    stub.stock_margin_detail_bse = _wrap(bse, "bse")
    monkeypatch.setitem(sys.modules, "akshare", stub)
    return stub


# ── 市场路由 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code,market", [
    ("600887", "sse"), ("601857", "sse"), ("688825", "sse"),
    ("000001", "szse"), ("002415", "szse"), ("300677", "szse"),
    ("430047", "bse"), ("830799", "bse"),
])
def test_market_routing(code, market):
    assert AkShareMarginSource._market_for(code) == market


def test_unknown_market_raises_instead_of_fabricating(monkeypatch):
    _install_stub_akshare(monkeypatch)
    with pytest.raises(DataSourceError):
        AkShareMarginSource().fetch("900901", 3)


# ── 列映射与排序契约 ────────────────────────────────────────────────────────

def test_sse_mapping_and_descending_dates(monkeypatch):
    _install_stub_akshare(monkeypatch, sse=lambda d: _sse_frame(d))
    rows = AkShareMarginSource().fetch("600887", 4)

    assert len(rows) == 4
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True), "必须是日期倒序（data[0]=最新）"

    first = rows[0]
    assert first["financing_balance"] == pytest.approx(2454463005 / 10000)  # 元→万元
    assert first["financing_buy"] == pytest.approx(53617293 / 10000)
    assert first["margin_sell"] == pytest.approx(389500)  # 量保持股，不折算
    assert first["has_margin_balance"] is False, "沪市明细无融券余额列，须显式标注而非伪装成 0"
    assert first["margin_balance"] == 0.0
    assert first["total_balance"] == pytest.approx(first["financing_balance"])


def test_szse_mapping_uses_native_total(monkeypatch):
    _install_stub_akshare(monkeypatch, szse=lambda d: _szse_frame(d))
    rows = AkShareMarginSource().fetch("300677", 2)

    assert len(rows) == 2
    first = rows[0]
    assert first["has_margin_balance"] is True
    assert first["margin_balance"] == pytest.approx(7274560 / 10000)
    assert first["total_balance"] == pytest.approx(342157724 / 10000)
    assert first["financing_balance"] == pytest.approx(334883164 / 10000)


def test_filter_only_target_symbol(monkeypatch):
    """同日全市场明细里必须只取目标股票那一行（沪市代码列名为标的证券代码）。"""
    _install_stub_akshare(monkeypatch, sse=lambda d: _sse_frame(d, code="600887"))
    rows = AkShareMarginSource().fetch("600887", 1)
    assert rows[0]["financing_balance"] == pytest.approx(2454463005 / 10000)

    rows_other = AkShareMarginSource().fetch("600519", 1)
    assert rows_other[0]["financing_balance"] == pytest.approx(111 / 10000)


def test_candidate_dates_skip_weekends():
    dates = AkShareMarginSource._candidate_dates(5)
    assert len(dates) >= 6
    for d in dates:
        assert pd.Timestamp(d).weekday() < 5, f"{d} 是周末，不应作为候选交易日"


# ── 故障语义：空返回 vs 真实故障 ────────────────────────────────────────────

def test_unpublished_day_skips_without_retry(monkeypatch):
    """akshare 对未发布日抛 ValueError(Length mismatch)：属正常无数据，只调一次、不重试。"""
    calls = []

    def _raise(date):
        raise ValueError("Length mismatch: Expected axis has 0 elements, new values have 13 elements")

    _install_stub_akshare(monkeypatch, sse=_raise, calls=calls)
    rows = AkShareMarginSource().fetch("600887", 3)

    assert rows == []
    expected_days = len(AkShareMarginSource._candidate_dates(3))
    assert len(calls) == expected_days, f"每日应只尝试一次，实际 {len(calls)} 次"


def test_consecutive_real_failures_raise(monkeypatch):
    """真实异常（非空返回）连续 3 个交易日失败 → 显式 DataSourceError，交由上层降级并如实标注。"""
    calls = []

    def _boom(date):
        raise RuntimeError("upstream down")

    _install_stub_akshare(monkeypatch, sse=_boom, calls=calls)
    with pytest.raises(DataSourceError):
        AkShareMarginSource().fetch("600887", 5)
    assert len(calls) == 9, "3 个交易日 × 每个 3 次重试"


def test_empty_frame_skips_day(monkeypatch):
    calls = []

    def _empty(date):
        return pd.DataFrame()

    _install_stub_akshare(monkeypatch, sse=_empty, calls=calls)
    assert AkShareMarginSource().fetch("600887", 2) == []
    assert len(calls) == len(AkShareMarginSource._candidate_dates(2))


# ── 聚合层降级必须可识别 ────────────────────────────────────────────────────

def test_aggregate_labels_simulated_fallback(monkeypatch):
    def _fail(self, symbol, days):
        raise DataSourceError("akshare unavailable")

    monkeypatch.setattr(AkShareMarginSource, "fetch", _fail)
    data = MarginDataSource().get_margin_data("600887", 5)
    assert data["source"] == "simulated", "降级到模拟源时必须在 source 字段如实标注"
    assert len(data["data"]) == 5
