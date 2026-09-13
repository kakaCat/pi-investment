"""baostock 日期格式归一 + None 结果守护 回归（2026-09-13，w-32314d00，事件 d9361056）

事故：data_backfiller 传 start_date.replace("-", "")（YYYYMMDD）给 DataProviderManager，
manager 原样转发给各 provider；baostock **只认 ISO 格式**，实测：
    YYYYMMDD -> query_history_k_data_plus 返回 None，baostock 仅打印「日期格式不正确，请修改。」
    ISO      -> error_code=0，正常返回数据
旧代码在 rs 为 None 时直接取 rs.error_code → AttributeError: NoneType object has no attribute
error_code → 被当作 provider 失败；3 分钟 150 条错误日志，且 baostock（抗 WAF 的独立 TCP 源）
在这条链路里等于不可用。

本文件锁定：①日期归一容忍两种写法；②provider 必须用 ISO 调 baostock；③rs=None 时给出可读
last_error 且不重试（不再抛 AttributeError）。
"""
import sys
from types import SimpleNamespace

import pytest

from adapters.outbound.datasources.providers.kline.baostock import BaostockKlineProvider


def test_normalize_date_accepts_both_formats():
    assert BaostockKlineProvider._normalize_date('20260911') == '2026-09-11'
    assert BaostockKlineProvider._normalize_date('2026-09-11') == '2026-09-11'
    assert BaostockKlineProvider._normalize_date('') == ''
    assert BaostockKlineProvider._normalize_date(None) == ''


class _FakeResult:
    def __init__(self, rows):
        self.error_code = "0"
        self.error_msg = "success"
        self._rows = list(rows)
        self._i = -1

    def next(self):
        self._i += 1
        return self._i < len(self._rows)

    def get_row_data(self):
        return self._rows[self._i]


def _fake_bs(query_impl):
    return SimpleNamespace(
        login=lambda: SimpleNamespace(error_code="0", error_msg="success"),
        logout=lambda: SimpleNamespace(error_code="0"),
        query_history_k_data_plus=query_impl,
    )


ROW = ["2026-09-11", "sz.000908", "10.0", "11.0", "9.5", "10.5", "1000", "10500", "1.2"]


def test_provider_passes_iso_dates_to_baostock(monkeypatch):
    """核心回归：调用方传 YYYYMMDD，provider 必须用 ISO 去调 baostock（否则恒返回 None）。"""
    seen = {}

    def _q(code, fields, start_date=None, end_date=None, frequency=None, adjustflag=None):
        seen["start"] = start_date
        seen["end"] = end_date
        if len(str(start_date)) != 10 or str(start_date)[4] != "-":
            return None            # 复刻 baostock 对非法日期返回 None 的真实行为
        return _FakeResult([ROW])

    monkeypatch.setitem(sys.modules, "baostock", _fake_bs(_q))
    rows = BaostockKlineProvider().get_klines("000908", "daily", "20260826", "20260911")
    assert seen == {"start": "2026-08-26", "end": "2026-09-11"}
    assert rows and rows[0].date == "2026-09-11" and rows[0].close == 10.5


def test_none_result_set_gives_readable_error_without_retry(monkeypatch):
    """rs=None（入参非法/无数据）→ 可读 last_error、只查一次、不抛 AttributeError。"""
    calls = []

    def _q(*a, **k):
        calls.append(1)
        return None

    monkeypatch.setitem(sys.modules, "baostock", _fake_bs(_q))
    provider = BaostockKlineProvider()
    assert provider.get_klines("000908", "daily", "20260911", "20260911") is None
    assert len(calls) == 1, "永久错误不得重试（会话级错误才重登重试）"
    assert "未返回结果集" in (provider.last_error or "")
