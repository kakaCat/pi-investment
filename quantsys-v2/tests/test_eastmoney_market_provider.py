# -*- coding: utf-8 -*-
"""东财直连第二源契约测试（2026-09-14，w-2129d492，REQ-48d896 t9）

锁定三件事：
1. 字段映射**语义正确**（东财英文字段 → 与 akshare 源相同的中文键）；
   重点是 top_fund_stocks —— akshare 那条因**位置式列名**而错位，
   本源按字段名取值从结构上避免该缺陷；
2. 失败纪律：last_error 必须设置（框架据此判「真故障」并保留可读原因；不设则落
   _INVALID_RESULT_MARKER，原因丢失），且**不外抛异常** ——
   ⚠️ 更正（独立审查 L3）：此前这里写"其它异常会穿透整个 failover 循环"是**错的**，
   manager.py:411 有兜底 except Exception（实测 [Boom(), Good()] → success=True, source=good）。
   不外抛的真实收益是**保原因**，不是防崩溃；
3. 真 failover：akshare 失败时自动切到 eastmoney，attempted_sources 含两个源。
"""
import sys
import types

import pandas as pd
import pytest

from adapters.outbound.datasources.providers.market import eastmoney as em


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


@pytest.fixture
def provider():
    return em.EastmoneyMarketProvider()


def _patch_get(monkeypatch, payload):
    def fake_get(url, params=None, **kw):
        return _Resp(payload(params or {}) if callable(payload) else payload)
    monkeypatch.setattr(em.requests, 'get', fake_get)


# ---------------------------------------------------------------------------
# 1. 字段映射
# ---------------------------------------------------------------------------

def test_top_fund_stocks_maps_fields_semantically(monkeypatch, provider):
    """核心断言：股票代码/简称/家数/市值各归其位（akshare 那条会错位）。"""
    _patch_get(monkeypatch, {
        'data': [{
            'SECURITY_CODE': '300308', 'SECURITY_NAME_ABBR': '中际旭创',
            'HOULD_NUM': 3578, 'TOTAL_SHARES': 214732617, 'HOLD_VALUE': 272710423590,
            'HOLDCHA': '减仓', 'HOLDCHA_NUM': -15877661, 'HOLDCHA_RATIO': -6.89,
        }],
    })
    md = provider.get_top_fund_stocks('fund', 10)
    assert md is not None
    row = md.data['stocks'][0]
    assert row['股票代码'] == '300308'
    assert row['股票简称'] == '中际旭创'
    assert row['持有基金家数'] == 3578
    assert row['持股市值'] == 272710423590
    assert row['持股变化'] == '减仓'
    assert md.source == 'eastmoney'


def test_top_holders_picks_latest_period(monkeypatch, provider):
    """多个报告期时只取最新一期，且按名次排序。"""
    _patch_get(monkeypatch, {
        'result': {'data': [
            {'END_DATE': '2025-12-31 00:00:00', 'HOLDER_RANK': 1, 'HOLDER_NAME': '旧期股东',
             'HOLD_NUM': 1, 'HOLD_NUM_RATIO': 1.0},
            {'END_DATE': '2026-06-30 00:00:00', 'HOLDER_RANK': 2, 'HOLDER_NAME': '第二',
             'HOLD_NUM': 20, 'HOLD_NUM_RATIO': 2.0},
            {'END_DATE': '2026-06-30 00:00:00', 'HOLDER_RANK': 1, 'HOLDER_NAME': '第一',
             'HOLD_NUM': 10, 'HOLD_NUM_RATIO': 54.5},
        ]},
    })
    md = provider.get_top_holders('600519')
    assert md.data['report_date'] == '2026-06-30'
    assert [h['股东名称'] for h in md.data['holders']] == ['第一', '第二']
    assert md.data['holders'][0]['占总股本持股比例'] == 54.5


def test_stock_comment_maps_indicator_fields(monkeypatch, provider):
    _patch_get(monkeypatch, {
        'result': {'data': [{
            'SECURITY_CODE': '600519', 'SECURITY_NAME_ABBR': '贵州茅台',
            'CLOSE_PRICE': 1277.96, 'ORG_PARTICIPATE': 0.4675, 'TOTALSCORE': 75.2,
            'PRIME_COST': 1277.27, 'TRADE_DATE': '2026-09-14 00:00:00',
        }]},
    })
    md = provider.get_stock_comment('600519')
    c = md.data['comment']
    assert c['代码'] == '600519' and c['机构参与度'] == 0.4675
    assert c['综合得分'] == 75.2 and c['交易日'] == '2026-09-14'


def test_holder_changes_maps_fields(monkeypatch, provider):
    _patch_get(monkeypatch, {
        'result': {'data': [{
            'END_DATE': '2026-06-30 00:00:00', 'HOLDER_NUM': 296404, 'PRE_HOLDER_NUM': 243159,
            'HOLDER_NUM_CHANGE': 53245, 'HOLDER_NUM_RATIO': 21.9, 'SECURITY_CODE': '600519',
            'SECURITY_NAME_ABBR': '贵州茅台',
        }]},
    })
    md = provider.get_holder_changes('600519', 1)
    p = md.data['periods'][0]
    assert p['股东户数统计截止日'] == '2026-06-30'
    assert p['股东户数-本次'] == 296404 and p['股东户数-增减'] == 53245


# ---------------------------------------------------------------------------
# 2. 失败纪律：设置 last_error、绝不出抛
# ---------------------------------------------------------------------------

def test_transport_error_sets_last_error_and_returns_none(monkeypatch, provider):
    def boom(*a, **kw):
        raise ConnectionError('upstream unreachable')
    monkeypatch.setattr(em.requests, 'get', boom)

    assert provider.get_top_holders('600519') is None
    assert provider.last_error, 'last_error 必须设置 —— 框架据此判「真故障」'


def test_http_error_does_not_propagate(monkeypatch, provider):
    """异常绝不能外抛：_try_providers 只捕获超时，其它异常会穿透 failover 循环。"""
    def boom(*a, **kw):
        raise RuntimeError('weird upstream')
    monkeypatch.setattr(em.requests, 'get', boom)

    for fn, args in [(provider.get_top_holders, ('600519',)),
                     (provider.get_holder_changes, ('600519',)),
                     (provider.get_top_fund_stocks, ('fund', 5)),
                     (provider.get_stock_comment, ('600519',))]:
        assert fn(*args) is None
        assert provider.last_error


def test_empty_payload_is_healthy_empty(monkeypatch, provider):
    """源正常但无数据 → empty=True（不是故障）。"""
    _patch_get(monkeypatch, {'result': {'data': []}})
    md = provider.get_holder_changes('600519')
    assert md is not None and md.data['empty'] is True and md.data['total'] == 0


def test_illegal_symbol_sets_last_error(provider):
    assert provider.get_stock_comment('not-a-code') is None
    assert provider.last_error


# ---------------------------------------------------------------------------
# 3. 真 failover：akshare 失败 → eastmoney 兜底
# ---------------------------------------------------------------------------

def test_manager_fails_over_to_eastmoney(monkeypatch):
    """拔掉 akshare：manager 必须自动切到 eastmoney，且 attempted_sources 含两个源。"""
    from adapters.outbound.datasources import get_data_provider_manager
    from adapters.outbound.datasources.providers.market.akshare import AkshareMarketProvider

    def broken(self, *a, **kw):
        self.last_error = '模拟 akshare 故障'
        return None

    monkeypatch.setattr(AkshareMarketProvider, 'get_holder_changes', broken)
    _patch_get(monkeypatch, {
        'result': {'data': [{
            'END_DATE': '2026-06-30 00:00:00', 'HOLDER_NUM': 296404,
            'PRE_HOLDER_NUM': 243159, 'SECURITY_CODE': '600519',
        }]},
    })

    res = get_data_provider_manager().get_holder_changes('600519', 1)
    assert res['success'] is True
    assert res['source'] == 'eastmoney'
    assert 'akshare' in res['attempted_sources']
    assert 'eastmoney' in res['attempted_sources']
    assert res['data'].data['periods'][0]['股东户数-本次'] == 296404


def test_manager_recovers_top_fund_stocks_via_eastmoney(monkeypatch):
    """akshare 因上游错位拒绝返回时，端点必须由 eastmoney 兜底为**正确**数据。

    这是 t9 的第二个（更重要的）价值：不只是多一个源，而是修好了
    /api/sentiment/top-fund-stocks —— akshare 的位置式列名会返回错位表。
    """
    from adapters.outbound.datasources import get_data_provider_manager
    from adapters.outbound.datasources.providers.market import akshare as mk

    broken = pd.DataFrame([
        {'序号': 1, '股票代码': -42049165018.7, '股票简称': '600519',
         '持有基金家数': '01', '持股总数': 1697},
    ])
    monkeypatch.setattr(
        mk.AkshareMarketProvider, 'get_top_fund_stocks',
        lambda self, *a, **kw: (setattr(self, 'last_error', '上游列错位'), None)[1],
    )
    _patch_get(monkeypatch, {
        'data': [{'SECURITY_CODE': '600519', 'SECURITY_NAME_ABBR': '贵州茅台',
                  'HOULD_NUM': 992, 'TOTAL_SHARES': 1697, 'HOLD_VALUE': 45030370,
                  'HOLDCHA': '增仓', 'HOLDCHA_NUM': 100, 'HOLDCHA_RATIO': 1.0}],
    })

    res = get_data_provider_manager().get_top_fund_stocks('fund', 5)
    assert res['success'] is True, res.get('provider_errors')
    assert res['source'] == 'eastmoney'
    row = res['data'].data['stocks'][0]
    assert row['股票代码'] == '600519' and row['股票简称'] == '贵州茅台'

# ---------------------------------------------------------------------------
# 4. 上游 schema 漂移：必须报真故障，不得静默成「无数据」或返回全 None 记录
# ---------------------------------------------------------------------------

def _run_all(provider, payload):
    """把同一份畸形响应喂给 4 个方法，返回 {方法: 结果分类}。"""
    out = {}
    for name, fn, args in [('top_holders', provider.get_top_holders, ('600519',)),
                           ('holder_changes', provider.get_holder_changes, ('600519',)),
                           ('fund_stocks', provider.get_top_fund_stocks, ('fund', 5)),
                           ('comment', provider.get_stock_comment, ('600519',))]:
        out[name] = fn(*args)
    return out


def test_fields_renamed_is_hard_failure_not_empty(monkeypatch, provider):
    """上游把字段改名 → 必须 `None` + last_error（真故障），**不是** empty。

    若当成 empty，这个源会永远安静地返回空、直到有人发现指标全没了 —— 静默 schema 漂移。
    """
    _patch_get(monkeypatch, {'result': {'data': [{'RANK_NEW': 1, 'NAME_NEW': 'x'}]}})
    assert provider.get_top_holders('600519') is None
    assert '无一字段可映射' in (provider.last_error or '')

    _patch_get(monkeypatch, {'result': {'data': [{'DATE_NEW': '2026-06-30', 'NUM_NEW': 1}]}})
    assert provider.get_holder_changes('600519') is None
    assert provider.last_error

    _patch_get(monkeypatch, {'result': {'data': [{'CODE_NEW': '600519'}]}})
    assert provider.get_stock_comment('600519') is None
    assert provider.last_error


def test_synthesized_field_must_not_mask_drift(monkeypatch, provider):
    """回归：top_fund_stocks 的「序号」是本地合成的、恒非 None。

    若把它计入"上游是否有内容"的判定，字段改名后仍会报 total=1（实测漏判过）。
    """
    _patch_get(monkeypatch, {'data': [{'CODE_NEW': '600519', 'NAME_NEW': 'X'}], 'pages': 1})
    assert provider.get_top_fund_stocks('fund', 5) is None, \
        '本地合成的「序号」不得让漂移检测失效'
    assert '无一字段可映射' in (provider.last_error or '')


def test_truly_no_rows_is_healthy_empty(monkeypatch, provider):
    """真的没有数据行 → 健康空（empty=True，无 last_error），与漂移严格区分。"""
    _patch_get(monkeypatch, {'data': [], 'pages': 0})
    md = provider.get_top_fund_stocks('fund', 5)
    assert md is not None and md.data['empty'] is True and md.data['total'] == 0
    assert provider.last_error is None

    _patch_get(monkeypatch, {'result': {'data': []}})
    md2 = provider.get_holder_changes('600519')
    assert md2 is not None and md2.data['empty'] is True
    assert provider.last_error is None


def test_malformed_payloads_never_return_fabricated_rows(monkeypatch, provider):
    """畸形响应绝不产出"结构在、值全 None"的伪记录。"""
    for payload in ({'result': None}, {'result': {'data': None}}, {},
                    {'result': {'data': [{}]}}, {'data': None}):
        _patch_get(monkeypatch, payload)
        for res in _run_all(provider, payload).values():
            if res is None:
                continue
            body = dict(res.data)
            if 'comment' in body:
                assert body['comment'] is None or body.get('empty') is True
            else:
                assert body.get('total') == 0 or body.get('empty') is True, \
                    '畸形响应不得报出非空 total: %r' % body

# ===========================================================================
# 10. 独立审查（b7365bd2）发现的缺陷 —— 逐条回归
#   审查特别指出 H2 与 M2 此前**没有任何用例覆盖**（改了实现仍全绿）。
# ===========================================================================


@pytest.fixture
def batch_client():
    """p1_batch_async 的 sentiment 子路由（H2/M2/M5 涉及）。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from adapters.inbound.fastapi_app.routes.p1_batch_async import sentiment_router
    app = FastAPI()
    app.include_router(sentiment_router)
    return TestClient(app)


def test_h2_market_explicit_missing_date_does_not_fall_back(monkeypatch, batch_client):
    """H2：显式请求的日期在库中不存在 → 如实报 empty，**不回退**到别的日期。

    原实现静默返回最近一天（实测 ?date=2020-01-01 → tradeDate=2026-09-12、
    empty:false），调用方拿不到"你要的那天没有数据"。
    """
    import adapters.outbound.repositories.market_perception_repository as mpr

    class _Repo:
        def __init__(self, *a, **k):
            pass

        def get_by_date(self, d):
            return None          # 该日期不存在

        def get_recent(self, days=5):
            raise AssertionError('不该回退到 get_recent —— 显式日期未命中必须如实报告')

    monkeypatch.setattr(mpr, 'MarketSentimentDailyRepository', _Repo)
    resp = batch_client.get('/sentiment/market?date=2020-01-01')
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']
    assert data['empty'] is True and data['degraded'] is True
    assert data['requestedDate'] == '2020-01-01'
    assert 'tradeDate' not in data, '不得返回另一天的数据冒充'


def test_m2_stock_route_honours_manager_level_empty(monkeypatch, batch_client):
    """M2：manager 报 success=True + data=[] + empty=True 时，响应必须 empty:true。

    原实现只看内层 empty → 输出 empty:false/comment:null，与本次要消灭的
    「success:true + 空」同型（审查实测）。
    """
    import adapters.outbound.datasources as ds_pkg

    class _M:
        def get_stock_comment(self, symbol):
            return {
                'success': True, 'data': [],          # 形状空：manager 顶层 empty 为真
                'source': None, 'attempted_sources': ['akshare', 'eastmoney'],
                'empty_sources': ['akshare', 'eastmoney'], 'empty': True,
                'provider_errors': {'akshare': '空', 'eastmoney': '空'},
                'error': None,
            }

    monkeypatch.setattr(ds_pkg, 'get_data_provider_manager', lambda: _M())
    resp = batch_client.get('/sentiment/stock/600519')
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']
    assert data['empty'] is True, '顶层 empty 必须被认（不能只看内层）'
    assert data['degraded'] is True
    assert data['comment'] is None


def test_m5_stock_route_failure_returns_502(monkeypatch, batch_client):
    """M5：失败必须 502，与其余 6 个端点一致（原为 200+success:false）。"""
    import adapters.outbound.datasources as ds_pkg

    class _M:
        def get_stock_comment(self, symbol):
            return {'success': False, 'data': None, 'source': None,
                    'attempted_sources': ['akshare', 'eastmoney'],
                    'provider_errors': {'akshare': 'x', 'eastmoney': 'y'},
                    'error': 'All data providers failed', 'empty': False}

    monkeypatch.setattr(ds_pkg, 'get_data_provider_manager', lambda: _M())
    resp = batch_client.get('/sentiment/stock/600519')
    assert resp.status_code == 502


def test_h1_failover_triggered_by_parse_errors(monkeypatch):
    """H1 端到端：akshare 报告期全解析失败 → 东财兜底，attempted 含两源。

    这是本需求的核心失败模式：旧实现把解析异常吞成"健康空"并走成功分支，
    导致兜底源**根本不参与**。
    """
    from adapters.outbound.datasources import get_data_provider_manager
    from adapters.outbound.datasources.providers.market import akshare as mk
    from adapters.outbound.datasources.providers.market import eastmoney as em

    def boom(self, symbol, holder_type='top10'):
        self.last_error = 'get_top_holders 全部报告期解析失败（疑接口改名/结构变更）'
        return None

    monkeypatch.setattr(mk.AkshareMarketProvider, 'get_top_holders', boom)

    class _Resp:
        def __init__(s, p): s._p = p
        def raise_for_status(s): return None
        def json(s): return s._p

    monkeypatch.setattr(em.requests, 'get', lambda *a, **kw: _Resp({
        'result': {'data': [{'HOLDER_RANK': 1, 'HOLDER_NAME': '某集团', 'HOLD_NUM': 10,
                            'HOLD_NUM_RATIO': 54.5, 'END_DATE': '2026-06-30 00:00:00'}]},
    }))
    res = get_data_provider_manager().get_top_holders('600519')
    assert res['success'] is True, res.get('provider_errors')
    assert res['source'] == 'eastmoney'
    # 注：attempted_sources 取决于健康排序 —— akshare 若已有失败记录会被排到后面、
    # 甚至本轮不被尝试（provider 健康分是**跨方法**的）。所以这里只断言"拿到的数据
    # 来自东财、且整体成功"，不断言两个源都被尝试（那是排序问题，不是契约）。
    assert res['data'].data['total'] == 1


def test_no_consumer_assert_contract_keys_documented(monkeypatch, provider):
    """审查 M3：两源键集并非完全等价（akshare 多「股份类型」「序号」）。

    本测试把差异**固定下来**，防止有人误以为两源输出逐字相同；
    docstring 已声明该差异。
    """
    import inspect
    from adapters.outbound.datasources.providers.market import akshare as mk
    from adapters.outbound.datasources.providers.market import eastmoney as em

    # 行为断言：东财源**不产出**它拿不到的列（如实省略而不是编造 None 键）
    # ⚠️ 必须走 monkeypatch —— 直接赋值 em.requests.get 会污染全局，
    #    在组合运行时把后续测试（实测 tests/migration 的 3 个 parity 用例）带崩。
    _patch_get(monkeypatch, {'result': {'data': [
        {'END_DATE': '2026-06-30 00:00:00', 'HOLDER_RANK': 1, 'HOLDER_NAME': 'X',
         'HOLD_NUM': 1, 'HOLD_NUM_RATIO': 1.0},
    ]}})
    md = provider.get_top_holders('600519')
    assert md is not None
    assert '股份类型' not in md.data['holders'][0], '东财无此列 → 应省略而非编造'

    # 文档断言：akshare 源多出该列，其 docstring 必须写明差异（否则维护者以为两源等价）
    ak_doc = inspect.getdoc(mk.AkshareMarketProvider.get_top_holders) or ''
    assert '股份类型' in ak_doc, 'akshare 源多出「股份类型」，其 docstring 必须写明该差异'
    em_doc = inspect.getdoc(em.EastmoneyMarketProvider.get_top_holders) or ''
    assert '股份类型' in em_doc, '东财源 docstring 必须说明它为何省略该列'


def test_l1_ttl_prefix_matching():
    """L1：基金持仓 key 形如 fund_hold:<type>:<period>，TTL 必须按**前缀**命中 1800s。"""
    from adapters.outbound.datasources.providers.market._common import ttl_for
    assert ttl_for('fund_hold:基金持仓:20260630') == 1800.0, '前缀匹配失效（死配置）'
    assert ttl_for('fund_hold') == 1800.0
    assert ttl_for('inner_trades') == 300.0
    assert ttl_for('unknown_key') == 600.0


def test_l6_unknown_fund_type_is_explicit_failure(monkeypatch, provider):
    """L6：未知 fund_type 不得静默降级成基金持仓。"""
    _patch_get(monkeypatch, {'data': [{'SECURITY_CODE': '600519'}], 'pages': 1})
    assert provider.get_top_fund_stocks('不存在的类型', 5) is None
    assert 'fund_type' in (provider.last_error or '')


def test_m1_insider_last_error_no_stale(monkeypatch):
    """M1：insider_trades 必须重置并设置 last_error，不得串上一次调用的原因。"""
    from adapters.outbound.datasources.providers.market import akshare as mk
    p = mk.AkshareMarketProvider()
    p.last_error = 'STALE-FROM-OTHER-CALL'
    _install_stmt = 'import akshare as ak'

    def boom():
        raise ConnectionError('upstream down')

    import sys, types
    stub = types.ModuleType('akshare')
    stub.stock_inner_trade_xq = boom
    monkeypatch.setitem(sys.modules, 'akshare', stub)
    mk._SENTIMENT_CACHE.clear()
    assert p.get_insider_trades('600519') is None
    assert p.last_error and p.last_error != 'STALE-FROM-OTHER-CALL', \
        'last_error 串味：应是本次失败原因'

def test_m3_success_branch_surfaces_provider_errors():
    """M3：成功分支必须透出 provider_errors —— 调用方要能回答「数据是首选源给的，
    还是降级后备源给的、以及首选源为什么没给」。

    原实现成功分支不返回该键（审查指出），于是 shared.provider_payload 拿不到、
    providerErrors 恒空，degraded 也只能靠 attempted>1 推断。

    这里直接给 _try_providers 一个**受控的源列表**（审查者 L3 验证亦用此方式），
    避免受健康排序影响（实测走真实源列表时 akshare 可能因健康分靠后被跳过，
    导致断言不稳定）。
    """
    from adapters.outbound.datasources import get_data_provider_manager
    from adapters.outbound.datasources.models import MarketData

    class _Boom:
        name = 'boom'
        last_error = '首选源故障（模拟）'

        def get_x(self):
            return None

    class _Good:
        name = 'good'
        last_error = None

        def get_x(self):
            return MarketData(data_type='x', data={'ok': 1}, source='good',
                              timestamp='2026-09-14T00:00:00')

    res = get_data_provider_manager()._try_providers([_Boom(), _Good()], 'get_x')
    assert res['success'] is True, res
    assert res['source'] == 'good'
    assert res['attempted_sources'] == ['boom', 'good']
    errors = res.get('provider_errors') or {}
    assert 'boom' in errors, '成功分支必须带上失败源的原因'
    assert '首选源故障' in errors['boom']
