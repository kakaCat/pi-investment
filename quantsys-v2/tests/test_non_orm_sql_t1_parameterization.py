"""非 ORM SQL 收敛 · t1（参数化与列白名单）回归（2026-09-13，w-32314d00，REQ-24e15d）。

覆盖两类修复：
  1) industry_data_adapter：列名白名单 + 取值走绑定参数（原为 f-string 直接拼 factor_name 与 symbols）；
  2) financial_data_update_job：SET 子句列名白名单（原为拼上游 dict 的 key）。
"""
import contextlib

import pytest

from infrastructure.adapters import industry_data_adapter as ida
from infrastructure.jobs import financial_data_update_job as fdu


# ═══════════════ industry_data_adapter ═══════════════

def test_factor_column_whitelist_accepts_known_columns():
    for col in ('pe', 'pb', 'roe', 'revenue_growth'):
        assert ida._validated_factor_column(col) == col


@pytest.mark.parametrize("bad", [
    'pe; DROP TABLE quant.stocks', 'pe, name', '1=1', '', None, 'unknown_col',
])
def test_factor_column_whitelist_rejects_unknown(bad):
    with pytest.raises(ValueError):
        ida._validated_factor_column(bad)


class _CapturingCursor:
    def __init__(self, sink):
        self.sink = sink

    def execute(self, sql, params=None):
        self.sink.append((sql, params))

    def fetchall(self):
        return []


@contextlib.contextmanager
def _fake_db_cursor(sink):
    yield _CapturingCursor(sink)


def test_symbols_are_bound_parameters_not_interpolated(monkeypatch):
    sink = []
    monkeypatch.setattr(ida, 'db_cursor', lambda: _fake_db_cursor(sink), raising=True)
    adapter = ida.IndustryDataAdapter()
    adapter.get_sector_factor_values('医药', 'pe', symbols=['600519', "000001' OR '1'='1"])
    sql, params = sink[0]
    assert '= ANY(%s)' in sql, '取值必须走绑定参数'
    assert "OR '1'='1" not in sql, 'symbol 不得进入 SQL 文本'
    assert params == (["600519", "000001' OR '1'='1"],)


def test_unknown_factor_name_never_reaches_sql(monkeypatch):
    sink = []
    monkeypatch.setattr(ida, 'db_cursor', lambda: _fake_db_cursor(sink), raising=True)
    adapter = ida.IndustryDataAdapter()
    assert adapter.get_sector_factor_values('医药', 'pe; DROP TABLE quant.stocks', symbols=['600519']) == []
    assert sink == []


# ═══════════════ financial_data_update_job ═══════════════

def test_writable_columns_contract():
    assert fdu.WRITABLE_STOCK_COLUMNS == {'roe', 'gross_margin', 'net_profit_growth', 'revenue_growth'}
    assert 'debt_ratio' not in fdu.WRITABLE_STOCK_COLUMNS, 'debt_ratio 明确不在本 job 范围（文件头口径）'
