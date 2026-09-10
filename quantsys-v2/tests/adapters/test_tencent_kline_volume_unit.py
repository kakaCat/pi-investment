# -*- coding: utf-8 -*-
"""腾讯 K 线 provider 成交量量纲回归测试（2026-09-10 w-23c70356）。

契约：DB daily_klines.volume 单位 = 股。
腾讯 /appstock/app/kline/kline 接口：科创板（688/689）返回股，其余板块返回手。
历史缺陷：统一 ×100 使科创板放大 100 倍（2026-07-24~08-31 共 2,110 行）。
本测试锁定该契约，防止再次回归。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.outbound.datasources.providers.kline.tencent import TencentKlineProvider


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _payload(code: str, rows):
    return {'code': 0, 'data': {code: {'day': rows}}}


def _patch(monkeypatch, payload):
    import adapters.outbound.datasources.providers.kline.tencent as mod

    monkeypatch.setattr(mod.requests, 'get', lambda *a, **kw: _FakeResp(payload))


# 字段顺序: [date, open, close, high, low, volume]
_ROW = [['2026-08-20', '10.00', '10.50', '10.80', '9.90', '12345']]


def test_star_board_volume_not_multiplied(monkeypatch):
    """科创板：接口值即股，不得 ×100。"""
    _patch(monkeypatch, _payload('sh688663', _ROW))
    klines = TencentKlineProvider().get_klines('688663', 'daily', '2026-08-01', '2026-08-31')
    assert klines and len(klines) == 1
    assert klines[0].volume == 12345


def test_star_board_cdr_689(monkeypatch):
    """科创板 CDR（689）同规则。"""
    _patch(monkeypatch, _payload('sh689009', _ROW))
    klines = TencentKlineProvider().get_klines('689009', 'daily', '2026-08-01', '2026-08-31')
    assert klines[0].volume == 12345


def test_main_board_volume_lots_to_shares(monkeypatch):
    """主板/创业板：接口值为手，需 ×100 归一为股。"""
    _patch(monkeypatch, _payload('sh600519', _ROW))
    klines = TencentKlineProvider().get_klines('600519', 'daily', '2026-08-01', '2026-08-31')
    assert klines[0].volume == 12345 * 100


def test_gem_board_volume_lots_to_shares(monkeypatch):
    _patch(monkeypatch, _payload('sz300750', _ROW))
    klines = TencentKlineProvider().get_klines('300750', 'daily', '2026-08-01', '2026-08-31')
    assert klines[0].volume == 12345 * 100


def test_symbol_with_suffix_tolerated(monkeypatch):
    """600519.SH 形式：板块判定需先去后缀。"""
    _patch(monkeypatch, _payload('sh688663', _ROW))
    klines = TencentKlineProvider().get_klines('688663.SH', 'daily', '2026-08-01', '2026-08-31')
    assert klines[0].volume == 12345


def test_amount_consistent_with_volume(monkeypatch):
    """amount = volume × close（契约单位股），量纲错会同时放大成交额。"""
    _patch(monkeypatch, _payload('sh688663', _ROW))
    klines = TencentKlineProvider().get_klines('688663', 'daily', '2026-08-01', '2026-08-31')
    assert klines[0].amount == pytest.approx(12345 * 10.50, rel=1e-6)
