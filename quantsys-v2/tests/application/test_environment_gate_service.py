"""EnvironmentGateService 单测（2026-10-20，盯盘确认核验管线 · 环境前置判定）

覆盖三条验收：
  · 三维判定（指数/板块主线/资金氛围）与数据缺失 fail-open 分支；
  · 服务可导入、只依赖 MarketState 快照（AST 导入白名单 + 运行期禁 I/O）；
  · 拦截语义 = 只记录不动作，reason 可直接进通知（无买卖指令、单行、固定后缀）。

纪律：缺失数据只能 skipped，绝不能用 0 冒充事实（否则「涨停 0 家 → 冰点」式假信号）。
"""
import ast
import builtins
import inspect
import json
import socket

import pytest

from qs_watch.application.services.watch_engine.environment_gate_service import (
    DIM_CAPITAL,
    DIM_INDEX,
    DIM_SECTOR,
    DIMENSIONS,
    EnvironmentGateDecision,
    EnvironmentGatePolicy,
    EnvironmentGateService,
    GateDimensionVerdict,
)
from qs_watch.domain.watch.models import MarketState


def _state(**kw):
    """一份「环境正常」的完整快照，用例按需覆盖单维。"""
    base = dict(
        trade_date="2026-10-20",
        indices={"000300.SH": {"close": 3900.0, "change_pct": 0.60}},
        limit_up_count=42,
        max_streak=4,
        sentiment_score=58.0,
        fear_greed_index=62.0,
        advance_decline_ratio=1.30,
        volume_ratio=1.10,
        sectors={"半导体": 2.40, "银行": 0.30, "农林牧渔": -1.20},
        degraded=[],
    )
    base.update(kw)
    return MarketState(**base)


def _svc(policy=None):
    return EnvironmentGateService(policy)


# ── 正常放行 ────────────────────────────────────────────────

def test_all_three_dimensions_ok():
    decision = _svc().evaluate(_state())
    assert decision.blocked is False
    assert decision.reason == ""
    assert decision.skipped is False
    assert decision.skipped_dimensions == ()
    assert decision.missing == ()
    assert decision.verdict == "ok"
    assert decision.label == "环境正常"
    assert decision.ok is True
    assert decision.fail_open is False
    assert [v.dimension for v in decision.verdicts] == list(DIMENSIONS)
    assert all(v.status == "ok" for v in decision.verdicts)
    assert decision.dimension_verdict(DIM_INDEX).value == pytest.approx(0.60)
    assert decision.dimension_verdict(DIM_SECTOR).value == pytest.approx(2.40)
    assert decision.dimension_verdict(DIM_CAPITAL).value == pytest.approx(58.0)


def test_check_matches_evaluate_and_engine_tuple_shape():
    svc = _svc()
    blocked, reason = svc.check(_state())
    assert (blocked, reason) == (False, "")
    blocked2, reason2 = svc.check(_state(indices={"000300.SH": {"change_pct": -1.80}}))
    assert blocked2 is True and "只记录不动作" in reason2


# ── 维度一：指数涨跌 ────────────────────────────────────────

def test_index_drop_blocks_with_notification_ready_reason():
    decision = _svc().evaluate(_state(indices={"000300.SH": {"change_pct": -1.80}}))
    assert decision.blocked is True
    assert decision.reason == (
        "环境闸拦截：沪深300 跌 1.80%（触线 -1.50%），系统性风险日"
        "——本次信号只记录不动作"
    )
    assert decision.skipped is False
    assert decision.verdict == "blocked"
    assert decision.label == "环境拦截"
    assert decision.ok is False
    assert decision.dimension_verdict(DIM_INDEX).status == "blocked"


def test_index_surge_blocks_as_overheat():
    decision = _svc().evaluate(_state(indices={"000300.SH": {"change_pct": 3.20}}))
    assert decision.blocked is True
    assert decision.reason == (
        "环境闸拦截：沪深300 涨 3.20%（触线 +3.00%），过热追高保护"
        "——本次信号只记录不动作"
    )


@pytest.mark.parametrize(
    "pct,blocked",
    [(-1.50, True), (-1.49, False), (3.00, True), (2.99, False)],
)
def test_index_threshold_boundaries_are_inclusive(pct, blocked):
    decision = _svc().evaluate(_state(indices={"000300.SH": {"change_pct": pct}}))
    assert decision.blocked is blocked


def test_index_prefers_hs300_over_later_codes():
    """多指数同时在场时按 policy 优先级取沪深300，不被其他指数的暴跌误伤。"""
    state = _state(indices={
        "000300.SH": {"change_pct": 0.50},
        "000001.SH": {"change_pct": -2.00},
    })
    assert _svc().evaluate(state).blocked is False


def test_index_falls_back_when_preferred_code_missing():
    state = _state(indices={"399006.SZ": {"change_pct": -1.90}})
    decision = _svc().evaluate(state)
    assert decision.blocked is True
    assert "创业板指" in decision.reason
    assert decision.reason.startswith("环境闸拦截：")


def test_index_skipped_when_only_non_numeric():
    state = _state(indices={"000300.SH": {"change_pct": "n/a"}}, sectors={},
                   sentiment_score=None, fear_greed_index=None,
                   advance_decline_ratio=None)
    decision = _svc().evaluate(state)
    assert decision.blocked is False
    assert DIM_INDEX in decision.skipped_dimensions
    assert decision.dimension_verdict(DIM_INDEX).detail.startswith("指数快照缺失")


# ── 维度二：板块主线强度 ────────────────────────────────────

def test_sector_without_mainline_blocks():
    decision = _svc().evaluate(_state(sectors={"银行": 0.30, "农林牧渔": -1.20}))
    assert decision.blocked is True
    assert decision.reason == (
        "环境闸拦截：板块无主线（最强 银行 +0.30%，需 ≥ +1.00%），赚钱效应缺失"
        "——本次信号只记录不动作"
    )
    assert decision.dimension_verdict(DIM_SECTOR).value == pytest.approx(0.30)


@pytest.mark.parametrize("strongest,blocked", [(1.00, False), (0.99, True), (-0.01, True)])
def test_sector_threshold_boundaries(strongest, blocked):
    state = _state(sectors={"电子": strongest, "银行": -0.50})
    assert _svc().evaluate(state).blocked is blocked


def test_sector_ignores_non_numeric_entries():
    state = _state(sectors={"电子": None, "银行": "oops", "半导体": 1.50})
    decision = _svc().evaluate(state)
    assert decision.blocked is False
    assert decision.dimension_verdict(DIM_SECTOR).detail.startswith("最强板块 半导体")


# ── 维度三：资金氛围 ────────────────────────────────────────

def test_capital_cold_sentiment_blocks():
    decision = _svc().evaluate(_state(sentiment_score=18.0, fear_greed_index=16.0,
                                      advance_decline_ratio=1.10))
    assert decision.blocked is True
    assert decision.reason == (
        "环境闸拦截：资金氛围偏冷（情绪 18.0 < 30.0），风险偏好不足"
        "——本次信号只记录不动作"
    )


def test_capital_falls_back_to_fear_greed_when_sentiment_missing():
    state = _state(sentiment_score=None, fear_greed_index=15.0,
                   advance_decline_ratio=1.10)
    decision = _svc().evaluate(state)
    assert decision.blocked is True
    assert "情绪 15.0 < 30.0" in decision.reason
    assert decision.missing == ()


def test_capital_ad_ratio_blocks_even_when_sentiment_warm():
    """情绪分是均值，广度是事实：指数/情绪看着还行、个股普跌时仍要拦。"""
    decision = _svc().evaluate(_state(sentiment_score=58.0, fear_greed_index=62.0,
                                      advance_decline_ratio=0.30))
    assert decision.blocked is True
    assert "涨跌家数比 0.30 < 0.50" in decision.reason


@pytest.mark.parametrize(
    "sentiment,ad_ratio,blocked",
    [(30.0, 0.50, False), (29.9, 0.50, True), (30.0, 0.49, True), (58.0, 0.50, False)],
)
def test_capital_threshold_boundaries(sentiment, ad_ratio, blocked):
    state = _state(sentiment_score=sentiment, advance_decline_ratio=ad_ratio)
    assert _svc().evaluate(state).blocked is blocked


def test_capital_partial_missing_still_judges_and_records_missing():
    """部分字段缺失不等于整维跳过：在场数据（广度）足以发现真实风险。"""
    state = _state(sentiment_score=None, fear_greed_index=None,
                   advance_decline_ratio=0.30)
    decision = _svc().evaluate(state)
    assert decision.blocked is True
    assert decision.dimension_verdict(DIM_CAPITAL).missing == ("capital.sentiment",)
    assert decision.missing == ("capital.sentiment",)
    assert "capital.sentiment" not in decision.skipped_dimensions


# ── 数据缺失 fail-open + skipped 标注 ───────────────────────

def test_none_snapshot_fail_open_all_dimensions_skipped():
    decision = _svc().evaluate(None)
    assert decision.blocked is False
    assert decision.reason == ""
    assert decision.skipped is True
    assert decision.skipped_dimensions == DIMENSIONS
    assert decision.skipped_labels == ("指数涨跌", "板块主线强度", "资金氛围")
    assert decision.verdict == "skipped"
    assert decision.ok is None
    assert decision.fail_open is True
    assert all(v.status == "skipped" for v in decision.verdicts)
    assert _svc().check(None) == (False, "")


def test_empty_snapshot_fail_open_and_records_missing_inputs():
    decision = _svc().evaluate(MarketState())
    assert decision.blocked is False
    assert decision.reason == ""
    assert decision.skipped is True
    assert decision.skipped_dimensions == DIMENSIONS
    assert decision.missing == (
        "index.change_pct",
        "sector.pct",
        "capital.sentiment",
        "capital.advance_decline_ratio",
    )


def test_partial_missing_only_skips_that_dimension():
    state = _state(sectors={}, sentiment_score=None, fear_greed_index=None,
                   advance_decline_ratio=None)
    decision = _svc().evaluate(state)
    assert decision.blocked is False
    assert decision.reason == ""
    assert decision.skipped is True
    assert decision.skipped_dimensions == (DIM_SECTOR, DIM_CAPITAL)
    assert decision.dimension_verdict(DIM_INDEX).status == "ok"


def test_missing_data_alone_never_blocks():
    """全维缺失也必须放行——不能用「没数据」当事实去拦截。"""
    state = _state(indices={}, sectors={}, sentiment_score=None,
                   fear_greed_index=None, advance_decline_ratio=None)
    decision = _svc().evaluate(state)
    assert decision.blocked is False
    assert decision.reason == ""
    assert decision.skipped is True
    assert len(decision.skipped_dimensions) == 3


def test_blocked_alongside_skipped_keeps_both_annotations():
    """一维命中拦截、其余维缺数据：拦是拦，但 skipped 仍要标出来。"""
    state = _state(indices={"000300.SH": {"change_pct": -1.80}}, sectors={},
                   sentiment_score=None, fear_greed_index=None,
                   advance_decline_ratio=None)
    decision = _svc().evaluate(state)
    assert decision.blocked is True
    assert decision.skipped is True
    assert decision.verdict == "blocked"     # blocked 优先，skipped 不覆盖拦截结论
    assert decision.fail_open is False       # 已拦截时不算 fail-open
    assert decision.skipped_dimensions == (DIM_SECTOR, DIM_CAPITAL)
    assert "沪深300" in decision.reason


def test_nan_and_inf_are_treated_as_missing_not_facts():
    """NaN/Inf 是取数失败的另一种写法，必须按缺失处理（既不当 0，也不当事实）。"""
    state = _state(indices={"000300.SH": {"change_pct": float("nan")}},
                   sectors={"银行": float("nan")},
                   sentiment_score=float("nan"), fear_greed_index=None,
                   advance_decline_ratio=float("inf"))
    decision = _svc().evaluate(state)
    assert decision.blocked is False
    assert decision.skipped is True
    assert decision.skipped_dimensions == DIMENSIONS


def test_malformed_containers_fail_open_instead_of_crashing():
    state = _state(indices=["not-a-dict"], sectors=["not-a-dict"],
                   sentiment_score=None, fear_greed_index=None,
                   advance_decline_ratio=None)
    decision = _svc().evaluate(state)
    assert decision.blocked is False
    assert decision.skipped is True
    assert decision.skipped_dimensions == DIMENSIONS


def test_skipped_detail_carries_degraded_sources():
    state = _state(indices={}, degraded=["index_daily", "zt_pool"])
    decision = _svc().evaluate(state)
    detail = decision.dimension_verdict(DIM_INDEX).detail
    assert "指数快照缺失" in detail
    assert "index_daily" in detail and "zt_pool" in detail


# ── 拦截语义：只记录不动作 / 可直接进通知 ────────────────────

@pytest.mark.parametrize("state", [
    _state(indices={"000300.SH": {"change_pct": -1.80}}),
    _state(indices={"000300.SH": {"change_pct": 3.30}}),
    _state(sectors={"银行": 0.20, "农林牧渔": -1.00}),
    _state(sentiment_score=18.0, advance_decline_ratio=0.30),
    _state(indices={"000300.SH": {"change_pct": -2.20}},
           sectors={"银行": 0.10}, sentiment_score=12.0, advance_decline_ratio=0.20),
])
def test_reason_is_single_line_notification_ready(state):
    reason = _svc().evaluate(state).reason
    assert reason.startswith("环境闸拦截：")
    assert reason.endswith("——本次信号只记录不动作")
    assert reason.count("只记录不动作") == 1
    assert "\n" not in reason and reason == reason.strip()
    assert len(reason) <= 300
    # 拦截只记录、不代下单：reason 不得出现买卖动作词
    assert not any(word in reason for word in ("买入", "卖出", "加仓", "减仓", "下单"))


def test_multi_dimension_blocks_combine_three_causes_once():
    state = _state(indices={"000300.SH": {"change_pct": -1.80}},
                   sectors={"银行": 0.20, "农林牧渔": -1.00},
                   sentiment_score=18.0, advance_decline_ratio=0.30)
    decision = _svc().evaluate(state)
    assert decision.blocked is True
    assert "沪深300" in decision.reason
    assert "板块无主线" in decision.reason
    assert "资金氛围偏冷" in decision.reason
    assert decision.reason.count("只记录不动作") == 1
    # 维度顺序稳定（index → sector → capital），通知文案可回归
    assert decision.reason.index("沪深300") < decision.reason.index("板块无主线")
    assert decision.reason.index("板块无主线") < decision.reason.index("资金氛围偏冷")


def test_decision_bool_and_accessors():
    blocked = _svc().evaluate(_state(indices={"000300.SH": {"change_pct": -2.00}}))
    ok = _svc().evaluate(_state())
    assert bool(blocked) is True and blocked.is_blocked is True
    assert bool(ok) is False and ok.is_blocked is False
    assert blocked.verdict == "blocked" and blocked.ok is False
    assert ok.verdict == "ok" and ok.ok is True
    assert blocked.dimension_verdict("nope") is None
    # 解包兼容：直接 `blocked, reason = evaluate(state)` 也能用
    unpacked_blocked, unpacked_reason = blocked
    assert unpacked_blocked is True and unpacked_reason == blocked.reason
    assert blocked.as_tuple() == (True, blocked.reason)


def test_decision_to_dict_is_json_serializable():
    decision = _svc().evaluate(_state(indices={"000300.SH": {"change_pct": -1.80}}))
    payload = decision.to_dict()
    assert payload == decision.as_dict()
    assert payload["blocked"] is True
    assert payload["reason"] == decision.reason
    assert payload["verdict"] == "blocked"
    assert payload["label"] == "环境拦截"
    assert payload["ok"] is False
    assert payload["skipped"] is False
    assert payload["skipped_dimensions"] == []
    assert [v["dimension"] for v in payload["verdicts"]] == list(DIMENSIONS)
    assert payload["verdicts"][0]["label"] == "指数涨跌"
    assert payload["verdicts"][0]["verdict"] == "blocked"
    assert json.loads(json.dumps(payload, ensure_ascii=False))["blocked"] is True


def test_skipped_decision_serializes_fail_open_annotation():
    payload = _svc().evaluate(None).to_dict()
    assert payload["blocked"] is False
    assert payload["skipped"] is True
    assert payload["fail_open"] is True
    assert payload["ok"] is None
    assert payload["skipped_dimensions"] == list(DIMENSIONS)
    assert payload["skipped_labels"] == ["指数涨跌", "板块主线强度", "资金氛围"]


def test_convenience_entry_matches_service():
    from qs_watch.application.services.watch_engine.environment_gate_service import (
        check_environment,
    )

    state = _state(indices={"000300.SH": {"change_pct": -1.80}})
    assert check_environment(state).to_dict() == _svc().evaluate(state).to_dict()


# ── 策略可配 / 入参校验 ────────────────────────────────────

def test_policy_override_changes_verdict():
    state = _state(indices={"000300.SH": {"change_pct": -0.80}})
    assert _svc().evaluate(state).blocked is False
    strict = _svc(EnvironmentGatePolicy(index_drop_pct=-0.50))
    assert strict.evaluate(state).blocked is True

    sector_state = _state(sectors={"半导体": 2.40})
    assert _svc().evaluate(sector_state).blocked is False
    demanding = _svc(EnvironmentGatePolicy(sector_min_mainline_pct=3.0))
    assert demanding.evaluate(sector_state).blocked is True


@pytest.mark.parametrize("kwargs", [
    {"index_codes": ()},
    {"index_drop_pct": 0.5},
    {"index_surge_pct": -1.0},
    {"advance_decline_min": -0.1},
])
def test_policy_rejects_bad_thresholds(kwargs):
    with pytest.raises(ValueError):
        EnvironmentGatePolicy(**kwargs)


# ── 验收：可导入、仅依赖 MarketState、无 I/O ────────────────

def test_module_imports_only_marketstate_from_project():
    """AST 白名单：只允许标准库 dataclasses/typing + 领域快照模型。"""
    module = __import__(
        "qs_watch.application.services.watch_engine.environment_gate_service",
        fromlist=["EnvironmentGateService"],
    )
    tree = ast.parse(inspect.getsource(module))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert modules <= {
        "dataclasses",
        "math",
        "typing",
        "qs_watch.domain.watch.models",
    }


def test_service_has_no_repository_or_provider_dependency():
    params = list(inspect.signature(EnvironmentGateService.__init__).parameters)
    assert params == ["self", "policy"]
    assert list(inspect.signature(EnvironmentGateService.evaluate).parameters) == [
        "self", "state",
    ]
    assert list(inspect.signature(EnvironmentGateService.check).parameters) == [
        "self", "state",
    ]


def test_evaluate_performs_no_io(monkeypatch):
    """运行期禁 I/O：打开文件/建 socket 立即炸，正常与拦截两条路径都不得触碰。"""
    def _boom(*args, **kwargs):
        raise AssertionError("EnvironmentGateService 是纯判定，不得做 I/O")

    monkeypatch.setattr(builtins, "open", _boom)
    monkeypatch.setattr(socket, "socket", _boom)

    svc = _svc()
    assert svc.evaluate(_state()).blocked is False
    assert svc.evaluate(_state(indices={"000300.SH": {"change_pct": -1.80}})).blocked is True


def test_verdict_value_object_shape():
    verdict = GateDimensionVerdict(DIM_INDEX, "blocked", reason="x", value=-1.0)
    assert verdict.blocked is True and verdict.skipped is False
    assert verdict.label == "指数涨跌"
    assert verdict.verdict == "blocked"
    assert isinstance(verdict, GateDimensionVerdict)
    decision = EnvironmentGateDecision(False, "")
    assert decision.skipped_labels == ()
