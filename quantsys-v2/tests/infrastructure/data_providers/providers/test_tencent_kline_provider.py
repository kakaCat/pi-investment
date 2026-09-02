"""
TencentKlineProvider 测试（mock 响应，不依赖网络）。

契约来自 2026-07-23 实测响应：
data.{code}.qfqday = [[date, open, close, high, low, volume], ...]
"""
from unittest.mock import patch, MagicMock

from adapters.outbound.datasources.providers.kline.tencent import TencentKlineProvider


SAMPLE_RESPONSE = {
    "code": 0,
    "msg": "",
    "data": {
        "sz300001": {
            "day": [
                ["2026-07-15", "31.790", "32.280", "33.610", "31.400", "260109.000"],
                ["2026-07-16", "32.770", "31.280", "32.880", "30.940", "194854.000"],
            ]
        }
    }
}


def _mock_get(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return patch('adapters.outbound.datasources.providers.kline.tencent.requests.get',
                 return_value=resp)


def test_parse_qfqday_field_order():
    """字段顺序必须是 date, open, close, high, low, volume"""
    with _mock_get(SAMPLE_RESPONSE):
        klines = TencentKlineProvider().get_klines(
            '300001', 'daily', '2026-07-15', '2026-07-22')

    assert klines is not None and len(klines) == 2
    k = klines[0]
    assert k.date == '2026-07-15'
    assert k.open == 31.79
    assert k.close == 32.28
    assert k.high == 33.61
    assert k.low == 31.40
    # volume 原始单位为手，契约统一归一为股（×100），amount = 股×收盘价
    assert k.volume == 26010900
    assert k.amount == 26010900 * 32.28
    assert k.source == 'tencent'
    # 第二天 change_pct = (31.28-32.28)/32.28 = -3.10%
    assert klines[1].change_pct == -3.10


def test_symbol_prefix_mapping():
    """600→sh, 300→sz, 920→bj"""
    assert TencentKlineProvider._to_tencent_code('600519') == 'sh600519'
    assert TencentKlineProvider._to_tencent_code('300001') == 'sz300001'
    assert TencentKlineProvider._to_tencent_code('920896') == 'bj920896'
    assert TencentKlineProvider._to_tencent_code('600519.SH') == 'sh600519'


INDEX_RESPONSE = {
    "code": 0,
    "msg": "",
    "data": {
        "sz399006": {
            "day": [
                ["2026-07-23", "3596.730", "3575.520", "3621.730", "3538.110", "181766334.000"],
                ["2026-07-24", "3515.500", "3480.870", "3561.350", "3480.870", "168793607.000"],
            ]
        }
    }
}


def test_shenzhen_index_symbol_mapping():
    """399 前缀是深市指数代码段（399001 深成指、399006 创业板指）→ sz399xxx"""
    assert TencentKlineProvider._to_tencent_code('399006') == 'sz399006'
    assert TencentKlineProvider._to_tencent_code('399001') == 'sz399001'


def test_index_klines_parse_day_field():
    """指数无复权数据，腾讯返回 day 而非 qfqday，必须能解析"""
    with _mock_get(INDEX_RESPONSE):
        klines = TencentKlineProvider().get_klines(
            '399006', 'daily', '2026-07-23', '2026-07-24')

    assert klines is not None and len(klines) == 2
    assert klines[0].close == 3575.52
    assert klines[1].close == 3480.87
    assert klines[1].change_pct == round((3480.87 - 3575.52) / 3575.52 * 100, 2)


def test_non_daily_period_returns_none():
    assert TencentKlineProvider().get_klines('300001', '5m', '2026-07-15', '2026-07-22') is None


def test_api_error_returns_none():
    with _mock_get({"code": -1, "msg": "error"}):
        assert TencentKlineProvider().get_klines(
            '300001', 'daily', '2026-07-15', '2026-07-22') is None


def test_empty_data_returns_none():
    with _mock_get({"code": 0, "data": {"sz300001": {}}}):
        assert TencentKlineProvider().get_klines(
            '300001', 'daily', '2026-07-15', '2026-07-22') is None


def test_network_exception_returns_none():
    with patch('adapters.outbound.datasources.providers.kline.tencent.requests.get',
               side_effect=ConnectionError('reset')):
        assert TencentKlineProvider().get_klines(
            '300001', 'daily', '2026-07-15', '2026-07-22') is None


def test_manager_kline_chain_has_tencent_before_akshare():
    """DataProviderManager 的 K线 fallback 链：tencent 必须在 akshare 之前"""
    from adapters.outbound.datasources.manager import DataProviderManager
    manager = DataProviderManager()
    names = [p.name for p in manager.kline_providers]
    assert 'tencent' in names and 'akshare' in names
    assert names.index('tencent') < names.index('akshare')


def test_last_error_records_unmappable_symbol():
    """无法映射的代码必须留下具体原因（供 manager 聚合返回）"""
    p = TencentKlineProvider()
    assert p.get_klines('ABC123', 'daily', '2026-07-15', '2026-07-22') is None
    assert p.last_error and '无法映射' in p.last_error


def test_last_error_records_non_daily():
    p = TencentKlineProvider()
    assert p.get_klines('600519', '5m', '2026-07-15', '2026-07-22') is None
    assert p.last_error and 'daily' in p.last_error


def test_last_error_records_api_empty_data():
    p = TencentKlineProvider()
    with _mock_get({"code": 0, "data": {"sz300001": {}}}):
        assert p.get_klines('300001', 'daily', '2026-07-15', '2026-07-22') is None
    assert p.last_error and '无' in p.last_error


def test_last_error_cleared_on_success():
    """成功后 last_error 复位，避免残留上次的失败原因"""
    p = TencentKlineProvider()
    p.get_klines('ABC123', 'daily', '2026-07-15', '2026-07-22')
    assert p.last_error is not None
    with _mock_get(SAMPLE_RESPONSE):
        assert p.get_klines('300001', 'daily', '2026-07-15', '2026-07-22') is not None
    assert p.last_error is None


def test_try_providers_aggregates_failure_reasons():
    """manager 必须聚合每个 provider 的具体失败原因到 provider_errors"""
    from adapters.outbound.datasources.manager import DataProviderManager

    class DummyProvider:
        def __init__(self, name, reason=None, exc=None):
            self._name, self.last_error, self._exc = name, reason, exc

        @property
        def name(self):
            return self._name

        def get_klines(self, *args):
            if self._exc:
                raise self._exc
            return None

    manager = DataProviderManager()
    manager.kline_providers = [
        DummyProvider('database', reason='数据库无 399006 的K线缓存'),
        DummyProvider('tencent', reason='代码无法映射'),
        DummyProvider('akshare', exc=ConnectionError('reset by peer')),
    ]
    result = manager.get_klines('399006', 'daily', '2026-07-01', '2026-07-24')

    assert result['success'] is False
    assert result['provider_errors'] == {
        'database': '数据库无 399006 的K线缓存',
        'tencent': '代码无法映射',
        'akshare': 'ConnectionError: reset by peer',
    }
