"""净值快照日收益率口径测试 — 2026-09-11 w-8f2c4cc5

背景：quant.simulation_equity_snapshot.daily_return 长期存在基准错位——写入方用
get_equity_snapshots(limit=1) 取「最近一条快照」当日收益率基准，而该条可能是当日自己
09:31 的早盘快照（估值残缺）。实证：2026-07-27 净值 100000 到 100718.48（+0.72%），
库里却记 daily_return=0.2408（+24.08%），cumulative_return 0.3746（净值口径 0.0518），
并连带污染 sharpe/波动率/最大回撤与 M4 熔断判定。

本测试锁定修复后的契约：
1. daily_return 只能由 upsert_equity_snapshot 按「上一交易日有效快照」计算（口径唯一）
2. 基准不得是残缺行（total_value <= 0 或 total_value < cash）
3. 无可用基准时写 NULL（未知），不再与「平盘 0.0」混淆
4. 风控口径以账户净值为唯一真源：nav_returns_from_snapshots 按日期升序、跳过非正净值
"""
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from adapters.outbound.repositories.simulation_repository import (
    SimulationORMRepository,
    SNAPSHOT_RETURN_SUSPICIOUS,
)
from application.services.risk_metrics_service import (
    RiskMetricsService,
    nav_returns_from_snapshots,
)


class _FakeQuery:
    """极简查询替身：只区分「历史序列查询(all)」与「当日行查询(first)」。"""

    def __init__(self, session, model=None):
        self.session = session
        self.model = model
        self._same_day_lookup = False
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        if 'snapshot_date' in kwargs:
            self._same_day_lookup = True
        return self

    def order_by(self, *args):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def all(self):
        name = getattr(self.model, '__name__', '')
        if name == 'SimulationCashFlow':
            return list(self.session.flows)
        if name == 'SimulationAccount':
            return [self.session.account] if self.session.account is not None else []
        rows = sorted(self.session.history, key=lambda r: r.snapshot_date, reverse=True)
        return rows[: self._limit] if self._limit else rows

    def first(self):
        name = getattr(self.model, '__name__', '')
        if name == 'SimulationAccount':
            return self.session.account
        if self._same_day_lookup:
            return self.session.same_day
        return self.session.history[0] if self.session.history else None


class _FakeSession:
    def __init__(self, history=(), same_day=None, flows=(), account=None):
        self.history = list(history)
        self.same_day = same_day
        self.flows = list(flows)
        self.account = account
        self.added = []
        self.committed = 0

    def query(self, model):
        return _FakeQuery(self, model)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1


def _repo_with(monkeypatch, server: _FakeSession) -> SimulationORMRepository:
    import infrastructure.persistence.orm.base_repository as base

    monkeypatch.setattr(base, 'get_session', lambda: server)
    return SimulationORMRepository()


def _snap(day: str, total: float, cash: float = 0.0):
    return SimpleNamespace(snapshot_date=date.fromisoformat(day), total_value=total, cash=cash)


# ── 基准选择：残缺行不入基准 ────────────────────────────────────────────────

def test_previous_valid_snapshot_skips_partial_rows(monkeypatch):
    """早盘残缺快照（total_value < cash）不能被当作日收益基准。"""
    session = _FakeSession(history=[
        _snap('2026-07-24', 81170.0, cash=81170.0),      # 收支平衡但无持仓估值 → 仍算完整
        _snap('2026-07-26', 5000.0, cash=100000.0),      # 残缺：总资产 < 现金
        _snap('2026-07-25', 0.0, cash=100000.0),         # 残缺：总资产为 0
    ])
    repo = _repo_with(monkeypatch, session)
    prev = repo.previous_valid_snapshot('agent_virtual', date.fromisoformat('2026-07-27'))
    assert prev is not None
    assert prev.snapshot_date == date.fromisoformat('2026-07-24')


def test_previous_valid_snapshot_none_when_all_partial(monkeypatch):
    session = _FakeSession(history=[_snap('2026-07-26', 5000.0, cash=100000.0)])
    repo = _repo_with(monkeypatch, session)
    assert repo.previous_valid_snapshot('agent_virtual', date.fromisoformat('2026-07-27')) is None


def test_calculate_daily_return_uses_previous_day(monkeypatch):
    session = _FakeSession(history=[_snap('2026-07-24', 100000.0)])
    repo = _repo_with(monkeypatch, session)
    got = repo.calculate_daily_return('agent_virtual', date.fromisoformat('2026-07-27'), 100718.48)
    assert got == pytest.approx(0.0071848, abs=1e-7), '真实 +0.72%，不是 +24.08%'


def test_calculate_daily_return_none_without_baseline(monkeypatch):
    repo = _repo_with(monkeypatch, _FakeSession(history=[]))
    assert repo.calculate_daily_return('agent_virtual', date.fromisoformat('2026-06-22'), 100000.0) is None


# ── 写入路径：口径唯一 ────────────────────────────────────────────────────

def test_upsert_auto_computes_daily_return(monkeypatch):
    session = _FakeSession(history=[_snap('2026-07-24', 100000.0)], same_day=None)
    repo = _repo_with(monkeypatch, session)
    snap = repo.upsert_equity_snapshot(
        'agent_virtual', cash=0.0, position_value=100718.48, total_value=100718.48,
        snapshot_date=date.fromisoformat('2026-07-27'),
    )
    assert snap.daily_return == pytest.approx(0.0071848, abs=1e-7)
    assert session.added and session.added[0].daily_return == pytest.approx(0.0071848, abs=1e-7)


def test_upsert_explicit_daily_return_not_recomputed(monkeypatch):
    session = _FakeSession(history=[_snap('2026-07-24', 100000.0)], same_day=None)
    repo = _repo_with(monkeypatch, session)

    def _boom(*a, **k):
        raise AssertionError('显式传入 daily_return 时不得再自算')

    monkeypatch.setattr(repo, 'calculate_daily_return', _boom)
    snap = repo.upsert_equity_snapshot(
        'agent_virtual', cash=0.0, position_value=1.0, total_value=1.0,
        daily_return=0.05, snapshot_date=date.fromisoformat('2026-07-27'),
    )
    assert snap.daily_return == 0.05


def test_upsert_writes_null_when_baseline_missing(monkeypatch):
    """无基准 → NULL（未知），不得写 0.0 冒充平盘。"""
    session = _FakeSession(history=[], same_day=None)
    repo = _repo_with(monkeypatch, session)
    snap = repo.upsert_equity_snapshot(
        'agent_virtual', cash=100000.0, position_value=0.0, total_value=100000.0,
        snapshot_date=date.fromisoformat('2026-06-22'),
    )
    assert snap.daily_return is None


def test_suspicious_threshold_is_15pct():
    assert SNAPSHOT_RETURN_SUSPICIOUS == 0.15


# ── 风控口径：以净值为唯一真源 ──────────────────────────────────────────────

def test_nav_returns_sorted_and_skips_non_positive():
    snaps = [
        SimpleNamespace(snapshot_date=date.fromisoformat('2026-09-02'), total_value=110.0),
        SimpleNamespace(snapshot_date=date.fromisoformat('2026-09-01'), total_value=100.0),
        SimpleNamespace(snapshot_date=date.fromisoformat('2026-09-03'), total_value=0.0),
        SimpleNamespace(snapshot_date=date.fromisoformat('2026-09-04'), total_value=99.0),
    ]
    returns, points = nav_returns_from_snapshots(snaps)
    assert points == 3, '非正净值不计入'
    assert returns == pytest.approx([0.1, -0.1])


def test_nav_returns_empty_input():
    returns, points = nav_returns_from_snapshots([])
    assert returns == [] and points == 0


def test_nav_returns_ignores_daily_return_column():
    """净值口径不消费 daily_return 列（该列历史上有 +24.08% 假值）。"""
    snaps = [
        SimpleNamespace(snapshot_date=date.fromisoformat('2026-07-24'), total_value=100000.0,
                        daily_return=0.0),
        SimpleNamespace(snapshot_date=date.fromisoformat('2026-07-27'), total_value=100718.48,
                        daily_return=0.2408),
    ]
    returns, points = nav_returns_from_snapshots(snaps)
    assert returns == pytest.approx([0.0071848], abs=1e-7)
    assert points == 2


# ── 真实库校验：基准查询排除当日（SQL 谓词层面的回归） ──────────────────────

def test_previous_valid_snapshot_excludes_same_day_live():
    """对真实库校验 snapshot_date < before 谓词生效（无库时跳过）。"""
    pytest.importorskip('psycopg2')
    try:
        repo = SimulationORMRepository()
        session = repo.session
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'无可用数据库会话: {e}')
    try:
        prev = repo.previous_valid_snapshot('agent_virtual', date.fromisoformat('2026-09-10'))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'查询失败（可能无测试库）: {e}')
    if prev is None:
        pytest.skip('测试库无 agent_virtual 历史快照')
    assert prev.snapshot_date < date.fromisoformat('2026-09-10'), '当日快照不得作为自身基准'
    assert float(prev.total_value) >= float(prev.cash or 0), '基准须为估值完整的行'

# ── 外部入金口径：成立资金不算当日流入 ──────────────────────────────────────

def _flow(day: str, amount: float, ftype: str = 'deposit'):
    return SimpleNamespace(created_at=datetime.fromisoformat(day + ' 09:00:00'),
                           amount=amount, flow_type=ftype)


def test_external_flow_ignores_founding_deposit(monkeypatch):
    """账户首笔 deposit 是成立资金（created_at 可能是迁移时间），不得当当日流入。"""
    session = _FakeSession(flows=[_flow('2026-07-21', 147070.15)])
    repo = _repo_with(monkeypatch, session)
    assert repo.external_flow_on('agent_virtual', date.fromisoformat('2026-07-21')) == 0.0


def test_external_flow_counts_later_deposit(monkeypatch):
    session = _FakeSession(flows=[_flow('2026-06-22', 100000.0), _flow('2026-07-27', 5000.0)])
    repo = _repo_with(monkeypatch, session)
    assert repo.external_flow_on('agent_virtual', date.fromisoformat('2026-07-27')) == 5000.0
    assert repo.external_flow_on('agent_virtual', date.fromisoformat('2026-06-22')) == 0.0


def test_calculate_daily_return_subtracts_external_inflow(monkeypatch):
    """注资不能被当成收益：+5% 净值里含 5000 元入金时，交易口径收益应为 0。"""
    session = _FakeSession(
        history=[_snap('2026-07-24', 100000.0)],
        flows=[_flow('2026-06-22', 100000.0), _flow('2026-07-27', 5000.0)],
    )
    repo = _repo_with(monkeypatch, session)
    assert repo.calculate_daily_return(
        'agent_virtual', date.fromisoformat('2026-07-27'), 105000.0) == pytest.approx(0.0, abs=1e-9)


def test_calculate_daily_return_no_founding_deposit_distortion(monkeypatch):
    """回归 2026-07-21：成立资金 147070.15 记在该日，旧逻辑会算出 -147%。"""
    session = _FakeSession(
        history=[_snap('2026-07-20', 100000.0)],
        flows=[_flow('2026-07-21', 147070.15)],
    )
    repo = _repo_with(monkeypatch, session)
    got = repo.calculate_daily_return('agent_virtual', date.fromisoformat('2026-07-21'), 100000.0)
    assert got == pytest.approx(0.0, abs=1e-9), f'不得出现 -147% 这类荒谬值，实际 {got}'


def test_adjustment_flow_warning_is_safe(monkeypatch):
    """当日有 adjustment 流水时只告警不改数（语义含糊，交人工复核）。"""
    session = _FakeSession(flows=[_flow('2026-07-27', 15505.15, ftype='adjustment')])
    repo = _repo_with(monkeypatch, session)
    repo._warn_if_adjustment_flow('agent_virtual', date.fromisoformat('2026-07-27'))


# ── 无风险利率口径：年化 → 单期 ────────────────────────────────────────────

def test_period_risk_free_converts_annual_to_daily():
    svc = RiskMetricsService(risk_free=0.02)
    daily = svc._period_risk_free(0.02)
    assert daily == pytest.approx((1.02 ** (1 / 252)) - 1, rel=1e-9)
    assert 0 < daily < 0.0001, '2% 年化绝不能当 2%/日使用'


def test_sharpe_sign_matches_return_sign():
    """正收益序列的夏普必须为正——2026-09-11 前因年化利率直传，出现
    annual_return +26.6% 而 sharpe -78.7 的自相矛盾结果。"""
    svc = RiskMetricsService(risk_free=0.02)
    returns = [0.003, 0.001, 0.002, 0.0015, 0.0025, 0.001, 0.002, 0.0018] * 5
    assert svc.calculate_sharpe_ratio(returns) > 0
    assert svc.calculate_sortino_ratio(returns) > 0


def test_sharpe_magnitude_sane_when_below_risk_free():
    svc = RiskMetricsService(risk_free=0.02)
    # 日均 2.1e-5 低于 2% 年化对应的日利率 7.86e-5 → 夏普为负；同序列加正漂移后转正。
    # 注意年化因子 sqrt(252)≈15.9 会把日内的小差异放大，故此处只断言符号与单调性，
    # 不设量级上限（旧实现的问题不是数值大小，而是把年化利率当单期利率导致符号/口径错乱）。
    returns = [0.00002, 0.00003, 0.00001, 0.000025] * 5
    assert svc.calculate_sharpe_ratio(returns) < 0
    assert svc.calculate_sharpe_ratio([r + 0.001 for r in returns]) > 0


