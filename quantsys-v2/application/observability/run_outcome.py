"""运行结果契约 —— 「干了没干、成了没成、为什么没成」的唯一表述。

REQ-261004154902-a7cd · t1（FR-1 / FR-2）。

## 为什么需要它

2026-10-04 取证：`run_daily_check` 丢弃 `rebalance()` 的返回值、`rebalance` 的 `except`
把异常吞成 `{'success': False}`，于是「调仓抛错」对外表现为 `success`；同一账户
9/1–9/11 零成交、5 次日检全记 success。根因不是某一处写错，而是**失败不是一等公民**。

本模块把结果收成一个值对象，并给出**唯一**的判定：
- ``ok``：这次是否**真的干成了一件事**（不是"没报错"）；
- ``status``：该结果写进 `quant.scheduler_runs.status` 时应当取什么值。

## 三条判定口径（全仓唯一，禁止各调用方自己 if）

1. ``ok = executed and error is None and reason not in SKIPPED_REASONS``
   —— 「跳过」不算干成，出错更不算；
2. ``status``：跳过类 → ``skipped``；失败类 → ``failed``；``ok`` → ``success``；
3. ``reason`` 是**受控枚举**：写错值当场抛 ``ValueError``（不许悄悄多出第四种状态）。

## 兼容

``to_dict()`` 是既有返回体的**超集**：``executed`` / ``reason`` / ``action`` 三个键名不变
（既有调用方与看板直接读它们），``detail`` 里的键平铺到顶层（旧契约本就把
``days_to_next`` 之类的附加项平铺）；保留键优先，``detail`` 不得覆盖它们。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

__all__ = [
    "RunOutcome",
    "REASON_OK",
    "REASON_NOT_TRADING_DAY",
    "REASON_NOT_DUE",
    "REASON_MARKET_CLOSED",
    "REASON_MODEL_NOT_LOADED",
    "REASON_FACTOR_EMPTY",
    "REASON_REBALANCE_FAILED",
    "REASON_STOP_LOSS_FAILED",
    "REASON_OVERSELL_BLOCKED",
    "REASON_PENDING_EXPIRED",
    "REASON_MATCH_FAILED",
    "SKIPPED_REASONS",
    "FAILED_REASONS",
    "ALL_REASONS",
    "ACTION_REBALANCE",
    "ACTION_STOP_LOSS",
    "ACTION_HOLD",
    "ACTION_SKIPPED",
    "STATUS_SUCCESS",
    "STATUS_SKIPPED",
    "STATUS_FAILED",
]

# ----------------------------------------------------------------------------
# reason：受控枚举（唯一真源）
# ----------------------------------------------------------------------------
REASON_OK = "ok"
REASON_NOT_TRADING_DAY = "not_trading_day"
REASON_NOT_DUE = "not_due"
REASON_MARKET_CLOSED = "market_closed"
REASON_MODEL_NOT_LOADED = "model_not_loaded"
REASON_FACTOR_EMPTY = "factor_empty"
REASON_REBALANCE_FAILED = "rebalance_failed"
REASON_STOP_LOSS_FAILED = "stop_loss_failed"
REASON_OVERSELL_BLOCKED = "oversell_blocked"
REASON_PENDING_EXPIRED = "pending_expired"
#: 挂单撮合本身抛错（非护栏拒绝）——2026-10-04（t4）新增：
#: 单笔内部异常必须能被命名并外发，否则只能笼统报成别的失败原因。
REASON_MATCH_FAILED = "match_failed"

#: 合理跳过（不是失败，但**也绝不是 success**）
SKIPPED_REASONS = frozenset(
    {REASON_NOT_TRADING_DAY, REASON_NOT_DUE, REASON_MARKET_CLOSED}
)

#: 真失败（环境坏 / 执行抛错 / 风控拒绝）
FAILED_REASONS = frozenset(
    {
        REASON_MODEL_NOT_LOADED,
        REASON_FACTOR_EMPTY,
        REASON_REBALANCE_FAILED,
        REASON_STOP_LOSS_FAILED,
        REASON_OVERSELL_BLOCKED,
        REASON_PENDING_EXPIRED,
        REASON_MATCH_FAILED,
    }
)

ALL_REASONS = frozenset({REASON_OK}) | SKIPPED_REASONS | FAILED_REASONS

# ----------------------------------------------------------------------------
# action：既有字段名沿用（rebalance / stop_loss / hold / skipped）
# ----------------------------------------------------------------------------
ACTION_REBALANCE = "rebalance"
ACTION_STOP_LOSS = "stop_loss"
ACTION_HOLD = "hold"
ACTION_SKIPPED = "skipped"

# ----------------------------------------------------------------------------
# 调度态（写进 quant.scheduler_runs.status 的取值集合，不新增取值）
# ----------------------------------------------------------------------------
STATUS_SUCCESS = "success"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

#: error 字段截断上限（与 job_executor.classify_job_result 的口径一致）
ERROR_MAX_CHARS = 2000


@dataclass(frozen=True)
class RunOutcome:
    """一次自动链路运行的结果（不可变值对象）。

    Args:
        executed: 这次运行是否**真的执行完成**（沿用既有字段名）。
            **失败与跳过一律 False** —— 需求判定标准明写：调仓失败不得再出现
            「executed=True + action='rebalance'」这一形状（那正是旧代码骗人的组合）。
        reason: 受控枚举，见模块级 ``REASON_*``。
        action: ``rebalance`` / ``stop_loss`` / ``hold`` / ``skipped``。
        error: 异常原文（None 表示无异常）；超长会截断到 :data:`ERROR_MAX_CHARS`。
        detail: 附加信息（平铺进 :meth:`to_dict` 的顶层）。
    """

    executed: bool
    reason: str
    action: str = ACTION_HOLD
    error: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.reason not in ALL_REASONS:
            raise ValueError(
                f"未知 reason: {self.reason!r}；合法取值: {sorted(ALL_REASONS)}"
            )
        if self.error is not None:
            text = str(self.error)
            if len(text) > ERROR_MAX_CHARS:
                text = text[:ERROR_MAX_CHARS]
            object.__setattr__(self, "error", text)
        if not isinstance(self.detail, dict):
            raise TypeError("detail 必须是 dict")

    # -- 判定（全仓唯一） --------------------------------------------------
    @property
    def ok(self) -> bool:
        """这次是否**真的干成了一件事**。

        「跳过」不算干成（这正是 8/31–9/11 零成交却记 success 的那条路），
        出错更不算。
        """
        return (
            bool(self.executed)
            and self.error is None
            and self.reason not in SKIPPED_REASONS
        )

    @property
    def status(self) -> str:
        """写进 ``quant.scheduler_runs.status`` 的取值。"""
        if self.reason in SKIPPED_REASONS:
            return STATUS_SKIPPED
        if self.reason in FAILED_REASONS:
            return STATUS_FAILED
        return STATUS_SUCCESS if self.ok else STATUS_FAILED

    @property
    def is_skipped(self) -> bool:
        return self.reason in SKIPPED_REASONS

    # -- 序列化（既有字段超集） -------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """平铺为既有返回体的超集；保留键优先，``detail`` 不得覆盖。"""
        detail = {k: v for k, v in (self.detail or {}).items()}
        base = {
            "executed": self.executed,
            "ok": self.ok,
            "status": self.status,
            "action": self.action,
            "reason": self.reason,
            "error": self.error,
        }
        return {**detail, **base}

    # -- 构造便捷入口 ------------------------------------------------------
    @classmethod
    def done(cls, action: str, detail: Optional[Dict[str, Any]] = None) -> "RunOutcome":
        """真干成了一件（调仓/止损）。"""
        return cls(
            executed=True,
            reason=REASON_OK,
            action=action,
            error=None,
            detail=detail or {},
        )

    @classmethod
    def skipped(
        cls,
        reason: str,
        action: str = ACTION_SKIPPED,
        detail: Optional[Dict[str, Any]] = None,
    ) -> "RunOutcome":
        """合理跳过（非交易日 / 未到调仓周期 / 非交易时段）。"""
        if reason not in SKIPPED_REASONS:
            raise ValueError(f"{reason!r} 不是跳过类 reason；合法取值: {sorted(SKIPPED_REASONS)}")
        return cls(executed=False, reason=reason, action=action, error=None, detail=detail or {})

    @classmethod
    def failed(
        cls,
        reason: str,
        error: Any,
        action: str = ACTION_HOLD,
        executed: bool = False,
        detail: Optional[Dict[str, Any]] = None,
    ) -> "RunOutcome":
        """真失败：必须带 ``error``（这是它区别于跳过类的唯一凭据）。

        ``executed`` 默认 **False**：失败不是"执行完成"，且需求判定标准明确禁止
        失败时返回 ``executed=True + action='rebalance'`` 这一旧形状。
        """
        if reason not in FAILED_REASONS:
            raise ValueError(f"{reason!r} 不是失败类 reason；合法取值: {sorted(FAILED_REASONS)}")
        return cls(
            executed=executed,
            reason=reason,
            action=action,
            error=str(error),
            detail=detail or {},
        )

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RunOutcome":
        """从 :meth:`to_dict` 的产物还原（保留键优先）。"""
        reserved = {"executed", "ok", "status", "action", "reason", "error"}
        detail = {k: v for k, v in (payload or {}).items() if k not in reserved}
        return cls(
            executed=bool(payload.get("executed", False)),
            reason=payload.get("reason") or REASON_OK,
            action=payload.get("action") or ACTION_HOLD,
            error=payload.get("error"),
            detail=detail,
        )
