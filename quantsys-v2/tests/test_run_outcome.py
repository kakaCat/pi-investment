"""RunOutcome 契约测试（REQ-261004154902-a7cd · t1 / FR-1 / FR-2）。

覆盖验收标准：
① error 非空时 ok=False（无论 executed）；
② 跳过类 reason → skipped，失败类 reason → failed；
外加：空转（executed=True 但 not_due）不得算成功、未知 reason 必须当场拒绝、
to_dict 是既有字段超集且保留键优先。
"""
from __future__ import annotations

import pytest

from application.observability.run_outcome import (
    ACTION_HOLD,
    ACTION_REBALANCE,
    ALL_REASONS,
    ERROR_MAX_CHARS,
    FAILED_REASONS,
    REASON_FACTOR_EMPTY,
    REASON_MODEL_NOT_LOADED,
    REASON_NOT_DUE,
    REASON_NOT_TRADING_DAY,
    REASON_OK,
    REASON_REBALANCE_FAILED,
    SKIPPED_REASONS,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    RunOutcome,
)


# -- ① error 非空 → ok=False，无论 executed ---------------------------------
@pytest.mark.parametrize("executed", [True, False])
def test_error_makes_not_ok_regardless_of_executed(executed: bool) -> None:
    outcome = RunOutcome(
        executed=executed,
        reason=REASON_REBALANCE_FAILED,
        action=ACTION_REBALANCE,
        error="AttributeError: boom",
    )
    assert outcome.ok is False
    assert outcome.status == STATUS_FAILED
    assert outcome.to_dict()["error"] == "AttributeError: boom"


# -- ② 跳过类 → skipped；失败类 → failed ------------------------------------
def test_every_skipped_reason_maps_to_skipped() -> None:
    assert SKIPPED_REASONS, "跳过类不应为空"
    for reason in sorted(SKIPPED_REASONS):
        outcome = RunOutcome.skipped(reason)
        assert outcome.ok is False, reason
        assert outcome.status == STATUS_SKIPPED, reason


def test_every_failed_reason_maps_to_failed() -> None:
    assert FAILED_REASONS, "失败类不应为空"
    for reason in sorted(FAILED_REASONS):
        outcome = RunOutcome.failed(reason, "boom")
        assert outcome.ok is False, reason
        assert outcome.status == STATUS_FAILED, reason


def test_ok_reason_maps_to_success() -> None:
    outcome = RunOutcome.done(ACTION_REBALANCE)
    assert outcome.ok is True
    assert outcome.status == STATUS_SUCCESS
    assert outcome.to_dict()["reason"] == REASON_OK


# -- 关键回归：空转不许算成功（8/31–9/11 零成交却记 success 的那条路） --------
def test_executed_but_not_due_is_not_success() -> None:
    outcome = RunOutcome(
        executed=True, reason=REASON_NOT_DUE, action=ACTION_HOLD
    )
    assert outcome.ok is False
    assert outcome.status == STATUS_SKIPPED


def test_not_trading_day_via_skipped_factory() -> None:
    outcome = RunOutcome.skipped(REASON_NOT_TRADING_DAY)
    assert outcome.executed is False
    assert outcome.status == STATUS_SKIPPED


# -- 受控枚举：不许悄悄多出第四种状态 ---------------------------------------
def test_unknown_reason_is_rejected() -> None:
    with pytest.raises(ValueError):
        RunOutcome(executed=True, reason="whatever_i_like")


def test_reason_enum_is_closed_under_construction() -> None:
    with pytest.raises(ValueError):
        RunOutcome.failed(REASON_NOT_DUE, "boom")  # 跳过类不许走失败工厂


def test_skipped_factory_rejects_failed_reason() -> None:
    with pytest.raises(ValueError):
        RunOutcome.skipped(REASON_MODEL_NOT_LOADED)


def test_factories_cover_the_whole_enum_partition() -> None:
    assert SKIPPED_REASONS | FAILED_REASONS | {REASON_OK} == ALL_REASONS
    assert not (SKIPPED_REASONS & FAILED_REASONS)


# -- 序列化 ------------------------------------------------------------------
def test_to_dict_is_superset_of_legacy_contract() -> None:
    outcome = RunOutcome.done(ACTION_REBALANCE, detail={"days_to_next": 3})
    payload = outcome.to_dict()
    # 既有字段名必须原样保留（既有调用方/看板直接读）
    for key in ("executed", "reason", "action"):
        assert key in payload
    # 新增字段
    for key in ("ok", "status", "error"):
        assert key in payload
    # detail 平铺到顶层（旧契约本就把附加项平铺）
    assert payload["days_to_next"] == 3


def test_detail_cannot_override_reserved_keys() -> None:
    outcome = RunOutcome(
        executed=True,
        reason=REASON_OK,
        action=ACTION_REBALANCE,
        detail={"executed": False, "ok": False, "reason": "fake"},
    )
    payload = outcome.to_dict()
    assert payload["executed"] is True
    assert payload["ok"] is True
    assert payload["reason"] == REASON_OK


def test_from_dict_roundtrip() -> None:
    original = RunOutcome.failed(
        REASON_FACTOR_EMPTY, "no factors", action=ACTION_REBALANCE, detail={"symbols": 0}
    )
    restored = RunOutcome.from_dict(original.to_dict())
    assert restored == original


def test_error_is_truncated_to_limit() -> None:
    outcome = RunOutcome.failed(REASON_REBALANCE_FAILED, "x" * (ERROR_MAX_CHARS + 500))
    assert len(outcome.error) == ERROR_MAX_CHARS


def test_detail_must_be_dict() -> None:
    with pytest.raises(TypeError):
        RunOutcome(executed=True, reason=REASON_OK, detail=["not", "a", "dict"])
