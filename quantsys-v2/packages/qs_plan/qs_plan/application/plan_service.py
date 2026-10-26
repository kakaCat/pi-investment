"""PlanService：计划 CRUD / 两步提交 / 修改纪律门 / 状态迁移（t4）

三步纪律（与 design/interfaces.md 错误码一致）：
1. **两步提交**：PATCH 只改 draft_spec 并返回编译预览；apply 才 version++ 生效。
2. **修改纪律**：
   - agent 自主修改必须带 decision_audit_id（缺 → DECISION_AUDIT_REQUIRED）；
   - 观察窗未满时改同一字段，需更强证据（hypothesis.evidence ≥2 条或 change_reason 非空），
     否则 PLAN_CHANGE_LOCKED；
   - 反向修改（改回更早版本的值）必须写明 change_reason，否则 PLAN_CHANGE_LOCKED。
3. **状态机**：全部走 evaluate_plan_transition；有持仓关闭必须给 close_disposition。

本服务不做 I/O 编排细节：仓储与时钟/持仓事实都注入，便于假件单测。
"""

from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from qs_plan.domain.plan import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_HOLDING,
    STATUS_PAUSED,
    evaluate_plan_transition,
    next_close_status,
    validate_plan_spec,
)

logger = structlog.get_logger(__name__)

#: 错误码（路由层原样映射到 HTTP 状态）
PLAN_SPEC_INVALID = "PLAN_SPEC_INVALID"
PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
VERSION_CONFLICT = "VERSION_CONFLICT"
PLAN_STATE_ILLEGAL = "PLAN_STATE_ILLEGAL"
PLAN_CHANGE_LOCKED = "PLAN_CHANGE_LOCKED"
DECISION_AUDIT_REQUIRED = "DECISION_AUDIT_REQUIRED"

_STATUS_HTTP = {
    PLAN_SPEC_INVALID: 400,
    PLAN_NOT_FOUND: 404,
    VERSION_CONFLICT: 409,
    PLAN_STATE_ILLEGAL: 422,
    PLAN_CHANGE_LOCKED: 400,
    DECISION_AUDIT_REQUIRED: 400,
}


class PlanError(Exception):
    """带错误码的计划域异常。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def http_status(self) -> int:
        return _STATUS_HTTP.get(self.code, 400)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _spec_diffs(
    old: Dict[str, Any], new: Dict[str, Any], prefix: str = ""
) -> List[Tuple[str, Any, Any]]:
    """逐路径 diff（只比较标量与列表整体；列表内部按整体替换处理）。"""
    diffs: List[Tuple[str, Any, Any]] = []
    keys = set(old or {}) | set(new or {})
    for k in sorted(keys):
        path = "%s.%s" % (prefix, k) if prefix else str(k)
        ov, nv = (old or {}).get(k), (new or {}).get(k)
        if isinstance(ov, dict) and isinstance(nv, dict):
            diffs.extend(_spec_diffs(ov, nv, path))
        elif ov != nv:
            diffs.append((path, ov, nv))
    return diffs


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:  # noqa: BLE001
        return None


class PlanService:
    def __init__(
        self,
        repo,
        now_fn: Callable[[], datetime] = _utcnow,
        position_provider: Optional[Callable[[str, str], bool]] = None,
        rule_port: Any = None,
    ):
        self.repo = repo
        self._now = now_fn
        self._position_provider = position_provider or (lambda account, symbol: False)
        #: 托管规则端口（批次退役用）；None = 只写事件不退役（假件/降级）
        self._rule_port = rule_port

    # ── 查询 ──────────────────────────────────────────────
    def get(self, plan_id: int):
        plan = self.repo.get_plan(plan_id)
        if plan is None:
            raise PlanError(PLAN_NOT_FOUND, "计划不存在：%s" % plan_id)
        return plan

    def list(self, account: str, statuses: Optional[List[str]] = None):
        return self.repo.list_plans(account, statuses=statuses)

    # ── 创建 ──────────────────────────────────────────────
    def create(
        self,
        account: str,
        name: str,
        horizon: str,
        spec: Dict[str, Any],
        created_by: str,
        actor: Optional[str] = None,
    ):
        problems = validate_plan_spec(spec)
        if problems:
            raise PlanError(PLAN_SPEC_INVALID, "；".join(problems))
        if horizon not in ("day", "swing"):
            raise PlanError(PLAN_SPEC_INVALID, "horizon 必须是 day 或 swing")
        return self.repo.create_plan(
            account=account,
            name=name,
            horizon=horizon,
            spec=spec,
            created_by=created_by,
            actor=actor or created_by,
        )

    # ── 两步提交：PATCH（暂存 + 预览） ──────────────────────
    def patch(
        self,
        plan_id: int,
        expected_version: int,
        patch_spec: Dict[str, Any],
        reason: Optional[str],
        actor: str = "agent",
        decision_audit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        plan = self.get(plan_id)
        self._require_mutable(plan)
        self._require_audit_for_agent(actor, decision_audit_id)
        merged = self._merge_spec(plan.spec, plan.draft_spec, patch_spec)
        problems = validate_plan_spec(merged)
        if problems:
            raise PlanError(PLAN_SPEC_INVALID, "；".join(problems))
        ok = self.repo.update_draft_spec(plan_id, merged, expected_version)
        if not ok:
            raise PlanError(VERSION_CONFLICT, "计划版本已变化，请重读后再改")
        diffs = _spec_diffs(plan.spec, merged)
        return {
            "plan_id": plan_id,
            "draft_version": expected_version,
            "diff": [{"path": p, "from": o, "to": n} for p, o, n in diffs],
            "reason": reason,
        }

    # ── 两步提交：apply（纪律门 + 生效） ────────────────────
    def apply(
        self,
        plan_id: int,
        expected_version: int,
        actor: str = "agent",
        decision_audit_id: Optional[str] = None,
        reason: Optional[str] = None,
        hypothesis: Optional[Dict[str, Any]] = None,
        window_days: int = 10,
    ) -> Dict[str, Any]:
        plan = self.get(plan_id)
        self._require_mutable(plan)
        self._require_audit_for_agent(actor, decision_audit_id)
        draft = plan.draft_spec
        if draft is None:
            raise PlanError(PLAN_SPEC_INVALID, "没有待生效的修改（先 PATCH 暂存）")
        self._enforce_change_discipline(plan, draft, reason, hypothesis)
        new_version = self.repo.apply_version(
            plan_id=plan_id,
            expected_version=expected_version,
            spec=draft,
            baseline=self._baseline_of(plan),
            window_days=window_days,
            change_reason=reason,
            hypothesis=hypothesis,
            created_by=actor,
            decision_audit_id=decision_audit_id,
        )
        if new_version is None:
            raise PlanError(VERSION_CONFLICT, "计划版本已变化，请重读后再改")
        return {"plan_id": plan_id, "version": new_version, "applied": True}

    # ── 生命周期 ──────────────────────────────────────────
    def activate(
        self, plan_id: int, expected_version: Optional[int] = None, actor: str = "agent"
    ) -> None:
        self._transition(
            plan_id,
            STATUS_ACTIVE,
            actor,
            "激活计划",
            expected_version=expected_version,
            extra_fields={"activated_at": self._now()},
        )

    def pause(self, plan_id: int, reason: str, actor: str = "agent") -> None:
        self._transition(plan_id, STATUS_PAUSED, actor, reason or "暂停计划")

    def resume(
        self, plan_id: int, expected_version: Optional[int] = None, actor: str = "agent"
    ) -> None:
        self._transition(
            plan_id, STATUS_ACTIVE, actor, "恢复计划", expected_version=expected_version
        )

    def close(
        self,
        plan_id: int,
        reason: str,
        actor: str = "agent",
        close_disposition: Optional[str] = None,
        target: str = STATUS_HOLDING,
    ) -> None:
        plan = self.get(plan_id)
        has_pos = self._position_provider(
            plan.account, (plan.spec.get("targets") or [{}])[0].get("symbol", "")
        )
        to_status = next_close_status(has_pos)
        ok, why = evaluate_plan_transition(
            plan.status,
            to_status,
            has_position=has_pos,
            has_close_disposition=bool(close_disposition),
        )
        if not ok:
            raise PlanError(PLAN_STATE_ILLEGAL, why or "非法状态迁移")
        fields = {
            "closed_at": self._now() if to_status != STATUS_HOLDING else None,
            "close_reason": reason,
        }
        ok = self.repo.transition_status(
            plan_id,
            to_status,
            actor=actor,
            reason=reason,
            extra_fields={k: v for k, v in fields.items() if v is not None},
        )
        if not ok:
            raise PlanError(PLAN_STATE_ILLEGAL, "状态迁移失败")

    def archive(
        self, plan_id: int, expected_version: Optional[int] = None, actor: str = "agent"
    ) -> None:
        plan = self.get(plan_id)
        overdue = int(getattr(plan, "reflection_overdue_count", 0) or 0)
        ok, why = evaluate_plan_transition(plan.status, STATUS_ARCHIVED, review_overdue=overdue)
        if not ok:
            raise PlanError(PLAN_STATE_ILLEGAL, why or "非法状态迁移")
        ok = self.repo.transition_status(
            plan_id,
            STATUS_ARCHIVED,
            actor=actor,
            reason="归档计划",
            expected_version=expected_version,
        )
        if not ok:
            raise PlanError(
                VERSION_CONFLICT if expected_version is not None else PLAN_STATE_ILLEGAL,
                "状态迁移失败（版本冲突或计划不存在）",
            )

    # ── 成交推进（t8 经端口调用） ──────────────────────────
    def on_fill(
        self,
        plan_id: int,
        *,
        side: str,
        qty: int,
        remaining_qty: int,
        trade_id: Optional[str] = None,
        sold_ratio: float = 0.0,
    ) -> Optional[str]:
        """成交回写推进：买入→holding；卖出清仓→closing→closed；部分→保持。

        sold_ratio>0 时按累计卖出比例匹配并退役对应减仓批次（FR-2），
        每批写一条 kind=fill 事件留痕；无匹配记 degraded_fill（不臆造退役）。
        """
        plan = self.get(plan_id)
        now = self._now()
        if side == "buy" and plan.status == STATUS_ACTIVE:
            self.repo.transition_status(
                plan_id,
                STATUS_HOLDING,
                actor="system",
                reason="成交开仓",
                extra_fields={"activated_at": plan.activated_at or now},
            )
            return STATUS_HOLDING
        if side == "sell":
            if sold_ratio and float(sold_ratio) > 0:
                self._converge_batches(
                    plan,
                    sold_ratio=float(sold_ratio),
                    qty=qty,
                    remaining_qty=remaining_qty,
                    trade_id=trade_id,
                )
            if remaining_qty <= 0:
                if plan.status == STATUS_HOLDING:
                    self.repo.transition_status(
                        plan_id, "closing", actor="system", reason="清仓成交（退出中）"
                    )
                self.repo.transition_status(
                    plan_id,
                    "closed",
                    actor="system",
                    reason="持仓清零，计划关闭",
                    extra_fields={"closed_at": now},
                )
                return "closed"
            if plan.status == STATUS_HOLDING:
                self.repo.transition_status(
                    plan_id, "closing", actor="system", reason="部分减仓成交"
                )
                self.repo.transition_status(
                    plan_id, STATUS_HOLDING, actor="system", reason="部分成交收敛回持仓"
                )
                return STATUS_HOLDING
        return plan.status

    # ── 内部 ──────────────────────────────────────────────
    def _converge_batches(
        self, plan, *, sold_ratio: float, qty: int, remaining_qty: int, trade_id: Optional[str]
    ) -> None:
        """按累计卖出比例退役减仓批次并留痕（FR-2）。幂等：同 trade_id 不重复写。"""
        from qs_plan.domain.plan.batch_matcher import match_reduce_batches

        plan_id = plan.id
        exit_spec = (plan.spec or {}).get("exit") or {}
        batches = exit_spec.get("reduce_plan") or []
        if not batches:
            return
        if trade_id is not None and self._already_logged(plan_id, trade_id):
            return
        try:
            indexes = match_reduce_batches(batches, sold_ratio)
        except ValueError as exc:
            self.repo.record_event(
                plan_id,
                "degraded_fill",
                "system",
                reason="批次匹配失败：%s" % exc,
                detail={
                    "trade_id": trade_id,
                    "qty": qty,
                    "sold_ratio": sold_ratio,
                    "remaining_qty": remaining_qty,
                },
            )
            return

        managed = {}
        enabled_by_rule = {}
        if self._rule_port is not None:
            try:
                for row in self._rule_port.list_managed(plan_id):
                    rule_id = row.get("rule_id")
                    managed.setdefault((row.get("role"), row.get("batch")), rule_id)
                    enabled_by_rule[rule_id] = bool(row.get("enabled", True))
            except Exception as exc:  # noqa: BLE001 - 读不到就只记事件
                logger.warning(
                    "读托管规则失败（批次只留痕不退役）", plan_id=plan_id, error=str(exc)
                )

        retired = []
        for idx in indexes:
            rule_id = managed.get(("reduce", idx))
            already_retired = rule_id is not None and not enabled_by_rule.get(rule_id, True)
            if rule_id is not None and not already_retired and self._rule_port is not None:
                try:
                    self._rule_port.retire_rule(
                        rule_id,
                        "计划批次已成交（第 %d 批，累计卖出 %.0f%%）" % (idx + 1, sold_ratio * 100),
                    )
                    retired.append(rule_id)
                except Exception as exc:  # noqa: BLE001 - 退役失败不吞事件
                    logger.warning(
                        "批次规则退役失败", plan_id=plan_id, rule_id=rule_id, error=str(exc)
                    )
            self.repo.record_event(
                plan_id,
                "fill",
                "system",
                reason="减仓批次进度（第 %d 批）" % (idx + 1),
                detail={
                    "batch": idx,
                    "trade_id": trade_id,
                    "qty": qty,
                    "remaining_qty": remaining_qty,
                    "sold_ratio": sold_ratio,
                    "rule_id": rule_id,
                    "retired": rule_id in retired,
                    "already_retired": already_retired,
                    "degraded": rule_id is None,
                },
            )

    def _already_logged(self, plan_id: int, trade_id: Optional[str]) -> bool:
        try:
            for ev in self.repo.list_events(plan_id, limit=50):
                detail = getattr(ev, "detail", None) or {}
                if (
                    str(detail.get("trade_id")) == str(trade_id)
                    and getattr(ev, "kind", "") == "fill"
                ):
                    return True
        except Exception:  # noqa: BLE001 - 读历史失败按未记录处理（宁可重复一次留痕）
            return False
        return False

    def _transition(
        self,
        plan_id: int,
        to_status: str,
        actor: str,
        reason: str,
        expected_version: Optional[int] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        plan = self.get(plan_id)
        ok, why = evaluate_plan_transition(plan.status, to_status)
        if not ok:
            raise PlanError(PLAN_STATE_ILLEGAL, why or "非法状态迁移")
        ok = self.repo.transition_status(
            plan_id,
            to_status,
            actor=actor,
            reason=reason,
            expected_version=expected_version,
            extra_fields=extra_fields,
        )
        if not ok:
            raise PlanError(
                VERSION_CONFLICT if expected_version is not None else PLAN_STATE_ILLEGAL,
                "状态迁移失败（版本冲突或计划不存在）",
            )

    @staticmethod
    def _require_mutable(plan) -> None:
        """closed/archived 计划不可再改（防止「关了还在改」的幽灵计划）。"""
        if plan.status in ("closed", "archived"):
            raise PlanError(
                PLAN_STATE_ILLEGAL,
                "已关闭/归档的计划不可修改（状态：%s），请新建计划" % plan.status,
            )

    @staticmethod
    def _require_audit_for_agent(actor: str, decision_audit_id: Optional[str]) -> None:
        if actor == "agent" and not decision_audit_id:
            raise PlanError(DECISION_AUDIT_REQUIRED, "agent 自主修改必须带 decision_audit_id")

    def _merge_spec(
        self, base: Dict[str, Any], draft: Optional[Dict[str, Any]], patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        current = draft if draft is not None else base
        merged = dict(current)
        for k, v in (patch or {}).items():
            merged[k] = v
        return merged

    def _baseline_of(self, plan) -> Dict[str, Any]:
        stats = plan.stats or {}
        return {
            "version": plan.version,
            "frozen_at": self._now().isoformat(),
            "hit_rate": stats.get("hit_rate"),
            "pnl": stats.get("pnl"),
            "trigger_count": stats.get("trigger_count"),
        }

    def _enforce_change_discipline(
        self,
        plan,
        draft: Dict[str, Any],
        reason: Optional[str],
        hypothesis: Optional[Dict[str, Any]],
    ) -> None:
        """观察窗锁定 + 反向修改 + agent 证据门槛。"""
        diffs = _spec_diffs(plan.spec, draft)
        if not diffs:
            raise PlanError(PLAN_SPEC_INVALID, "修改没有任何差异")
        versions = self.repo.list_versions(plan.id, limit=10) or []
        latest = versions[0] if versions else None
        today = self._now().date()
        window_active = bool(
            latest and latest.window_ends_at and _as_date(latest.window_ends_at) >= today
        )
        latest_paths = set()
        prev_spec = None
        if latest is not None and len(versions) > 1:
            latest_paths = {p for p, _o, _n in _spec_diffs(versions[1].spec, latest.spec)}
            prev_spec = versions[1].spec
        evidence = (hypothesis or {}).get("evidence") or []
        changed_paths = {p for p, _o, _n in diffs}
        if window_active and latest_paths & changed_paths:
            if not reason and len(evidence) < 2:
                raise PlanError(
                    PLAN_CHANGE_LOCKED,
                    "观察窗未满且改动同一字段：需要 change_reason 或 ≥2 条证据（无对照组）",
                )
        if prev_spec is not None:
            reversal_paths = []
            for path, _old, new in diffs:
                if path in latest_paths:
                    previous_value = self._value_at(prev_spec, path)
                    if previous_value == new and not reason:
                        reversal_paths.append(path)
            if reversal_paths:
                raise PlanError(
                    PLAN_CHANGE_LOCKED,
                    "反向修改（%s）必须写明上次判断为什么错了" % "，".join(reversal_paths),
                )

    @staticmethod
    def _value_at(spec: Dict[str, Any], path: str) -> Any:
        cur: Any = spec
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur
