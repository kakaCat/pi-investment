"""行情批量链路契约锁（2026-09-13，w-adb088f2）

背景（实测）：账户查询逐只取价，每只各新建一次 HTTP 连接；本机 IPv6 不可达但 getaddrinfo
先返回 AAAA，urllib3 逐个 SYN 超时后才回退 IPv4 → **每次新建连接多付约 8s**（curl 因实现
Happy Eyeballs 只需 0.3s）。2 只持仓 = 16.4s，超过 agent 工具 10s 超时，account_info /
position_list 直接不可用。同时发现批量接口是"假批量"：
  - GET  /api/provider/quotes  → 调用的 manager.get_quotes **根本不存在**（404 Method not found）
  - POST /api/stocks/batch-quotes → 注释写着 failover per symbol，实际 for 循环逐只（2 只 16.3s）

本文件锁三件事：
  ① 腾讯 provider 批量只发**一次**请求，且能解析多只（含无匹配段的容错）；
  ② manager.get_quotes 是"部分补齐"语义：缺口显式暴露（missing_symbols），
     绝不把"部分成功"当"全部成功"，也绝不因单源缺口丢数据；
  ③ 账户路径与批量 API 真的走批量入口（源码级断言，防止再退回逐只循环）。
"""
import socket

import pytest

from qs_market_data.adapters.outbound.datasources.manager import DataProviderManager
from qs_market_data.adapters.outbound.datasources.models import QuoteData
from qs_market_data.adapters.outbound.datasources.providers.quote import tencent as tencent_mod


def _quote(symbol, price, source='tencent'):
    return QuoteData(symbol=symbol, name='X', price=price, source=source)


# --------------------------- ① 腾讯 provider 真批量 ---------------------------

class _Resp:
    def __init__(self, text):
        self.text = text
        self.encoding = 'utf-8'


def _tencent_payload():
    # 腾讯多只响应：每个标的一行 v_CODE="..."，字段位置与单只一致
    return (
        'v_sz300677="51~英科医疗~300677~55.00~55.63~55.58~91739~49098~42641~54.99~3'
        + '~' * 20 + '55.00~0.00~0.00~56.69~54.27~";\n'
        'v_sh600887="51~伊利股份~600887~26.66~26.50~26.74~222222~111~111~26.6~3'
        + '~' * 20 + '26.66~0.10~0.30~26.9~26.4~";\n'
    )


def test_腾讯批量只发一次HTTP请求并解析多只(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _Resp(_tencent_payload())

    monkeypatch.setattr(tencent_mod.requests, 'get', fake_get)
    p = tencent_mod.TencentQuoteProvider()
    got = p.get_quotes(['300677', '600887'])

    assert len(calls) == 1, f'批量必须只发一次请求，实际 {len(calls)} 次 —— 退回逐只就等于每只再付一次连接成本'
    assert 'q=sz300677,sh600887' in calls[0], '多只必须以逗号拼接在同一个 q= 参数里'
    assert set(got.keys()) == {'300677', '600887'}
    assert got['300677'].price == pytest.approx(55.0)
    assert got['600887'].price == pytest.approx(26.66)


def test_腾讯批量忽略无法匹配的段且不抛错(monkeypatch):
    monkeypatch.setattr(tencent_mod.requests, 'get',
                        lambda url, **kw: _Resp('v_sz300677="51~英科医疗~300677~55.00~55.63~55.58~1~1~1~'
                                                + '~' * 20 + '55.0~0~0~56~54~";\n'
                                                'v_sh999999="garbage";\n'
                                                'not a quote line\n'))
    p = tencent_mod.TencentQuoteProvider()
    got = p.get_quotes(['300677', '600887'])
    assert list(got.keys()) == ['300677'], '未请求的代码/脏段必须丢弃，不能塞进结果'
    assert got['300677'].price > 0


def test_腾讯批量全空时置last_error交给降级链(monkeypatch):
    monkeypatch.setattr(tencent_mod.requests, 'get', lambda url, **kw: _Resp(''))
    p = tencent_mod.TencentQuoteProvider()
    got = p.get_quotes(['300677'])
    assert got == {}
    assert p.last_error, '整批无数据必须自报 last_error（否则会被当成"健康空"不计故障）'


def test_基类默认批量实现退化为逐只(monkeypatch):
    from qs_market_data.adapters.outbound.datasources.base import QuoteProvider

    class P(QuoteProvider):
        @property
        def name(self):
            return 'stub'

        def get_quote(self, symbol):
            if symbol == 'bad':
                raise RuntimeError('boom')
            return _quote(symbol, 10.0, source='stub')

    got = P().get_quotes(['a', 'bad', 'b'])
    assert set(got.keys()) == {'a', 'b'}, '不支持批量的源应退化为逐只，且单只失败不拖垮整批'


# --------------------------- ② manager 部分补齐语义 ---------------------------

def _manager(providers, broken=()):
    """只装配批量路径所需内部：不跑 __init__（避免真实 provider 链/仓储）"""
    m = DataProviderManager.__new__(DataProviderManager)
    m.quote_providers = providers
    m._circuit_breakers = {}
    m._sort_providers_by_health = lambda ps: list(ps)
    m._is_circuit_broken = lambda name: name in broken
    m._record_success = lambda name: None
    m._record_failure = lambda name: None
    m._record_empty = lambda name: None
    m._empty_reason = lambda p: '空结果'
    return m


class _Prov:
    def __init__(self, name, mapping=None, raises=None):
        self.name = name
        self.last_error = None
        self._mapping = mapping or {}
        self._raises = raises
        self.seen = []

    def get_quotes(self, symbols):
        self.seen.append(list(symbols))
        if self._raises:
            raise self._raises
        return {s: self._mapping[s] for s in symbols if s in self._mapping}


def test_批量只把缺口交给下一个源():
    p1 = _Prov('tencent', {'a': _quote('a', 1.0)})
    p2 = _Prov('sina', {'b': _quote('b', 2.0, source='sina')})
    m = _manager([p1, p2])
    r = m.get_quotes(['a', 'b'])
    assert r['success'] is True
    assert set(r['data']) == {'a', 'b'}, '前一个源没给的标的必须继续向后补齐，不能丢'
    assert p2.seen == [['b']], '已取到的标的不得重复请求（避免又付一次连接成本）'
    assert r['missing_symbols'] == []
    assert r['attempted_sources'] == ['tencent', 'sina']


def test_部分成功必须暴露缺口而不是冒充全部成功():
    p1 = _Prov('tencent', {'a': _quote('a', 1.0)})
    p2 = _Prov('sina', {})
    p3 = _Prov('eastmoney', {})
    m = _manager([p1, p2, p3])
    r = m.get_quotes(['a', 'zzz'])
    assert r['success'] is True and 'a' in r['data']
    assert r['missing_symbols'] == ['zzz'], '缺口要显式暴露，调用方据此置 price_stale'
    assert r['empty'] is False


def test_全部失败返回success_False并记尝试链():
    m = _manager([_Prov('tencent', raises=RuntimeError('conn reset'))])
    r = m.get_quotes(['a'])
    assert r['success'] is False
    assert r['data'] == {}
    assert r['attempted_sources'] == ['tencent']
    assert 'conn reset' in r['error']


def test_熔断源被跳过且不影响其它源():
    p1 = _Prov('tencent', {'a': _quote('a', 1.0)})
    p2 = _Prov('eastmoney', {'b': _quote('b', 2.0, source='eastmoney')})
    m = _manager([p1, p2], broken={'tencent'})
    r = m.get_quotes(['a', 'b'])
    assert set(r['data']) == {'b'}, '熔断源不参与，其余源照常补齐'
    assert r['missing_symbols'] == ['a']


def test_空入参不触网():
    m = _manager([_Prov('tencent', {'a': _quote('a', 1.0)})])
    r = m.get_quotes([])
    assert r['success'] is True and r['data'] == {}
    assert m.quote_providers[0].seen == []


# --------------------------- ③ 消费侧真的走批量 ---------------------------

def test_投递到账户路径的是批量入口(monkeypatch):
    import qs_trading.application.services.simulation_service as sim_mod

    calls = []

    class _Svc:
        def __init__(self):
            pass

        def get_realtime_quotes(self, symbols):
            calls.append(list(symbols))
            return {'a': _quote('a', 3.0), 'b': _quote('b', 4.0)}

        def get_realtime_quote(self, symbol):  # 若被调用即为回归
            raise AssertionError('账户路径不得再逐只取价')

    monkeypatch.setattr(sim_mod, 'RealtimeQuoteService', _Svc) if hasattr(sim_mod, 'RealtimeQuoteService') else None
    import qs_market_data.application.services.realtime_quote_service as rq_mod
    monkeypatch.setattr(rq_mod, 'RealtimeQuoteService', _Svc)

    svc = sim_mod.SimulationService.__new__(sim_mod.SimulationService)

    class _L:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

    svc.logger = _L()
    prices, timestamps = svc._fetch_current_prices(['a', 'b'])
    assert calls == [['a', 'b']], f'必须一次批量调用，实际 {calls}'
    assert prices == {'a': 3.0, 'b': 4.0}
    # 契约（2026-10-27，RFC 017 P0）：返回 (prices, timestamps)；mock 未设 timestamp → 空 dict，
    # 且不得残留在 svc 单例上（并发账户请求会互相覆盖）
    assert timestamps == {}
    assert getattr(svc, '_price_timestamps', None) is None


def test_批量接口使用manager批量入口():
    import qs_market_data.application.services.stock_data_service as sd_mod

    class _PM:
        def __init__(self):
            self.get_quote_calls = 0

        def get_quote(self, symbol):
            self.get_quote_calls += 1
            return {'success': True, 'data': _quote(symbol, 1.0)}

        def get_quotes(self, symbols):
            return {'success': True, 'data': {s: _quote(s, 5.0) for s in symbols},
                    'missing_symbols': [], 'source': 'tencent'}

    class _L:
        def info(self, *a, **k):
            pass

        def warning(self, *a, **k):
            pass

        def error(self, *a, **k):
            pass

    svc = sd_mod.StockDataService.__new__(sd_mod.StockDataService)
    svc.provider_manager = _PM()
    svc.logger = _L()
    got = svc.get_batch_quotes(['a', 'b'])
    assert svc.provider_manager.get_quote_calls == 0, '批量接口不得逐只调用 get_quote（那是假批量）'
    assert got['success'] is True
    assert len(got['data']['quotes']) == 2


# --------------------------- ④ IPv4 收敛 ---------------------------
def test_进程级收敛到IPv4(monkeypatch):
    import urllib3.util.connection as uc
    from qs_market_data.adapters.outbound.datasources import net_prefs

    orig = uc.allowed_gai_family
    try:
        assert net_prefs.prefer_ipv4() is True
        assert uc.allowed_gai_family() == socket.AF_INET, '必须真的收敛到 AF_INET（本机 IPv6 黑洞是 8s 的根因）'
        assert net_prefs.is_ipv4_preferred() is True
        # 幂等
        assert net_prefs.prefer_ipv4() is True
        monkeypatch.setenv('QUANTSYS_FORCE_IPV4', '0')
        assert net_prefs.prefer_ipv4() is False, '环境变量必须能关掉（排查真实 IPv6 问题用）'
    finally:
        uc.allowed_gai_family = orig


# --------------------------- ⑤ 慢源不烧光超时预算（2026-11-12 事故修复锁，w-09d7af23） ---------------------------
# 事故：akshare 盘前 stock_zh_a_spot_em 挂 44s（7 只 × 全市场表），agent 工具 20s 超时三连。
# 修复锁三件事：
#   a) akshare.get_quotes 只发**一次**全市场请求（不再逐只 ×7）；
#   b) 基类默认批量实现「全部异常且零结果」必须自报 last_error（系统性故障不得伪装成健康空）；
#   c) manager.get_quotes per-provider 超时预算：慢源记 failure 后立即转移到下一源。

def test_akshare批量只发一次全市场请求(monkeypatch):
    import pandas as pd
    from qs_market_data.adapters.outbound.datasources.providers.quote import akshare as ak_mod

    calls = []

    def fake_spot_em():
        calls.append(1)
        return pd.DataFrame({
            '代码': ['111111', '600887', '300677'],  # 含未请求的代码
            '名称': ['别的', '伊利股份', '英科医疗'],
            '最新价': [1.0, 26.66, 55.0],
            '今开': [1.0, 26.5, 55.63],
            '最高': [1.0, 26.74, 56.0],
            '最低': [1.0, 26.4, 54.0],
            '昨收': [1.0, 26.5, 55.0],
            '成交量': [100, 222222, 91739],
            '成交额': [1000.0, 333333.0, 444444.0],
            '涨跌幅': [0.0, 0.1, -0.2],
        })

    monkeypatch.setattr(ak_mod.ak, 'stock_zh_a_spot_em', fake_spot_em)
    p = ak_mod.AkshareQuoteProvider()
    got = p.get_quotes(['600887', '300677'])

    assert len(calls) == 1, f'批量必须只拉一次全市场表，实际 {len(calls)} 次 —— 逐只全市场抓取正是 44s 事故的形态'
    assert set(got.keys()) == {'600887', '300677'}, '本地过滤必须精确命中目标代码'
    assert got['600887'].price == pytest.approx(26.66)
    assert got['600887'].source == 'akshare'
    assert p.last_error is None, '有命中结果时不得自报错误'


def test_akshare批量空表必须自报last_error(monkeypatch):
    import pandas as pd
    from qs_market_data.adapters.outbound.datasources.providers.quote import akshare as ak_mod

    monkeypatch.setattr(ak_mod.ak, 'stock_zh_a_spot_em', lambda: pd.DataFrame())
    p = ak_mod.AkshareQuoteProvider()
    got = p.get_quotes(['600887'])
    assert got == {}
    assert p.last_error, '整批无数据必须自报 last_error，否则 manager 记 empty 不记 failure，健康分永远不掉'


def test_基类默认批量全部异常必须自报last_error():
    from qs_market_data.adapters.outbound.datasources.base import QuoteProvider

    class P(QuoteProvider):
        @property
        def name(self):
            return 'stub'

        def get_quote(self, symbol):
            raise RuntimeError('conn reset')

    p = P()
    got = p.get_quotes(['a', 'b'])
    assert got == {}
    assert p.last_error and 'conn reset' in p.last_error, (
        '全部标的异常且零结果 = 系统性故障，必须经 last_error 暴露给 manager 记 failure；'
        '否则慢源/坏源被当成"健康空"永远排在故障转移第一位'
    )


def test_基类默认批量部分成功不报错误():
    from qs_market_data.adapters.outbound.datasources.base import QuoteProvider

    class P(QuoteProvider):
        @property
        def name(self):
            return 'stub'

        def get_quote(self, symbol):
            if symbol == 'bad':
                raise RuntimeError('boom')
            return _quote(symbol, 10.0, source='stub')

    p = P()
    got = p.get_quotes(['a', 'bad', 'b'])
    assert set(got.keys()) == {'a', 'b'}
    assert p.last_error is None, '部分成功属正常路径，不得误报错误（2026-09-11 空结果降权教训）'


def test_慢源超时后立即转移到下一源():
    import time as _time

    failures = []

    class _SlowProv:
        name = 'slow'
        last_error = None

        def get_quotes(self, symbols):
            _time.sleep(2.0)  # 远超预算
            return {s: _quote(s, 1.0, source='slow') for s in symbols}

    class _FastProv:
        name = 'fast'
        last_error = None

        def get_quotes(self, symbols):
            return {s: _quote(s, 2.0, source='fast') for s in symbols}

    m = _manager([_SlowProv(), _FastProv()])
    m._batch_quote_provider_timeout_s = 0.2
    m._record_failure = lambda name: failures.append(name)

    _t0 = _time.monotonic()
    r = m.get_quotes(['a', 'b'])
    elapsed = _time.monotonic() - _t0

    assert r['success'] is True and set(r['data']) == {'a', 'b'}
    assert all(q.source == 'fast' for q in r['data'].values()), '慢源结果不得采信（超时后其 future 未完成）'
    assert elapsed < 1.5, f'慢源不得烧光请求时长（实际 {elapsed:.1f}s），预算内必须转移到下一源'
    assert failures == ['slow'], '超时的源必须记 failure，让健康排序/熔断把它沉底'
    assert r['provider_errors'].get('slow'), '超时要向调用方暴露原因'
