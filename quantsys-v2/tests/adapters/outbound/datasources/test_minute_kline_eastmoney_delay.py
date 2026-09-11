"""东财延迟域分钟线 provider 单测（2026-09-11，w-f436d4ea）

为什么必须有这组单测（此前只做过一次跨源比对，属"验证过但没锁住"）：
1. **字段序映射**：东财 push2delay 的 kline 字段序是
   `时间,开,收,高,低,量,额,涨跌幅` —— 第 2/3 位是**开/收**而非直觉的**开/高**。
   这类"字段错位静默产出假数据"是项目已踩过的同型事故（分红 provider 读错列名→全 0）。
   本测试用固定样本行锁死映射；若有人"顺手改成标准 OHLC 顺序"，测试立刻失败。
2. **1m→Nm 聚合栅格**：延迟域只提供当日 1m，多周期靠 provider 内聚合。
   分桶必须按**交易时段栅格 + 周期结束时刻**，否则 60m 会跨午休断成 11:30~12:30。
3. **量纲**：vol 为手 → 统一 ×100 转股。

测试方式：monkeypatch 模块级 `requests.get`，不触网、不写库。
"""
import importlib
import json

import pytest

MODULE = 'adapters.outbound.datasources.providers.minute_kline.eastmoney'

# 实测样本（2026-09-11，600150）——字段序：时间,开,收,高,低,量(手),额(元),涨跌幅
SAMPLE_F2 = [
    '2026-09-11 09:31,39.50,39.59,39.93,39.40,168236,665639626.00,1.30',   # 开>收? 否：开39.50 收39.59
    '2026-09-11 09:32,39.65,39.20,39.65,39.19,89932,354436864.00,1.16',
    '2026-09-11 09:33,39.20,39.30,39.35,39.18,50000,196000000.00,0.25',
    '2026-09-11 09:34,39.30,39.40,39.45,39.28,40000,157600000.00,0.26',
    '2026-09-11 09:35,39.40,39.10,39.42,39.05,30000,117600000.00,-0.76',
    '2026-09-11 09:36,39.10,39.15,39.20,39.08,20000,78200000.00,0.13',
]


def _provider_class():
    """按能力发现 provider 类（避免硬编码类名）"""
    mod = importlib.import_module(MODULE)
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and hasattr(obj, 'get_minute_klines'):
            return obj
    raise AssertionError('未找到实现 get_minute_klines 的 provider 类')


@pytest.fixture()
def stub_http(monkeypatch):
    """monkeypatch 模块级 requests.get，返回固定 klines"""
    mod = importlib.import_module(MODULE)
    captured = {}

    class _Resp:
        status_code = 200
        text = ''

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    def _fake_get(url, **kwargs):
        captured['url'] = url
        captured['params'] = kwargs.get('params') or {}
        return _Resp({'rc': 0, 'data': {'name': '中国船舶', 'klines': list(SAMPLE_F2)}})

    monkeypatch.setattr(mod.requests, 'get', _fake_get)
    return captured


def test_field_order_open_close_not_open_high(stub_http):
    """**核心回归锁**：第 2/3 位是 开/收，不是 开/高"""
    prov = _provider_class()()
    rows = prov.get_minute_klines('600150', period='1m')
    assert rows, '应解析出分钟线'
    first = rows[0]
    # 原始行：09:31,开39.50,收39.59,高39.93,低39.40
    assert first.open == pytest.approx(39.50), '第 2 位必须是「开」'
    assert first.close == pytest.approx(39.59), '第 3 位必须是「收」'
    assert first.high == pytest.approx(39.93)
    assert first.low == pytest.approx(39.40)
    # OHLC 恒等式必须成立——若字段错位（把收当高），此处会失败
    for r in rows:
        assert r.high >= max(r.open, r.close) >= min(r.open, r.close) >= r.low, \
            f'OHLC 恒等式被破坏（疑字段错位）: {r.open},{r.close},{r.high},{r.low}'


def test_volume_unit_converted_hand_to_shares(stub_http):
    """量纲：vol 为手 → ×100 转股"""
    prov = _provider_class()()
    rows = prov.get_minute_klines('600150', period='1m')
    assert rows[0].volume == pytest.approx(168236 * 100), '手→股 必须 ×100'


def test_aggregate_5m_open_first_close_last_high_max_low_min(stub_http):
    """5m 聚合语义：open=首、close=末、high=max、low=min、volume=求和"""
    prov = _provider_class()()
    m1 = prov.get_minute_klines('600150', period='1m')
    m5 = prov.get_minute_klines('600150', period='5m')
    assert m5, '5m 应聚合出结果'
    # 前 5 根 1m（09:31~09:35）应聚合为 1 根 5m（桶标签=周期结束 09:35）
    bucket = m5[0]
    head = m1[:5]
    assert bucket.open == pytest.approx(head[0].open)
    assert bucket.close == pytest.approx(head[-1].close)
    assert bucket.high == pytest.approx(max(r.high for r in head))
    assert bucket.low == pytest.approx(min(r.low for r in head))
    assert bucket.volume == pytest.approx(sum(r.volume for r in head))
    # 聚合后根数必然少于 1m
    assert len(m5) <= len(m1)


def test_aggregate_bucket_never_crosses_lunch_break(stub_http):
    """60m 桶不得跨午休（11:30~13:00）：任何一根 60m 的时间必须落在时段内且不跨段"""
    prov = _provider_class()()
    m60 = prov.get_minute_klines('600150', period='60m')
    assert m60, '60m 应聚合出结果'
    for r in m60:
        hm = str(r.trade_datetime).split(' ')[-1][:5]
        # 桶标签 = 周期结束时刻，必须落在 09:30-11:30 或 13:00-15:00
        assert ('09:30' <= hm <= '11:30') or ('13:00' <= hm <= '15:00'), f'桶落在交易时段外: {hm}'


def test_empty_klines_returns_none_not_empty_list(stub_http, monkeypatch):
    """空结果必须返回 None（交给故障转移），不得返回空列表冒充成功"""
    mod = importlib.import_module(MODULE)

    class _Resp:
        status_code = 200

        def json(self):
            return {'rc': 0, 'data': {'name': '中国船舶', 'klines': []}}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(mod.requests, 'get', lambda url, **kw: _Resp())
    prov = _provider_class()()
    assert prov.get_minute_klines('600150', period='5m') is None


def test_last_error_set_on_http_failure(stub_http, monkeypatch):
    """网络失败必须自报 last_error（供 manager 判真故障；空结果才不计失败）"""
    mod = importlib.import_module(MODULE)

    def _boom(url, **kw):
        raise RuntimeError('connection reset')

    monkeypatch.setattr(mod.requests, 'get', _boom)
    prov = _provider_class()()
    assert prov.get_minute_klines('600150', period='1m') is None
    assert getattr(prov, 'last_error', None), '网络失败必须设置 last_error，否则被误判为「空结果」'
