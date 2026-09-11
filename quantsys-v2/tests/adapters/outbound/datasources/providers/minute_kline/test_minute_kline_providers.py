"""分钟线 provider 契约测试（monkeypatch 模块级 requests.get，不触网）

重点锁住**字段错位与量纲**两类静默失败（2026-09-11 已实证的事故类型）：
  腾讯字段序是 [时间, 开, **收**, 高, 低, 量]（第 2/3 位是开/收，不是开/高）
  腾讯非科创板成交量是「手」需 ×100，688/689 已是「股」不得换算
  OHLC 恒等式体检：字段错位必须 fail-loud，不得静默产出错位高低价
  新浪 volume 已是股、amount 直接返回（元）

**空结果 ≠ 故障**（2026-09-11 P10 契约对齐，见 providers/minute_kline/base.py 三态契约）：
  「该源无此标的 / 该时段无数据 / 窗口外」→ 返回 [] + last_note（健康路径），
  **不得**写 last_error —— 那会让 manager 计真故障、累计连续失败直至熔断该源。
  真故障（HTTP 异常 / 上游错误码 / 结构异常 / 映射体检失败 / 解析失败）保持
  last_error + return None，语义不变。
"""
from datetime import date, timedelta

import pytest

from adapters.outbound.datasources.providers.minute_kline import sina as sina_mod
from adapters.outbound.datasources.providers.minute_kline import tencent as tencent_mod
from adapters.outbound.datasources.providers.minute_kline.base import (
    bars_needed, bars_per_day, in_date_range, limit_klines, ohlc_sanity,
    period_label, period_minutes, to_prefixed_code,
)
from adapters.outbound.datasources.providers.minute_kline.sina import SinaMinuteKlineProvider
from adapters.outbound.datasources.providers.minute_kline.tencent import (
    TencentMinuteKlineProvider,
)
from domain.models.market_data import MinuteKline


class FakeResp:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self):
        return self._payload


def _bar(symbol, dt, o=10.0, h=10.5, l=9.5, c=10.2, v=100):
    return MinuteKline(symbol=symbol, trade_datetime=dt, open=o, high=h, low=l, close=c,
                       volume=v, amount=0.0, period='5m', source='x', timestamp='t')


# ───────────────────────────── base 工具契约 ─────────────────────────────

@pytest.mark.parametrize('period,expected', [
    ('1m', 1), ('5', 5), ('15min', 15), ('30m', 30), ('1h', 60), ('60m', 60),
])
def test_周期解析(period, expected):
    assert period_minutes(period) == expected


def test_非法周期必须抛错而不是静默兜底():
    with pytest.raises(ValueError):
        period_minutes('7m')
    with pytest.raises(ValueError):
        period_label(None)


def test_单日根数按240分钟连续竞价():
    assert bars_per_day('5m') == 48
    assert bars_per_day('60m') == 4
    assert bars_per_day('1m') == 240


@pytest.mark.parametrize('symbol,expected', [
    ('600519', 'sh600519'), ('688111', 'sh688111'), ('510300', 'sh510300'),
    ('399006', 'sh399006'), ('000001', 'sz000001'), ('300750', 'sz300750'),
    ('920023', 'bj920023'), ('830799', 'bj830799'),
    ('600519.SH', 'sh600519'),
])
def test_交易所前缀映射(symbol, expected):
    assert to_prefixed_code(symbol) == expected


@pytest.mark.parametrize('symbol', ['', None, '12345', 'ABCDEF', '99999', '234567'])
def test_无法映射的代码返回None由调用方fail_loud(symbol):
    assert to_prefixed_code(symbol) is None


def test_回溯根数以更早的一端为基准():
    """2026-09-11 实测教训：按 end_date 回溯会漏掉请求日自身（只回 28 根）。"""
    end = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
    start = (date.today() - timedelta(days=6)).strftime('%Y-%m-%d')
    assert bars_needed('5m', start, end, 100, 1000) > bars_needed('5m', end, end, 100, 1000)
    assert bars_needed('5m', start, end, 100, 1000) <= 1000, '必须受上游上限约束'


def test_回溯根数受上限保护():
    assert bars_needed('5m', '2020-01-01', date.today().strftime('%Y-%m-%d'), 10, 1023) == 1023
    assert bars_needed('5m', None, None, 240, 1000) == 240


def test_日期窗口与限量():
    assert in_date_range('2026-09-11 14:15:00', '2026-09-11', '2026-09-11') is True
    assert in_date_range('2026-09-10 14:15:00', '2026-09-11', None) is False
    assert in_date_range('2026-09-12 14:15:00', None, '2026-09-11') is False
    bars = [_bar('600519', f'2026-09-11 14:{i:02d}:00') for i in range(10)]
    assert len(limit_klines(bars, 3)) == 3 and limit_klines(bars, 3)[-1] is bars[-1]
    assert limit_klines(bars, 0) == bars


def test_OHLC恒等式体检能抓住字段错位():
    """把「开收高低」按直觉读成「开高低收」时会产出 high<close 的行——必须被抓住。"""
    good = [_bar('600519', '2026-09-11 14:15:00')]
    assert ohlc_sanity(good) is None
    bad = [_bar('600519', '2026-09-11 14:15:00', o=10.0, h=9.8, l=9.5, c=10.2)]
    assert 'OHLC' in (ohlc_sanity(bad) or '')


def test_少量脏数据不否定整批():
    bars = [_bar('x', '2026-09-11 14:00:00') for _ in range(10)]
    bars[0] = _bar('x', '2026-09-11 14:01:00', h=1.0)
    assert ohlc_sanity(bars) is None, '单点异常（<20%）不应整批失败'


# ────────────────────────────── 腾讯通道 ──────────────────────────────

def _tencent_payload(rows, code='sh600150', key='m5'):
    return {'code': 0, 'msg': '', 'data': {code: {key: rows, 'prec': 40.82}}}


def _mk_tencent_row(dt='202609111415', o=39.65, c=39.78, h=39.82, l=39.65, v=11796.0):
    return [dt, str(o), str(c), str(h), str(l), str(v), {}, '1.57']


def _patch_requests(monkeypatch, module, mapping):
    """mapping: dict 或 list（按调用顺序）"""
    calls = []

    def fake_get(url, **kwargs):
        calls.append({'url': url, **kwargs})
        resp = mapping.pop(0) if isinstance(mapping, list) else mapping
        return resp

    monkeypatch.setattr(module.requests, 'get', fake_get)
    return calls


def test_腾讯字段序必须按_时间开收高低量_映射(monkeypatch):
    """第 2/3 位是开/收：按直觉当开/高会让 high/low 错位且不报错。"""
    row = _mk_tencent_row(o=39.65, c=39.78, h=39.82, l=39.65)
    _patch_requests(monkeypatch, tencent_mod,
                    FakeResp(_tencent_payload([row])))
    bars = TencentMinuteKlineProvider().get_minute_klines('600150', '5m')
    assert len(bars) == 1
    bar = bars[0]
    assert (bar.open, bar.close, bar.high, bar.low) == (39.65, 39.78, 39.82, 39.65)
    assert bar.trade_datetime == '2026-09-11 14:15:00'
    assert bar.period == '5m' and bar.symbol == '600150'
    assert bar.source == 'tencent_minute'


def test_腾讯主板成交量是手_必须乘100(monkeypatch):
    row = _mk_tencent_row(v=11796.0, c=39.65, h=40.0, l=39.0)
    _patch_requests(monkeypatch, tencent_mod, FakeResp(_tencent_payload([row])))
    bar = TencentMinuteKlineProvider().get_minute_klines('600150', '5m')[0]
    assert bar.volume == 1179600, '主板上游是「手」，必须归一为「股」'
    assert bar.amount == round(1179600 * 39.65, 2)


def test_腾讯科创板成交量已是股不得换算(monkeypatch):
    row = _mk_tencent_row(v=101150.0)
    payload = _tencent_payload([row], code='sh688111')
    _patch_requests(monkeypatch, tencent_mod, FakeResp(payload))
    bar = TencentMinuteKlineProvider().get_minute_klines('688111', '5m')[0]
    assert bar.volume == 101150


def test_腾讯字段错位会被体检拦住(monkeypatch):
    """构造错位行：open=39.65, close=39.78 但把 39.78 当 high、39.65 当 low → 恒等式仍成立；
    真错位（high < close）必须被拦住并 fail-loud。"""
    rows = [_mk_tencent_row(h=39.60) for _ in range(5)]   # high=39.60 < close=39.78
    _patch_requests(monkeypatch, tencent_mod, FakeResp(_tencent_payload(rows)))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') is None
    assert '体检失败' in provider.last_error


def test_腾讯接口返回错误码必须显式失败(monkeypatch):
    _patch_requests(monkeypatch, tencent_mod, FakeResp({'code': 1, 'msg': 'param error'}))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') is None
    assert 'param error' in provider.last_error


def test_腾讯结构异常必须显式失败(monkeypatch):
    _patch_requests(monkeypatch, tencent_mod, FakeResp({'code': 0, 'data': {}}))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') is None
    assert '结构异常' in provider.last_error


def test_腾讯网络异常必须显式失败(monkeypatch):
    monkeypatch.setattr(tencent_mod.requests, 'get',
                        lambda *a, **kw: (_ for _ in ()).throw(ConnectionError('reset')))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') is None
    assert 'ConnectionError' in provider.last_error


def test_腾讯非法周期与非法代码不打上游(monkeypatch):
    calls = _patch_requests(monkeypatch, tencent_mod, FakeResp(_tencent_payload([])))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '7m') is None and '不支持' in provider.last_error
    assert provider.get_minute_klines('ABCDEF', '5m') is None and '前缀' in provider.last_error
    assert calls == []


def test_腾讯无数据返回空列表且只写last_note不写last_error(monkeypatch):
    """P10 核心：上游正常应答但该标的/周期没有数据 = 健康，不是故障。

    写成 last_error+None 会让 manager 计真故障 → 连续失败 → 熔断该源
    （把一个「这个查询它没有」升级成「这个源坏了」）。
    """
    _patch_requests(monkeypatch, tencent_mod, FakeResp(_tencent_payload([])))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') == []
    assert provider.last_error is None, '无数据不得写成 last_error（会触发熔断）'
    assert '腾讯无 600150 的 m5 数据' in provider.last_note, '诊断必须留在 last_note 里'


def test_腾讯窗口外同样算无数据而非故障(monkeypatch):
    rows = [_mk_tencent_row(dt='202001011000')]
    _patch_requests(monkeypatch, tencent_mod, FakeResp(_tencent_payload(rows)))
    provider = TencentMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m',
                                      start_date=date.today().strftime('%Y-%m-%d')) == []
    assert provider.last_error is None
    assert '均不在请求窗口' in provider.last_note


def test_腾讯每次调用重置last_note(monkeypatch):
    """provider 是长生命周期单例：上一次调用的说明不得泄漏到这一次"""
    _patch_requests(monkeypatch, tencent_mod, [FakeResp(_tencent_payload([])),
                                               FakeResp(_tencent_payload([_mk_tencent_row()]))])
    provider = TencentMinuteKlineProvider()
    provider.get_minute_klines('600150', '5m')
    assert provider.last_note
    provider.get_minute_klines('600150', '5m')
    assert provider.last_note == '' and provider.last_error is None


def test_腾讯窗口外的行被过滤(monkeypatch):
    today = date.today().strftime('%Y%m%d')
    rows = [_mk_tencent_row(dt=f'{today}1000'), _mk_tencent_row(dt='202001011000')]
    _patch_requests(monkeypatch, tencent_mod, FakeResp(_tencent_payload(rows)))
    bars = TencentMinuteKlineProvider().get_minute_klines(
        '600150', '5m', start_date=date.today().strftime('%Y-%m-%d'))
    assert [b.trade_datetime[:10] for b in bars] == [date.today().strftime('%Y-%m-%d')]


def test_腾讯请求参数带上市场前缀与周期(monkeypatch):
    calls = _patch_requests(monkeypatch, tencent_mod,
                            FakeResp(_tencent_payload([_mk_tencent_row()])))
    TencentMinuteKlineProvider().get_minute_klines('600150', '15m', limit=50)
    assert calls[0]['params']['param'].startswith('sh600150,m15,,')
    assert calls[0]['proxies'] == {'http': None, 'https': None}, '国内源必须绕过本机代理'


# ────────────────────────────── 新浪通道 ──────────────────────────────

def _sina_row(day='2026-09-11 14:15:00', o='39.670', h='39.830', l='39.640',
              c='39.820', v='1250028', a='49684335.1899'):
    return {'day': day, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v, 'amount': a}


def test_新浪字段映射与单位(monkeypatch):
    _patch_requests(monkeypatch, sina_mod, FakeResp([_sina_row()]))
    bars = SinaMinuteKlineProvider().get_minute_klines('600150', '5m')
    bar = bars[0]
    assert (bar.open, bar.high, bar.low, bar.close) == (39.67, 39.83, 39.64, 39.82)
    assert bar.volume == 1250028, '新浪 volume 已是股，不得再乘 100'
    assert bar.amount == pytest.approx(49684335.1899), 'amount 上游直接给（元），不得估算'
    assert bar.source == 'sina_minute'


def test_新浪不支持1分钟且不打上游(monkeypatch):
    calls = _patch_requests(monkeypatch, sina_mod, FakeResp([]))
    provider = SinaMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '1m') is None
    assert '不支持' in provider.last_error
    assert calls == []


def test_新浪空响应算无数据而非故障(monkeypatch):
    """P10：上游正常应答空数组 = 该标的无此周期数据（健康），不是源故障"""
    _patch_requests(monkeypatch, sina_mod, FakeResp([]))
    provider = SinaMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') == []
    assert provider.last_error is None, '无数据不得写成 last_error（会触发熔断）'
    assert '新浪无 600150 的 5 分钟数据' in provider.last_note


def test_新浪结构异常必须显式失败(monkeypatch):
    _patch_requests(monkeypatch, sina_mod, FakeResp({'unexpected': 'dict'}))
    provider = SinaMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') is None
    assert provider.last_error


def test_新浪坏行被跳过而不是炸掉整批(monkeypatch):
    payload = [_sina_row(), {'day': '2026-09-11 14:20:00', 'open': 'x', 'high': '1',
                             'low': '1', 'close': '1', 'volume': '1', 'amount': '1'}]
    _patch_requests(monkeypatch, sina_mod, FakeResp(payload))
    bars = SinaMinuteKlineProvider().get_minute_klines('600150', '5m')
    assert len(bars) == 1


def test_新浪网络异常必须显式失败(monkeypatch):
    monkeypatch.setattr(sina_mod.requests, 'get',
                        lambda *a, **kw: (_ for _ in ()).throw(TimeoutError('timeout')))
    provider = SinaMinuteKlineProvider()
    assert provider.get_minute_klines('600150', '5m') is None
    assert 'TimeoutError' in provider.last_error


def test_新浪请求参数(monkeypatch):
    calls = _patch_requests(monkeypatch, sina_mod, FakeResp([_sina_row()]))
    SinaMinuteKlineProvider().get_minute_klines('000001', '30m', limit=100)
    params = calls[0]['params']
    assert params['symbol'] == 'sz000001' and params['scale'] == 30 and params['ma'] == 'no'
    assert params['datalen'] >= 100


# ─────────────── 三源无数据不得进 failure 计数（manager 侧断言） ───────────────

def test_三源无数据时不计故障不影响熔断(monkeypatch):
    """(c) 端到端护栏：三个分钟源都「无数据」时，
    consecutive_failures 必须保持 0（不得累计到熔断阈值 10），failure 计数为 0，
    且 manager 返回 success=True+empty=True 而不是 All providers failed。

    修复前：三源无数据 → 各计 1 次 failure → 连续失败累计 → 10 次后熔断该源。
    """
    from adapters.outbound.datasources.manager import DataProviderManager
    from adapters.outbound.datasources.providers.minute_kline.database import (
        DatabaseMinuteKlineProvider,
    )

    # 注意：tencent_mod.requests 与 sina_mod.requests 是**同一个 module 对象**，
    # 分别 patch 会互相覆盖 → 必须按 url 分流
    empty_sina = 'quotes.sina.cn'

    def routed_get(url, **kwargs):
        if empty_sina in url:
            return FakeResp([])
        return FakeResp(_tencent_payload([]))

    monkeypatch.setattr(tencent_mod.requests, 'get', routed_get)

    class EmptyRepo:
        def get_latest_minute_kline(self, symbol):
            return None

        def get_minute_klines(self, symbol, start_dt, end_dt):
            return []

    m = DataProviderManager.__new__(DataProviderManager)   # 不构造真实 provider 链
    m.provider_timeout_seconds = 5
    m._failure_threshold = 3
    m._recovery_window = 5
    m._circuit_breaker_threshold = 10
    m._circuit_breaker_duration = 300
    m.minute_kline_providers = [
        TencentMinuteKlineProvider(), SinaMinuteKlineProvider(),
        DatabaseMinuteKlineProvider(EmptyRepo()),
    ]
    m.provider_stats = {p.name: {'success': 0, 'failure': 0, 'empty': 0,
                                 'consecutive_failures': 0, 'last_attempt_time': 0}
                        for p in m.minute_kline_providers}
    m._circuit_breakers = {}

    res = m.get_minute_klines('600150', '5m', start_date=date.today().strftime('%Y-%m-%d'))
    assert res['success'] is True and res['empty'] is True, '三源健康无数据 ≠ 全源失败'
    assert sorted(res['empty_sources']) == ['database_minute', 'sina_minute', 'tencent_minute']
    for p in m.minute_kline_providers:
        stats = m.provider_stats[p.name]
        assert stats['failure'] == 0, f'{p.name} 无数据不得计 failure'
        assert stats['consecutive_failures'] == 0, f'{p.name} 无数据不得累计连续失败（P10 核心）'
        assert stats['empty'] == 1
    # 诊断不丢：每个源的原生说明都要能读到
    errors = res['provider_errors']
    assert '腾讯无 600150 的 m5 数据' in errors['tencent_minute']
    assert '新浪无 600150 的 5 分钟数据' in errors['sina_minute']
    assert 'DB 无 600150 的分钟线缓存' in errors['database_minute']
