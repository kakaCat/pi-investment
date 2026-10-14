"""净值窗口（交易日口径）在两个净值消费端点上的契约 — REQ-261006190953-fc43 卡 D

覆盖端点：
  · POST /api/risk/metrics           （adapters/inbound/fastapi_app/routes/analysis_async.py）
  · GET  /api/simulation/performance （adapters/inbound/fastapi_app/routes/simulation_async.py）

验收对应（卡 D ①~⑦）：
  ① `navPoints == window.trading_days`
  ② `window` 五字段齐备且类型正确
  ③ `nav_coverage.verified` 在场
  ④ 含周末/节假日行的账户：`equity_curve` 无这些行 且 `window.filtered_non_trading > 0`
  ⑤ `nav_coverage` 只反映**净值序列自身**缺口（基准序列的缺口不影响它）
  ⑥ `max_drawdown` 取自 `simulation_account` 的重算值（不是由净值曲线现算）
  ⑦ 既有响应键一个不缺（回归）

与"今天是不是交易日"无关：交易日集合一律打桩，桩打在**被调函数所在模块**
（`adapters.outbound.repositories.trading_calendar_repository.trading_day_set`）——
两条路由都是函数内惰性导入，故调用时取到的是桩。测试库 `quant_test` 的日历表为空，
本文件绝不依赖其内容（真库段落用哨兵账户自造自清，同
`tests/test_equity_snapshot_trading_day_gate.py` 的口径）。

真库段落的落库走 `upsert_equity_snapshot(..., force=True, commit=False)`：force 是
**测试构造历史序列**的正当用途（非交易日脏行正是本卡要证明会被读取端剔除的东西），
commit=False 避免仓储自动重算账户回撤（⑥ 要的是"账户表里那个值"）。
"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

#: 哨兵账户名：测试自造自清，不碰任何真实账户
ACCOUNT = '__req_fc43_cardd_test__'

# ---- 交易日集合（显式传入/打桩，绝不问"今天"）--------------------------------
SEP18 = date(2026, 9, 18)   # 周五
SEP21 = date(2026, 9, 21)
SEP22 = date(2026, 9, 22)
SEP23 = date(2026, 9, 23)
SEP24 = date(2026, 9, 24)   # 日历里有、序列里**缺**（⑤ 的"自身缺口"）
SEP25 = date(2026, 9, 25)
SEP28 = date(2026, 9, 28)
SAT = date(2026, 9, 26)     # 周六（脏行日之一）
SUN = date(2026, 9, 27)     # 周日（脏行日之一）
HOLIDAY = date(2026, 10, 1)  # 国庆休市（日历判定，不是周末）

#: 风险指标端点用的交易日集合（7 天，其中 09-24 在序列里缺席 → 缺口 1）
TRADING_DAYS = {SEP18, SEP21, SEP22, SEP23, SEP24, SEP25, SEP28}

# ---- 绩效端点（真库）用的交易日集合 ------------------------------------------
P14, P15, P16, P17, P18, P21 = (
    date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16),
    date(2026, 9, 17), date(2026, 9, 18), date(2026, 9, 21),
)
PERF_TRADING_DAYS = {P14, P15, P16, P17, P18, P21}
PERF_SAT = date(2026, 9, 19)
PERF_SUN = date(2026, 9, 20)
PERF_HOLIDAY = HOLIDAY      # 10-01（国庆）

WINDOW_KEYS = {'from', 'to', 'trading_days', 'filtered_non_trading', 'trading_day_source'}

#: 既有（卡 D 之前就有的）风险指标响应键 —— 回归基准，一个不许少
LEGACY_RISK_KEYS = {
    'sharpeRatio', 'sortinoRatio', 'calmarRatio', 'maxDrawdown', 'annualReturn',
    'annualVolatility', 'var95', 'cvar95', 'cumulativeReturn',
    'returnsSource', 'navPoints',
}


# ===========================================================================
# 打桩：交易日集合（唯一判据入口 = trading_calendar_repository.trading_day_set）
# ===========================================================================

def _patch_calendar(monkeypatch, days):
    """把 `trading_day_set` 换成返回固定集合的桩（days=None 模拟"日历不可得"）。"""
    monkeypatch.setattr(
        'adapters.outbound.repositories.trading_calendar_repository.trading_day_set',
        lambda exchange='ALL', *, force_refresh=False: days,
    )


def _client(router):
    """只装被测路由的 FastAPI 应用；请求收尾关闭 scoped_session。

    收尾关会话是老问题：路由线程的事务 idle in transaction 会阻塞后续测试文件的
    DDL（见 CLAUDE.md「测试库 DDL 会被 idle in transaction 连接锁住」）。
    """
    app = FastAPI()

    @app.middleware("http")
    async def _close_session_after_request(request, call_next):
        try:
            return await call_next(request)
        finally:
            from infrastructure.persistence.orm.config import close_session
            close_session()

    app.include_router(router)
    return app


@pytest.fixture()
def risk_client(monkeypatch):
    """POST /api/risk/metrics 的客户端 + 假净值仓储（`simulation_repo` 在被测模块里的名字）。"""
    from adapters.inbound.fastapi_app.routes import analysis_async

    repo = _FakeNavRepo(_nav_rows())
    monkeypatch.setattr(analysis_async, 'simulation_repo', repo)
    _patch_calendar(monkeypatch, TRADING_DAYS)
    with TestClient(_client(analysis_async.router)) as c:
        c.fake_repo = repo
        yield c
    from infrastructure.persistence.orm.config import close_session
    close_session()


@pytest.fixture()
def perf_client(monkeypatch):
    """GET /api/simulation/performance 的客户端（路由内 `SimulationORMRepository()` 换成真库实例）。"""
    from adapters.inbound.fastapi_app.routes import simulation_async

    repo = SimulationORMRepository()
    _purge(repo)
    monkeypatch.setattr(simulation_async, 'SimulationORMRepository', lambda *a, **k: repo)
    _patch_calendar(monkeypatch, PERF_TRADING_DAYS)
    with TestClient(_client(simulation_async.router)) as c:
        c.repo = repo
        yield c
    _purge(repo)
    try:
        repo.session.close()
    except Exception:  # noqa: BLE001 —— 收尾关连接失败不该让用例变红
        pass
    from infrastructure.persistence.orm.config import close_session
    close_session()


# ===========================================================================
# 假仓储（风险端点用）：语义逐条对齐真仓储的 `get_equity_snapshots`
#   · trading_days_only=False → 不过滤，limit = 快照**行数**
#   · trading_days_only=True 且 trading_days 非 None → 先按交易日过滤，limit = **交易日数**
#   · trading_days_only=True 且 trading_days is None → **不过滤**（不可得 ≠ 空集）
# ===========================================================================

def _nav_rows():
    """账户净值序列：6 个交易日行（缺 09-24）+ 3 行非交易日脏行。"""
    rows = [
        (SEP18, 100000.0), (SEP21, 101000.0), (SEP22, 100500.0),
        (SEP23, 102000.0), (SEP25, 102500.0), (SEP28, 103000.0),
        (SAT, 999999.0), (SUN, 999999.0), (HOLIDAY, 999999.0),
    ]
    return [SimpleNamespace(snapshot_date=d, total_value=v) for d, v in rows]


class _FakeNavRepo:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def get_equity_snapshots(self, account_name, limit=90, *,
                             trading_days_only=False, trading_days=None):
        self.calls.append({
            'account_name': account_name, 'limit': limit,
            'trading_days_only': trading_days_only, 'trading_days': trading_days,
        })
        rows = list(self.rows)
        if trading_days_only and trading_days is not None:
            rows = [r for r in rows if r.snapshot_date in trading_days]
        rows.sort(key=lambda r: r.snapshot_date, reverse=True)
        return rows[:limit]

    def get_all_positions(self, account_name, only_nonzero=True):
        return []


def _risk_metrics(client, **body):
    resp = client.post('/api/risk/metrics', json={'account_name': ACCOUNT, **body})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload['success'] is True, payload
    return payload['data']


def _assert_window_shape(window):
    """② 五字段齐备 + 类型正确。"""
    assert set(window) == WINDOW_KEYS, window
    assert isinstance(window['trading_days'], int)
    assert isinstance(window['filtered_non_trading'], int)
    assert isinstance(window['trading_day_source'], str)
    for key in ('from', 'to'):
        assert isinstance(window[key], str), (key, window[key])
        assert date.fromisoformat(window[key])  # ISO 日期，可解析


# ===========================================================================
# ① ② ③ ⑤ ⑦ —— POST /api/risk/metrics（account_name 口径）
# ===========================================================================

class TestRiskMetricsNavWindow:
    def test_nav_points_equals_window_trading_days(self, risk_client):
        """① `days` 是**交易日数**：6 个交易日行 → navPoints == window.trading_days == 6。

        若窗口按"快照行数"取（改造前的口径），未过滤的同一窗口里会混进周六/周日/国庆，
        交易日行不足 6 行，本断言即失败。
        """
        data = _risk_metrics(risk_client, days=6)
        assert data['returnsSource'] == 'account_nav'
        assert data['navPoints'] == 6
        assert data['window']['trading_days'] == data['navPoints'] == 6

    def test_window_has_five_typed_fields(self, risk_client):
        """② window 五字段齐备且类型正确。"""
        data = _risk_metrics(risk_client, days=6)
        _assert_window_shape(data['window'])
        assert data['window']['trading_day_source'] == 'trading-calendar'
        assert data['window']['from'] == SEP18.isoformat()
        assert data['window']['to'] == SEP28.isoformat()
        # 未过滤口径（limit=6）里落在非交易日的 3 行被剔除 → 计数必须 > 0
        assert data['window']['filtered_non_trading'] == 3

    def test_nav_coverage_verified_and_reports_series_gap(self, risk_client):
        """③ nav_coverage 在场且 verified；缺口 = 序列自身缺的交易日（09-24）。"""
        data = _risk_metrics(risk_client, days=6)
        cov = data['nav_coverage']
        assert cov['verified'] is True
        assert cov['points'] == 6
        assert cov['missing_count'] == 1
        assert cov['missing_trading_days'] == [SEP24.isoformat()]
        assert cov['trading_day_source'] == 'trading-calendar'

    def test_nav_coverage_ignores_benchmark_gap(self, risk_client):
        """⑤ nav_coverage 只反映净值序列自身缺口：基准序列再缺也不影响它。"""
        without = _risk_metrics(risk_client, days=6)
        with_bench = _risk_metrics(
            risk_client, days=6,
            benchmark_returns=[0.001, 0.0, 0.002, -0.001, 0.001],   # 基准自成一段、与净值缺口无关
        )
        # 基准确实被消费了（否则下面的"无影响"是空断言）
        assert 'beta' in with_bench
        assert with_bench['nav_coverage'] == without['nav_coverage']
        assert with_bench['nav_coverage']['missing_count'] == 1
        assert with_bench['window'] == without['window']

    def test_days_are_handed_to_the_repo_as_trading_day_count(self, risk_client):
        """①' 传参口径：`trading_days_only=True` + `limit=days` + 显式交易日集合。"""
        _risk_metrics(risk_client, days=6)
        calls = risk_client.fake_repo.calls
        assert calls, '路由没读净值序列'
        assert calls[0]['trading_days_only'] is True
        assert calls[0]['limit'] == 6
        assert calls[0]['trading_days'] == TRADING_DAYS
        # 第二次调用是"同一 limit 的未过滤口径"，用于数被剔除的非交易日行
        assert calls[1]['trading_days_only'] is False

    def test_legacy_response_keys_survive(self, risk_client):
        """⑦ 既有键一个不改：老键集合原样，新增只有 window / nav_coverage 两块。"""
        data = _risk_metrics(risk_client, days=6)
        assert LEGACY_RISK_KEYS <= set(data)
        assert set(data) - LEGACY_RISK_KEYS == {'window', 'nav_coverage'}

    def test_explicit_returns_path_unchanged(self, risk_client):
        """⑦ 回归：显式传 returns（无 account_name）的路径一个字节不改——不掺 window/nav_coverage。

        （本条是实测踩出来的：window 若在 account_name 分支里才赋值，显式口径下会
        UnboundLocalError → 整个端点 500。既有键的兼容性必须由用例守住。）
        """
        resp = risk_client.post('/api/risk/metrics', json={
            'returns': [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.008]})
        assert resp.status_code == 200, resp.text
        data = resp.json()['data']
        assert data['returnsSource'] == 'explicit_returns'
        assert set(data) == LEGACY_RISK_KEYS - {'navPoints'}
        assert 'window' not in data and 'nav_coverage' not in data

    def test_calendar_unavailable_does_not_filter_on_risk_endpoint(self, risk_client, monkeypatch):
        """③' 同一把锁也管风险端点：日历不可得 → 不过滤、如实声明未校验、缺口按 0 上报。"""
        _patch_calendar(monkeypatch, None)
        data = _risk_metrics(risk_client, days=6)
        assert data['window']['trading_day_source'] == 'unavailable'
        assert data['window']['filtered_non_trading'] == 0
        assert data['nav_coverage']['verified'] is False
        assert data['nav_coverage']['missing_count'] == 0
        assert data['window']['to'] == HOLIDAY.isoformat(), '不过滤 → 序列末尾的休市日行仍在窗口内'


# ===========================================================================
# ② ③ ④ ⑤ ⑥ —— GET /api/simulation/performance（真库 + 哨兵账户）
# ===========================================================================

def _purge(repo):
    """哨兵账户自清（子表先删）。"""
    from infrastructure.persistence.orm import models as m

    for model in ('SimulationEquitySnapshot', 'SimulationCashFlow', 'SimulationOrder',
                  'SimulationTrade', 'SimulationPosition', 'SimulationAccount'):
        cls = getattr(m, model, None)
        if cls is None:
            continue
        try:
            repo.session.query(cls).filter_by(account_name=ACCOUNT).delete()
        except Exception:  # noqa: BLE001 —— 表不存在/无该列时不该挡住清理
            repo.session.rollback()
    repo.session.commit()


def _seed_account_and_curve(repo, *, weekend_values_are_huge=True):
    """哨兵账户 + 6 个交易日净值行 + 3 行非交易日脏行（周末 2 + 国庆 1）。

    账户表的 `max_drawdown` 显式写成 -0.055，而曲线自身含一段 -20% 的下跌——
    两者刻意不同，⑥ 才能分辨 max_drawdown 到底取自哪一边。
    """
    repo.create_account(ACCOUNT, initial_capital=100000)
    curve = [(P14, 100000.0), (P15, 101000.0), (P16, 80000.0),
             (P17, 82000.0), (P18, 83000.0), (P21, 84000.0)]
    dirty_value = 999999.0 if weekend_values_are_huge else 70000.0
    dirty = [(PERF_SAT, dirty_value), (PERF_SUN, dirty_value), (PERF_HOLIDAY, dirty_value)]
    for day, total in curve + dirty:
        repo.upsert_equity_snapshot(
            account_name=ACCOUNT, cash=total, position_value=0.0, total_value=total,
            daily_return=0.0, cumulative_return=0.0, drawdown=0.0,
            snapshot_date=day, commit=False, force=True,
        )
    repo.session.commit()
    repo.update_account(
        ACCOUNT, cash_available=84000.0, total_value=84000.0, peak_value=101000.0,
        cumulative_return=-0.16, max_drawdown=-0.055,
    )
    return curve


def _performance(client):
    resp = client.get(f'/api/simulation/performance?account_name={ACCOUNT}')
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload['success'] is True, payload
    return payload['data']


class TestSimulationPerformanceNavWindow:
    def test_equity_curve_excludes_non_trading_rows(self, perf_client):
        """④ 周末/节假日行不进 equity_curve，且被剔除的行数如实上报。"""
        _seed_account_and_curve(perf_client.repo)
        data = _performance(perf_client)

        dates = [row['date'] for row in data['equity_curve']]
        assert len(dates) == 6
        assert dates == sorted(d.isoformat() for d in PERF_TRADING_DAYS)
        for dirty in (PERF_SAT, PERF_SUN, PERF_HOLIDAY):
            assert dirty.isoformat() not in dates, f'{dirty} 是非交易日脏行，不该出现在曲线里'
        # equity_curve 字段不变（卡面要求：只含交易日，字段一个不改）
        assert set(data['equity_curve'][0]) == {'date', 'total_value', 'cash', 'market_value', 'return'}

        assert data['window']['filtered_non_trading'] == 3
        assert data['window']['filtered_non_trading'] > 0
        assert data['window']['trading_days'] == len(data['equity_curve']) == 6

    def test_window_and_coverage_shape(self, perf_client):
        """② ③ 绩效端点同样返回 window 五字段与 nav_coverage（形状与风险端点一致）。"""
        _seed_account_and_curve(perf_client.repo)
        data = _performance(perf_client)

        _assert_window_shape(data['window'])
        assert data['window']['trading_day_source'] == 'trading-calendar'
        assert data['window']['from'] == P14.isoformat()
        assert data['window']['to'] == P21.isoformat()

        cov = data['nav_coverage']
        assert cov['verified'] is True
        assert cov['points'] == 6
        assert cov['missing_count'] == 0, '6 个交易日行一天不缺（缺口只看序列自身）'
        assert cov['missing_trading_days'] == []

    def test_max_drawdown_comes_from_simulation_account(self, perf_client):
        """⑥ max_drawdown = `simulation_account.max_drawdown`（重算值）× 100，不由曲线现算。

        曲线自身含 101000 → 80000 的下跌（约 -20.8%），账户表写的是 -0.055；
        响应报 -5.5 即证明取的是账户表的值。
        """
        _seed_account_and_curve(perf_client.repo)
        account = perf_client.repo.get_account(ACCOUNT)
        assert float(account.max_drawdown) == pytest.approx(-0.055)

        data = _performance(perf_client)
        assert data['max_drawdown'] == -5.5

    def test_calendar_unavailable_does_not_filter_or_zero_out(self, perf_client, monkeypatch):
        """③ 锁"不可得 ≠ 空集"：日历不可得时不过滤（序列不被清空）+ 如实声明未校验。"""
        _patch_calendar(monkeypatch, None)
        _seed_account_and_curve(perf_client.repo)
        data = _performance(perf_client)

        dates = [row['date'] for row in data['equity_curve']]
        assert len(dates) == 9, '日历不可得 ≠ 空集：静默按空集过滤会把整个序列清空'
        assert PERF_SAT.isoformat() in dates     # 未校验 → 退回改造前行为（原样返回）

        assert data['window']['trading_day_source'] == 'unavailable'
        assert data['window']['filtered_non_trading'] == 0, '没做过过滤，就不能报"剔除过"'
        assert data['nav_coverage']['verified'] is False
        assert data['nav_coverage']['missing_count'] == 0
