# -*- coding: utf-8 -*-
"""sentiment 域真实数据源契约测试（2026-09-14，w-2129d492，REQ-48d896）

背景：`adapters/outbound/datasources/sentiment_data_source.py` 的 5 个方法曾是
`random` 生成的**伪造数据**（已删除），端点恒返回 success:true 且无来源标记。
本测试锁定改造后的契约：

1. 5 个 provider 方法返回真实结构；日期列被 stringify（JSON 安全，否则路由编码 500）；
2. 「健康空」（源正常、该标的确实无数据）与「硬失败」（传输故障→熔断）**严格区分**；
3. 上游损坏（`stock_report_fund_hold` 列错位）必须**拒绝返回**，
   绝不把错位表当数据 —— 这正是本次要消灭的「假数据」问题，只是来源换成上游；
4. 防回归源码护栏：伪造类与其 random 生成器不得复活。
"""
import sys
import types
from datetime import date, timedelta

import pandas as pd
import pytest

from adapters.outbound.datasources.providers.market import akshare as mk


@pytest.fixture(autouse=True)
def _clear_sentiment_cache():
    """清空模块级 TTL 缓存，避免测试间互相污染。"""
    mk._SENTIMENT_CACHE.clear()
    yield
    mk._SENTIMENT_CACHE.clear()


@pytest.fixture
def provider():
    return mk.AkshareMarketProvider()


def _install(monkeypatch, **funcs):
    """把假 akshare 注入 sys.modules（provider 内部是延迟 import，故可拦截）。"""
    stub = types.ModuleType('akshare')
    for name, fn in funcs.items():
        setattr(stub, name, fn)
    monkeypatch.setitem(sys.modules, 'akshare', stub)
    return stub


# ---------------------------------------------------------------------------
# 1. 十大股东
# ---------------------------------------------------------------------------

def test_top_holders_returns_records_and_stringifies_dates(monkeypatch, provider):
    df = pd.DataFrame([
        {'名次': 1, '股东名称': '某集团', '持股数': 100, '增减': '不变', '变动比率': None},
    ])
    _install(monkeypatch, stock_gdfx_top_10_em=lambda **kw: df)

    md = provider.get_top_holders('600519')
    assert md is not None
    data = md.data
    assert data['total'] == 1
    assert data['holder_type'] == 'top10'
    assert data['report_date'] is not None          # 实际报告期必须回填
    assert data['holders'][0]['股东名称'] == '某集团'
    assert md.source == 'akshare'


def test_top_holders_stringifies_date_columns(monkeypatch, provider):
    """日期列必须变字符串：datetime.date 不是 JSON 可序列化类型。"""
    df = pd.DataFrame([{'名次': 1, '股东名称': 'X', '截止日': date(2026, 6, 30)}])
    _install(monkeypatch, stock_gdfx_top_10_em=lambda **kw: df)

    md = provider.get_top_holders('600519')
    val = md.data['holders'][0]['截止日']
    assert isinstance(val, str) and val == '2026-06-30'


def test_top_holders_all_periods_parse_error_is_failure(monkeypatch, provider):
    """★ 独立审查 H1 修正：四期全部**解析失败** → 必须按故障上报，不是健康空。

    原实现把解析异常一律 continue，最后返回 empty:True 且 last_error=None →
    manager 走成功分支 → **东财兜底源根本不会被尝试**。而"接口改名/结构变更"
    正是以解析异常的形式出现，于是该源会永远安静返回空。
    （本测试此前断言的正是那个错误行为 —— 即"把 bug 锁成期望值"。）
    """
    def boom(**kw):
        raise ValueError('Length mismatch: Expected axis has 1 elements')

    _install(monkeypatch, stock_gdfx_top_10_em=boom)
    md = provider.get_top_holders('600519')
    assert md is None, '四期全解析失败必须报故障（否则 failover 不触发）'
    assert provider.last_error, '必须给出原因，便于排障与 provider_errors 展示'


def test_top_holders_all_periods_clean_empty_is_healthy_empty(monkeypatch, provider):
    """四期都"干净地空"（无异常）→ 才是健康空（与上一条严格区分）。"""
    _install(monkeypatch, stock_gdfx_top_10_em=lambda **kw: pd.DataFrame())

    md = provider.get_top_holders('600519')
    assert md is not None
    assert md.data['holders'] == [] and md.data['total'] == 0
    assert md.data['empty'] is True
    assert provider.last_error is None, '干净空不是故障'


def test_top_holders_transport_error_is_hard_failure(monkeypatch, provider):
    """传输故障 → None（计入熔断）——不能伪装成「无数据」。"""
    def boom(**kw):
        raise ConnectionError('upstream unreachable')

    _install(monkeypatch, stock_gdfx_top_10_em=boom)
    assert provider.get_top_holders('600519') is None


def test_top_holders_unknown_symbol_prefix_is_hard_failure(monkeypatch, provider):
    _install(monkeypatch, stock_gdfx_top_10_em=lambda **kw: pd.DataFrame([{'a': 1}]))
    assert provider.get_top_holders('not-a-code') is None


# ---------------------------------------------------------------------------
# 2. 股东户数
# ---------------------------------------------------------------------------

def test_holder_changes_sorted_newest_first(monkeypatch, provider):
    df = pd.DataFrame([
        {'股东户数统计截止日': '2013-03-22', '股东户数-本次': 69331},
        {'股东户数统计截止日': '2026-06-30', '股东户数-本次': 296404},
        {'股东户数统计截止日': '2025-03-31', '股东户数-本次': 250000},
    ])
    _install(monkeypatch, stock_zh_a_gdhs_detail_em=lambda **kw: df)

    md = provider.get_holder_changes('600519', periods=2)
    assert md.data['total'] == 2
    assert md.data['periods'][0]['股东户数统计截止日'] == '2026-06-30'
    assert md.data['periods'][1]['股东户数统计截止日'] == '2025-03-31'


# ---------------------------------------------------------------------------
# 3. 基金持股
# ---------------------------------------------------------------------------

def test_fund_holdings_quarter_filter(monkeypatch, provider):
    df = pd.DataFrame([
        {'基金名称': 'A基金', '截止日期': '2026-06-30', '持仓数量': 1},
        {'基金名称': 'B基金', '截止日期': '2025-12-31', '持仓数量': 2},
    ])
    _install(monkeypatch, stock_fund_stock_holder=lambda **kw: df)

    md = provider.get_fund_holdings('600519', '2026Q2')
    assert md.data['total'] == 1
    assert md.data['holdings'][0]['基金名称'] == 'A基金'
    assert md.data['quarter'] == '2026-06-30'


# ---------------------------------------------------------------------------
# 4. 基金重仓股（上游损坏必须拒绝）
# ---------------------------------------------------------------------------

def test_top_fund_stocks_rejects_misaligned_upstream(monkeypatch, provider):
    """上游「股票代码」列不是 6 位代码（实测错位：浮点 + 简称列装代码）→ 拒绝返回。

    这是本次改造的核心防线：宁可诚实失败，也不把错位表当真实数据返回。
    """
    broken = pd.DataFrame([
        {'序号': 1, '股票代码': -42049165018.7, '股票简称': '600519',
         '持有基金家数': '01', '持股总数': 1697, '持股变动比例': -20784953},
    ])
    _install(monkeypatch, stock_report_fund_hold=lambda **kw: broken)

    assert provider.get_top_fund_stocks('fund', 10) is None


def test_top_fund_stocks_valid_returns_records(monkeypatch, provider):
    good = pd.DataFrame([
        {'序号': 1, '股票代码': '600519', '股票简称': '贵州茅台',
         '持有基金家数': 992, '持股总数': 1697, '持股市值': 45030370},
    ])
    _install(monkeypatch, stock_report_fund_hold=lambda **kw: good)

    md = provider.get_top_fund_stocks('fund', 10)
    assert md is not None
    assert md.data['stocks'][0]['股票代码'] == '600519'


# ---------------------------------------------------------------------------
# 5. 千股千评
# ---------------------------------------------------------------------------

def test_stock_comment_missing_symbol_marks_empty(monkeypatch, provider):
    _install(monkeypatch, stock_comment_em=lambda: pd.DataFrame([
        {'代码': '000001', '名称': '平安银行', '机构参与度': 0.1},
    ]))
    md = provider.get_stock_comment('600519')
    assert md is not None
    assert md.data['empty'] is True and md.data['comment'] is None


def test_stock_comment_returns_row(monkeypatch, provider):
    _install(monkeypatch, stock_comment_em=lambda: pd.DataFrame([
        {'代码': '600519', '名称': '贵州茅台', '机构参与度': 0.4675, '综合得分': 75.2},
    ]))
    md = provider.get_stock_comment('600519')
    assert md.data['empty'] is False
    assert md.data['comment']['机构参与度'] == 0.4675


# ---------------------------------------------------------------------------
# 6. 内部人交易：复用已有实现 + TTL 缓存
# ---------------------------------------------------------------------------

def test_insider_trades_reuses_cached_market_df(monkeypatch, provider):
    """全市场 2.5 万行接口不得每个请求都打一次上游。"""
    calls = {'n': 0}

    def fetch():
        calls['n'] += 1
        return pd.DataFrame([{'股票代码': '600519', '变动日期': '2026-09-01', '变动人': '张三'}])

    _install(monkeypatch, stock_inner_trade_xq=fetch)
    assert provider.get_insider_trades('600519').data['total'] == 1
    assert provider.get_insider_trades('600519').data['total'] == 1
    assert calls['n'] == 1, '第二次应命中 TTL 缓存'


def test_insider_trades_absent_is_healthy_empty(monkeypatch, provider):
    """该股确实无内部交易记录 → 空 records（健康空），不是失败。"""
    _install(monkeypatch, stock_inner_trade_xq=lambda: pd.DataFrame([
        {'股票代码': '000001', '变动日期': '2026-09-01', '变动人': '李四'},
    ]))
    md = provider.get_insider_trades('600519')
    assert md is not None and md.data['total'] == 0


# ---------------------------------------------------------------------------
# 7. 防回归源码护栏
# ---------------------------------------------------------------------------

def test_mock_datasource_is_deleted():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert not (root / 'adapters/outbound/datasources/sentiment_data_source.py').exists(), \
        'SentimentDataSource（random 伪造实现）不得复活'
    assert not (root / 'adapters/outbound/repositories/sentiment_async_repository.py').exists(), \
        'SentimentAsyncRepository（绑定幻觉表 quant.sentiment_data）不得复活'


def test_no_mock_generators_anywhere_in_adapters():
    """`_generate_mock_*` 是「把随机数当真实数据」的实现标记，不得复活。"""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'adapters'
    offenders = []
    for path in root.rglob('*.py'):
        if '__pycache__' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        if '_generate_mock_' in text:
            offenders.append(str(path.relative_to(root)))
    assert not offenders, '检测到伪造数据生成器: %s' % offenders


def test_sentiment_routes_do_not_reference_deleted_modules():
    """路由层不得再 import 已删除的两个模块（含动态 import）。"""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'adapters/inbound'
    offenders = []
    for path in root.rglob('*.py'):
        if '__pycache__' in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if 'sentiment_data_source' in stripped or 'sentiment_async_repository' in stripped:
                offenders.append('%s:%d' % (path.relative_to(root), lineno))
    assert not offenders, '路由层仍在引用已删除模块: %s' % offenders

# ---------------------------------------------------------------------------
# 8. 路由层契约：真实数据 / 诚实降级（502）/ 不再假成功
# ---------------------------------------------------------------------------

import pytest as _pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeMarketData:
    def __init__(self, data):
        self.data = data


def _manager_result(data, ok=True, source='akshare'):
    return {
        'success': ok,
        'data': _FakeMarketData(data) if ok else None,
        'source': source if ok else None,
        'attempted_sources': ['akshare'],
        'empty_sources': [],
        'empty': False,
        'error': None if ok else 'All data providers failed',
        'provider_errors': {} if ok else {'akshare': 'boom'},
    }


@_pytest.fixture
def sentiment_client():
    from adapters.inbound.fastapi_app.routes.sentiment_async import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@_pytest.fixture
def batch_client():
    from adapters.inbound.fastapi_app.routes.p1_batch_async import sentiment_router
    app = FastAPI()
    app.include_router(sentiment_router)
    return TestClient(app)


def _patch_manager(monkeypatch, method, result):
    import adapters.outbound.datasources as ds_pkg

    class _M:
        def __getattr__(self, name):
            def _call(*a, **k):
                if name != method:
                    raise AssertionError('未预期的 manager 调用: %s' % name)
                return result
            return _call

    monkeypatch.setattr(ds_pkg, 'get_data_provider_manager', lambda: _M())


@_pytest.mark.parametrize('path,method,payload', [
    ('/api/stock/600519/top-holders', 'get_top_holders',
     {'symbol': '600519', 'holders': [{'名次': 1}], 'total': 1}),
    ('/api/stock/600519/holder-changes', 'get_holder_changes',
     {'symbol': '600519', 'periods': [{'股东户数-本次': 296404}], 'total': 1}),
    ('/api/stock/600519/fund-holdings', 'get_fund_holdings',
     {'symbol': '600519', 'holdings': [{'基金名称': 'A'}], 'total': 1}),
    ('/api/sentiment/top-fund-stocks', 'get_top_fund_stocks',
     {'fund_type': '基金持仓', 'stocks': [{'股票代码': '600519'}], 'total': 1}),
])
def test_sentiment_routes_return_data_with_source_marker(
    monkeypatch, sentiment_client, path, method, payload
):
    """每个端点都必须带 source/attemptedSources 标记 —— 调用方能分辨真假。"""
    _patch_manager(monkeypatch, method, _manager_result(payload))
    resp = sentiment_client.get(path)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['success'] is True
    assert body['data']['source'] == 'akshare'
    assert body['data']['degraded'] is False
    assert body['data']['attemptedSources'] == ['akshare']


def test_sentiment_route_returns_502_on_provider_failure(monkeypatch, sentiment_client):
    """数据源不可用 → 502 显式失败，绝不 success:true + 空/假数据。"""
    _patch_manager(monkeypatch, 'get_top_holders', _manager_result(None, ok=False))
    resp = sentiment_client.get('/api/stock/600519/top-holders')
    assert resp.status_code == 502
    body = resp.json()
    assert body['success'] is False
    assert 'attempted_sources' in body


def test_insider_trades_route_filters_by_days(monkeypatch):
    """insider 端点复用已有 provider 方法，不新增取数实现。

    该端点定义在 stock_async 的 router（不在 sentiment_async），故单独挂载。
    """
    from adapters.inbound.fastapi_app.routes.stock_async import router as stock_router
    app = FastAPI()
    app.include_router(stock_router)
    client = TestClient(app)
    old = (date.today() - timedelta(days=100)).isoformat()
    recent = (date.today() - timedelta(days=1)).isoformat()
    _patch_manager(monkeypatch, 'get_insider_trades', _manager_result({
        'symbol': '600519', 'total': 2,
        'records': [{'变动日期': recent, '变动人': '张三'},
                    {'变动日期': old, '变动人': '李四'}],
    }))
    resp = client.get('/api/stock/600519/insider-trades?days=30')
    assert resp.status_code == 200, resp.text
    records = resp.json()['data']['records']
    assert len(records) == 1 and records[0]['变动人'] == '张三'


def test_stock_sentiment_route_uses_comment_provider(monkeypatch, batch_client):
    _patch_manager(monkeypatch, 'get_stock_comment', _manager_result({
        'symbol': '600519', 'comment': {'机构参与度': 0.4675}, 'empty': False,
    }))
    resp = batch_client.get('/sentiment/stock/600519')
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']
    assert data['comment']['机构参与度'] == 0.4675
    assert data['empty'] is False
    assert '千股千评' in data['sourceNote']


def test_market_sentiment_route_reads_real_table(monkeypatch, batch_client):
    """市场情绪只读已在库的真实表，不再走幻觉表 quant.sentiment_data。"""
    import adapters.outbound.repositories.market_perception_repository as mpr

    class _Row:
        trade_date = date(2026, 9, 14)
        up_count, down_count, flat_count = 2278, 1714, 8
        ad_ratio, new_high_count, new_low_count = 1.33, 12, 3
        volume_ratio, total_turnover, volatility = 0.95, 1.2e12, 0.21
        fear_greed_index, coverage, partial = 60, 4000, False

    class _Repo:
        def __init__(self, *a, **k):
            pass

        def get_by_date(self, d):
            return _Row()

        def get_recent(self, days=5):
            return [_Row()]

    monkeypatch.setattr(mpr, 'MarketSentimentDailyRepository', _Repo)
    resp = batch_client.get('/sentiment/market')
    assert resp.status_code == 200, resp.text
    data = resp.json()['data']
    assert data['upCount'] == 2278 and data['fearGreedIndex'] == 60
    assert data['source'] == 'quant.market_sentiment_daily'
    # 旧契约键保留但标注 deprecated（而非静默消失）
    assert data['deprecated'] == ['bullish', 'bearish', 'neutral', 'total']


def test_market_sentiment_route_honest_empty(monkeypatch, batch_client):
    """库中确实无记录 → empty:true 明确标注（不是 success:true + 空对象）。"""
    import adapters.outbound.repositories.market_perception_repository as mpr

    class _Repo:
        def __init__(self, *a, **k):
            pass

        def get_by_date(self, d):
            return None

        def get_recent(self, days=5):
            return []

    monkeypatch.setattr(mpr, 'MarketSentimentDailyRepository', _Repo)
    resp = batch_client.get('/sentiment/market')
    body = resp.json()
    assert body['success'] is True
    assert body['data']['empty'] is True
    assert 'note' in body['data']

# ---------------------------------------------------------------------------
# 9. 「健康空」必须自描述（empty 标记）
# ---------------------------------------------------------------------------

def test_healthy_empty_carries_empty_flag(monkeypatch, provider):
    """源正常但该标的无数据 → records 为空**且** empty=True。

    只给 total=0 而不给 empty 标记，调用方无法区分「无数据」与「字段没返回」。
    """
    _install(monkeypatch, stock_zh_a_gdhs_detail_em=lambda **kw: pd.DataFrame())
    md = provider.get_holder_changes('600519')
    assert md is not None
    assert md.data['total'] == 0 and md.data['empty'] is True


def test_route_surfaces_inner_empty_flag(monkeypatch, sentiment_client):
    """内层 empty 必须冒泡到响应顶层（manager 的 empty 在成功分支不会置位）。"""
    _patch_manager(monkeypatch, 'get_fund_holdings', _manager_result(
        {'symbol': '600519', 'holdings': [], 'total': 0, 'empty': True}
    ))
    resp = sentiment_client.get('/api/stock/600519/fund-holdings')
    assert resp.status_code == 200
    body = resp.json()['data']
    assert body['empty'] is True
    assert body['degraded'] is False
    assert body['source'] == 'akshare'
