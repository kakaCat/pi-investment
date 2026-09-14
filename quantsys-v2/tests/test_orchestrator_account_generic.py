"""orchestrator 账户通用化测试（2026-09-14，w-32314d00，REQ-24e15d）

本文件由 tests/test_orchestrator_account_unify.py **改写**而来（未删除：原文件锁定的是
2026-07-24「盈利闭环改造」的决定——把编排器各阶段账户统一为 agent_virtual）。

为什么改写：那次"统一"在系统只有一只账户时是合理简化；但此后长出了 agent_brain /
v13 / v14 / v15 / chip / user_main 等账户，而"唯一账本"假设没跟着变 —— 账户级维护动作
（T+1 结转 / 持仓估值 / 净值快照 / 复盘取数）只覆盖 agent_virtual，其余账户的持仓市值
与账户总资产长期停在最后一次交易时的值。2026-09-05 先修了 T+1 结转（settle_t1_all），
本批把余下三处一并改为按 active 账户循环。

刻意不改的边界（防止"改一半引入新缺陷"）：
  · 市场级动作（数据更新 / 风格检测 / 信号生成 / 因子计算）仍然只跑一次；
  · 对外事件契约（signals_ready / daily_review 的载荷口径与投递目标）本批不动。
    逐账户投递（③）必须与 per-account 幂等键（②）**同时**落地：
    只做 ③ 会因全局布尔幂等标志让第一个账户抑制其余全部；
    只做 ② 会在单次投递下把同一事件推 N 次（正是 2026-09-08 修掉的重复推送）。
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from application.services.daily_orchestrator import DailyOrchestrator, TRADING_ACCOUNT


class _Acct:
    def __init__(self, name):
        self.account_name = name


class _FakeRepo:
    """模拟 ISimulationRepository：只实现编排器真正用到的四个方法"""

    def __init__(self, accounts=(TRADING_ACCOUNT, "agent_brain", "v13_simulation")):
        self._accounts = [_Acct(a) for a in accounts]
        self.settle_all_calls = 0
        self.trade_calls = []
        self.trades = {}

    def list_accounts(self, status="active"):
        assert status == "active", "口径必须是 active（与 settle_t1_all 一致）"
        return list(self._accounts)

    def settle_t1_all(self):
        self.settle_all_calls += 1
        return {a.account_name: 0 for a in self._accounts}

    def get_trades_by_account(self, account_name, start_date=None, end_date=None):
        self.trade_calls.append((account_name, start_date, end_date))
        return list(self.trades.get(account_name, []))


class _FakeEngine:
    """假 PaperTradingEngine：按账户建档，记录每只账户的重估入参"""

    instances = {}
    positions = {}

    def __init__(self, account_name):
        self.account_name = account_name
        self.revalued = None
        self.snapshot_calls = 0
        _FakeEngine.instances[account_name] = self

    def get_current_positions(self):
        return [dict(p) for p in _FakeEngine.positions.get(self.account_name, [])]

    def _update_position_values(self, prices):
        self.revalued = dict(prices)
        return True

    def take_daily_snapshot(self):
        self.snapshot_calls += 1
        return {"account": self.account_name}

    def get_performance_report(self):
        return {"total_value": 100.0, "cumulative_return": 0.0,
                "cumulative_return_pct": 0.0, "today_pnl": 0.0, "open_positions": 0}


class _FakeKlineRepo:
    def __init__(self, calls):
        self._calls = calls

    def get_latest_daily_klines_batch(self, symbols):
        self._calls.append(list(symbols))
        return {s: {"close": 10.0} for s in symbols}


def _make_orchestrator(repo):
    orch = DailyOrchestrator.__new__(DailyOrchestrator)
    orch.name = "test"
    orch.session = MagicMock()
    orch._simulation_repo = repo
    return orch


def _make_state(trade_date=date(2026, 9, 11)):
    state = MagicMock()
    state.trade_date = trade_date
    state.context = {}
    return state


def _reset_engines():
    _FakeEngine.instances = {}
    _FakeEngine.positions = {}


# ---------------------------------------------------------------------------
# 账户清单口径
# ---------------------------------------------------------------------------

def test_active_accounts_uses_active_status():
    repo = _FakeRepo(accounts=("agent_virtual", "agent_brain", "v15_simulation"))
    orch = _make_orchestrator(repo)
    assert orch._active_accounts(repo) == ["agent_virtual", "agent_brain", "v15_simulation"]


def test_active_accounts_falls_back_without_list_accounts():
    """旧仓储/测试替身没有 list_accounts 时，回退单账户（不比通用化前更差）"""

    class _Bare:
        def settle_t1_all(self):
            return {}

    repo = _Bare()
    orch = _make_orchestrator(repo)
    assert orch._active_accounts(repo) == [TRADING_ACCOUNT]


def test_active_accounts_falls_back_when_repo_raises():
    class _Boom:
        def list_accounts(self, status="active"):
            raise RuntimeError("db down")

    repo = _Boom()
    orch = _make_orchestrator(repo)
    assert orch._active_accounts(repo) == [TRADING_ACCOUNT]


# ---------------------------------------------------------------------------
# MARKET_CLOSE：估值更新覆盖全部 active 账户
# ---------------------------------------------------------------------------

def test_market_close_revalues_every_active_account():
    _reset_engines()
    _FakeEngine.positions = {
        "agent_virtual": [{"symbol": "002007"}],
        "agent_brain": [{"symbol": "601398"}, {"symbol": "002007"}],
        "v13_simulation": [],
    }
    repo = _FakeRepo()
    orch = _make_orchestrator(repo)
    kline_calls = []

    with patch("application.trading.paper_trading_engine.PaperTradingEngine", _FakeEngine), \
         patch("infrastructure.services.service_factory.ServiceFactory.get_kline_repository",
               return_value=_FakeKlineRepo(kline_calls)):
        result = orch._phase_market_close(_make_state())

    # 2026-09-05 起 T+1 结转已是全 active 账户
    assert repo.settle_all_calls == 1
    # 估值：每只 active 账户各建一次引擎（原实现只有 agent_virtual）
    assert set(_FakeEngine.instances) == {"agent_virtual", "agent_brain", "v13_simulation"}
    # 只用自己持仓的 symbol 重估（避免对每账户跑全市场行情）
    assert _FakeEngine.instances["agent_virtual"].revalued == {"002007": 10.0}
    assert _FakeEngine.instances["agent_brain"].revalued == {"002007": 10.0, "601398": 10.0}
    assert _FakeEngine.instances["v13_simulation"].revalued is None
    assert result["positions_updated_by_account"] == {
        "agent_virtual": 1, "agent_brain": 2, "v13_simulation": 0}
    # 取价一次做完：全部账户并集的 symbol 只查一批
    assert kline_calls == [["002007", "601398"]]


# ---------------------------------------------------------------------------
# POST_MARKET：快照/绩效逐账户，因子重算只跑一次
# ---------------------------------------------------------------------------

def test_post_market_snapshots_every_account_but_factors_once():
    _reset_engines()
    _FakeEngine.positions = {}
    repo = _FakeRepo()
    orch = _make_orchestrator(repo)
    factor_calls = []

    def _factor():
        factor_calls.append(1)
        return {"status": "ok"}

    with patch("application.trading.paper_trading_engine.PaperTradingEngine", _FakeEngine), \
         patch("application.services.scheduler_tasks.handle_factor_compute", _factor):
        result = orch._phase_post_market(_make_state())

    assert set(_FakeEngine.instances) == {"agent_virtual", "agent_brain", "v13_simulation"}
    for eng in _FakeEngine.instances.values():
        assert eng.snapshot_calls == 1, eng.account_name
    # 因子是市场级动作：多账户不得放大成 N 次
    assert len(factor_calls) == 1
    assert result["accounts_snapshotted"] == 3


# ---------------------------------------------------------------------------
# REVIEW：逐账户取当日成交；today_trades 不再恒为空
# ---------------------------------------------------------------------------

def test_review_queries_trades_for_every_active_account():
    repo = _FakeRepo()
    orch = _make_orchestrator(repo)
    state = _make_state()

    with patch("application.services.daily_orchestrator.agent_service") as mock_agent:
        orch._phase_review(state)

    assert [c[0] for c in repo.trade_calls] == [
        "agent_virtual", "agent_brain", "v13_simulation"]
    assert all(c[1] == "2026-09-11" and c[2] == "2026-09-11" for c in repo.trade_calls)
    # 事件投递本批不动：仍然只推一次
    mock_agent.notify_agent.assert_called_once()


def test_collect_today_trades_reads_orm_objects():
    """回归：原实现用 t.get(symbol)/t.get(side) 读 ORM 对象 → 异常被裸 except 吞掉，
    daily_review 载荷里的 today_trades **恒为空**。此处用真实 ORM 实例固定正确行为。"""
    from infrastructure.persistence.orm.models.simulation import SimulationTrade

    trade = SimulationTrade(symbol="601600", action="SELL", amount=Decimal("3752.00"))
    # 旧实现依赖的两个前提，真实 ORM 对象都不成立（实体证据，非推断）
    assert not hasattr(trade, "get")
    assert not hasattr(trade, "side")

    repo = _FakeRepo(accounts=(TRADING_ACCOUNT,))
    repo.trades[TRADING_ACCOUNT] = [trade]
    orch = _make_orchestrator(repo)
    out = orch._collect_today_trades(repo, [TRADING_ACCOUNT], date(2026, 9, 11))

    assert out[TRADING_ACCOUNT] == [
        {"symbol": "601600", "action": "SELL", "amount": 3752.0}]


def test_review_payload_carries_agent_virtual_trades_only():
    """对外契约不变：载荷 today_trades 只含 TRADING_ACCOUNT 的成交（③ 落地前）"""
    from infrastructure.persistence.orm.models.simulation import SimulationTrade

    repo = _FakeRepo()
    repo.trades[TRADING_ACCOUNT] = [
        SimulationTrade(symbol="002007", action="BUY", amount=Decimal("100.00"))]
    repo.trades["agent_brain"] = [
        SimulationTrade(symbol="601398", action="BUY", amount=Decimal("200.00"))]
    orch = _make_orchestrator(repo)
    state = _make_state()

    with patch("application.services.daily_orchestrator.agent_service") as mock_agent:
        orch._phase_review(state)

    payload = mock_agent.notify_agent.call_args[0][1]
    assert payload["today_trades"] == [
        {"symbol": "002007", "action": "BUY", "amount": 100.0}]
    assert "trades_by_account" not in payload, "本批不得改对外载荷结构"

# ---------------------------------------------------------------------------
# ② 复盘唤醒幂等键：全局布尔 → per-account 集合
# ---------------------------------------------------------------------------

def test_notified_accounts_reads_legacy_boolean():
    """旧状态行里存的是 True，语义 = 当时唯一的口径账户已推送"""
    orch = _make_orchestrator(_FakeRepo())
    assert orch._notified_accounts({}) == set()
    assert orch._notified_accounts({"daily_review_notified": None}) == set()
    assert orch._notified_accounts({"daily_review_notified": True}) == {TRADING_ACCOUNT}
    assert orch._notified_accounts({"daily_review_notified": False}) == set()


def test_notified_accounts_reads_per_account_mapping():
    orch = _make_orchestrator(_FakeRepo())
    ctx = {"daily_review_notified": {"agent_virtual": True, "agent_brain": False}}
    assert orch._notified_accounts(ctx) == {"agent_virtual"}


def test_review_skips_when_payload_account_already_notified():
    repo = _FakeRepo()
    orch = _make_orchestrator(repo)
    state = _make_state()
    state.context = {"daily_review_notified": {"agent_virtual": True}}

    with patch("application.services.daily_orchestrator.agent_service") as mock_agent:
        out = orch._phase_review(state)

    assert out == {"status": "already_notified", "skipped": True,
                   "notified_accounts": ["agent_virtual"]}
    mock_agent.notify_agent.assert_not_called()
    assert repo.trade_calls == [], "已跳过时不应再取数"


def test_review_skips_on_legacy_boolean_state_row():
    """兼容：升级前遗留的 True 状态行仍然生效，不会因形态变更重推一次"""
    orch = _make_orchestrator(_FakeRepo())
    state = _make_state()
    state.context = {"daily_review_notified": True}

    with patch("application.services.daily_orchestrator.agent_service") as mock_agent:
        out = orch._phase_review(state)

    assert out["skipped"] is True
    mock_agent.notify_agent.assert_not_called()


def test_review_marks_notified_per_account_and_preserves_existing():
    """落库形态是 {账户: True}，且并入时不得抹掉别的账户的已推送标记。

    这条正是 ③ 的前置：若写成整体覆盖，逐账户投递时先推的账户会把后推账户的
    标记清掉，导致后推账户被反复重推。"""
    repo = _FakeRepo()
    orch = _make_orchestrator(repo)
    state = _make_state()
    state.context = {"daily_review_notified": {"agent_brain": True}}

    with patch("application.services.daily_orchestrator.agent_service"):
        orch._phase_review(state)

    assert state.context["daily_review_notified"] == {
        "agent_brain": True, "agent_virtual": True}


def test_review_invokes_notifier_once_not_per_account():
    """本批**行为等价**的证明：账户集合有 3 只，投递仍恒为 1 次。

    若把门位提前改成"全部账户"，这里会变成 3 次 —— 即 2026-09-08 修掉的重复推送。"""
    repo = _FakeRepo()  # 3 只 active 账户
    orch = _make_orchestrator(repo)
    state = _make_state()

    with patch("application.services.daily_orchestrator.agent_service") as mock_agent:
        orch._phase_review(state)

    assert len(repo.trade_calls) == 3
    assert mock_agent.notify_agent.call_count == 1