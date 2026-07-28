"""BaostockKlineProvider 测试（mock baostock 模块，不依赖网络）

baostock 契约：
- bs.login() / bs.logout() 会话
- bs.query_history_k_data_plus(code, fields, start_date, end_date, frequency='d', adjustflag='2')
  返回 ResultData，.error_code == '0' 成功，.next() 迭代，.get_row_data() 取行
- 日K 字段: date,code,open,high,low,close,volume(股),amount(元),turn(换手率%)
"""
import sys
from unittest.mock import patch, MagicMock

import pytest

from adapters.outbound.datasources.providers.kline.base import KlineData
from adapters.outbound.datasources.providers.kline.baostock import BaostockKlineProvider


def _mock_bs(rows, error_code='0'):
    """构造 mock baostock 模块"""
    rs = MagicMock()
    rs.error_code = error_code
    rs.error_msg = 'ok' if error_code == '0' else 'query failed'
    rs.next.side_effect = [True] * len(rows) + [False]
    rs.get_row_data.side_effect = rows

    bs = MagicMock()
    bs.login.return_value = MagicMock(error_code='0')
    bs.query_history_k_data_plus.return_value = rs
    return bs


SAMPLE_ROWS = [
    ['2026-07-27', 'sz.300750', '376.43', '385.00', '372.00', '382.20',
     '44036000', '16834567890.12', '1.13'],
    ['2026-07-28', 'sz.300750', '382.00', '386.50', '378.00', '385.00',
     '25186900', '9697961500.00', '0.64'],
]


def test_kline_data_has_turnover_field():
    """KlineData 契约必须有 turnover_rate 字段（默认 0.0 向后兼容）"""
    k = KlineData(symbol='300750', date='2026-07-28', open=1, high=1,
                  low=1, close=1, volume=100)
    assert k.turnover_rate == 0.0


def test_symbol_to_baostock_code():
    """300750→sz.300750, 600519→sh.600519, 399006→sz.399006, 容忍 .SH 后缀"""
    assert BaostockKlineProvider._to_baostock_code('300750') == 'sz.300750'
    assert BaostockKlineProvider._to_baostock_code('600519') == 'sh.600519'
    assert BaostockKlineProvider._to_baostock_code('399006') == 'sz.399006'
    assert BaostockKlineProvider._to_baostock_code('600519.SH') == 'sh.600519'
    assert BaostockKlineProvider._to_baostock_code('ABC') is None


def test_parse_daily_klines_with_amount_and_turnover():
    """日K 解析：volume 为股（baostock 原生单位）、amount 元、turn 换手率"""
    bs = _mock_bs(SAMPLE_ROWS)
    with patch.dict(sys.modules, {'baostock': bs}):
        klines = BaostockKlineProvider().get_klines(
            '300750', 'daily', '2026-07-27', '2026-07-28')

    assert klines is not None and len(klines) == 2
    k = klines[0]
    assert k.date == '2026-07-27'
    assert k.open == 376.43
    assert k.close == 382.20
    assert k.volume == 44036000            # 股，不 ×100
    assert k.amount == 16834567890.12      # 元
    assert k.turnover_rate == 1.13         # 换手率 %
    assert k.source == 'baostock'
    # 第二天 change_pct = (385.00-382.20)/382.20 = 0.73%
    assert klines[1].change_pct == 0.73


def test_login_failure_returns_none():
    bs = _mock_bs(SAMPLE_ROWS)
    bs.login.return_value = MagicMock(error_code='-1', error_msg='auth failed')
    with patch.dict(sys.modules, {'baostock': bs}):
        assert BaostockKlineProvider().get_klines(
            '300750', 'daily', '2026-07-27', '2026-07-28') is None


def test_query_error_returns_none_with_last_error():
    bs = _mock_bs([], error_code='-1')
    with patch.dict(sys.modules, {'baostock': bs}):
        p = BaostockKlineProvider()
        assert p.get_klines('300750', 'daily', '2026-07-27', '2026-07-28') is None
        assert p.last_error


def test_empty_rows_returns_none():
    bs = _mock_bs([])
    with patch.dict(sys.modules, {'baostock': bs}):
        assert BaostockKlineProvider().get_klines(
            '300750', 'daily', '2026-07-27', '2026-07-28') is None


def test_non_daily_period_returns_none():
    assert BaostockKlineProvider().get_klines(
        '300750', '5m', '2026-07-27', '2026-07-28') is None


def test_manager_kline_chain_order():
    """fallback 链：baostock → tencent → akshare（database 视环境可能缺席）"""
    from adapters.outbound.datasources.manager import DataProviderManager
    names = [p.name for p in DataProviderManager().kline_providers]
    if 'database' in names:
        assert names.index('database') < names.index('baostock')
    assert names.index('baostock') < names.index('tencent')
    assert names.index('tencent') < names.index('akshare')
