"""反思定时任务（t11 · FR-5 · D-5：定时器驱动反思）

职责（v2 侧备料，agent 判断）：
  1. 交易日守卫（仅日任务；周任务周六运行，不套交易日守卫）；
  2. 扫到期计划（review_due_at 为空或已过）：
     - 上一轮到期后 agent 未交反思 → overdue+1（真实闭环，不再只统计组包/唤醒失败）；
     - 组装材料包 → 唤醒 agent；
  3. 唤醒失败/agent 未交反思 → 记 overdue（连续缺席由摘要侧告警）；
  4. 成功推进下次到期时间（now + review_interval_days）；失败不推进，下次继续追。

周任务：同一账户的到期计划聚合成一个跨计划材料包，每个账户唤醒一次。

唤醒通道可注入（组合根注入既有 /wake 直连）；未注入时只落包不唤醒（可观测）。
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_trading_day(now: datetime) -> bool:
    """交易日守卫：优先既有 TradingDayGuard，不可用退化为工作日判断。"""
    try:
        from qs_ops.application.services.trading_day_guard import TradingDayGuard

        return bool(TradingDayGuard.is_trading_day(now.date()))
    except Exception:  # noqa: BLE001 - 退化不阻断（工作日口径）
        return now.weekday() < 5


def _week_period(now: datetime) -> str:
    iso = now.date().isocalendar()
    return "%04d-W%02d" % (iso.year, iso.week)


def _missed_reflection_since_due(plan, due_at) -> bool:
    """上一轮 due_at 后是否没有反思。时间精度只用于先后比较，跨库 tz 不一致时归一。"""
    last = getattr(plan, "last_reflected_at", None)
    if last is None:
        return True
    try:
        return bool(last < due_at)
    except TypeError:
        try:
            if (
                getattr(last, "tzinfo", None) is None
                and getattr(due_at, "tzinfo", None) is not None
            ):
                last = last.replace(tzinfo=due_at.tzinfo)
            elif (
                getattr(due_at, "tzinfo", None) is None
                and getattr(last, "tzinfo", None) is not None
            ):
                due_at = due_at.replace(tzinfo=last.tzinfo)
            return bool(last < due_at)
        except Exception:  # noqa: BLE001 - 时间不可比按已交处理，宁可少计一次 overdue
            logger.warning("反思时间不可比，跳过 overdue 判定", plan_id=getattr(plan, "id", None))
            return False


class PlanReflectionJob:
    name = "plan_reflect_daily"
    description = "交易计划反思：组装四输入材料包并唤醒 agent（盘后 15:35）"
    timeout_seconds = 300

    def __init__(
        self,
        plan_repo=None,
        pack_service=None,
        waker: Optional[Callable[[Any, Dict[str, Any]], Any]] = None,
        now_fn: Callable[[], datetime] = _utcnow,
        trading_day_fn: Callable[[datetime], bool] = _is_trading_day,
    ):
        self._repo = plan_repo
        self._pack = pack_service
        self._wake = waker
        self._now = now_fn
        self._is_trading_day = trading_day_fn

    # ── Job 协议入口 ──────────────────────────────────────
    async def execute(self, params: Optional[Dict[str, Any]] = None):
        from qs_ops.application.jobs.job_protocol import result_from_dict

        try:
            summary = await asyncio.to_thread(self.run, params or {})
            return result_from_dict(summary)
        except Exception as exc:  # noqa: BLE001 - 失败必须显式
            logger.error("计划反思任务失败", error=str(exc))
            return result_from_dict({"status": "failed", "error": str(exc)})

    # ── 主流程 ────────────────────────────────────────────
    def run(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = self._now()
        if not self._is_trading_day(now):
            return {
                "status": "skipped",
                "reason": "非交易日",
                "packed": 0,
                "woken": 0,
                "overdue": 0,
            }
        return self._run_due(now, params or {}, aggregate=False)

    def _run_due(self, now: datetime, params: Dict[str, Any], *, aggregate: bool) -> Dict[str, Any]:
        repo = self._repo or self._default_repo()
        pack_svc = self._pack or self._default_pack(repo)
        plans = repo.list_due_plans(now)
        overdue = self._mark_missed_reflections(repo, plans)

        if aggregate:
            packed, woken, pack_failed_plans, wake_failed_plans, groups = self._pack_and_group(
                repo, pack_svc, plans, params
            )
            overdue += len(pack_failed_plans)
            if self._wake is not None and groups:
                for account in sorted(groups):
                    group = groups[account]
                    weekly_pack = {
                        "kind": "weekly",
                        "period": _week_period(now),
                        "built_at": now.isoformat(),
                        "plan_count": len(group["packs"]),
                        "plans": group["packs"],
                    }
                    try:
                        self._wake(SimpleNamespace(id=None, account=account), weekly_pack)
                        woken += 1
                        self._advance_due(repo, now, group["plans"])
                    except Exception as e:  # noqa: BLE001 - 单账户失败不拖垮其他账户
                        logger.error("周度反思唤醒失败", account=account, error=str(e))
                        overdue += len(group["plans"])
                        wake_failed_plans.extend(group["plans"])
            if self._wake is None:
                # 唤醒通道关闭 = 有意只落包：组包成功后照常推进，避免下次重复扫同一批
                for group in groups.values():
                    self._advance_due(repo, now, group["plans"])
            else:
                for plan in plans:
                    if plan in pack_failed_plans or plan in wake_failed_plans:
                        continue
                    if any(plan in group["plans"] for group in groups.values()):
                        continue
                    self._advance_due(repo, now, [plan])
        else:
            packed = woken = 0
            for plan in plans:
                try:
                    pack = pack_svc.build(plan.id)
                    packed += 1
                except Exception as e:  # noqa: BLE001 - 单计划失败不拖垮整批
                    logger.error("材料包组装失败", plan_id=getattr(plan, "id", None), error=str(e))
                    repo.bump_overdue(plan.id)
                    overdue += 1
                    continue
                wake_ok = True
                if self._wake is not None:
                    try:
                        self._wake(plan, pack)
                        woken += 1
                    except Exception as e:  # noqa: BLE001
                        logger.error(
                            "反思唤醒失败", plan_id=getattr(plan, "id", None), error=str(e)
                        )
                        repo.bump_overdue(plan.id)
                        overdue += 1
                        wake_ok = False
                # 唤醒失败不推进 due：下一次扫描继续追这份反思；未注入唤醒是有意只落包，照常推进
                if self._wake is None or wake_ok:
                    self._advance_due(repo, now, [plan])

        return {
            "status": "ok",
            "packed": packed,
            "woken": woken,
            "overdue": overdue,
            "due_plans": len(plans),
        }

    def _pack_and_group(self, repo, pack_svc, plans, params):
        packed = 0
        pack_failed_plans: List[Any] = []
        wake_failed_plans: List[Any] = []
        groups: Dict[str, Dict[str, Any]] = {}
        for plan in plans:
            try:
                pack = pack_svc.build(plan.id)
                packed += 1
            except Exception as e:  # noqa: BLE001 - 单计划失败不拖垮整批
                logger.error("周度材料包组装失败", plan_id=getattr(plan, "id", None), error=str(e))
                repo.bump_overdue(plan.id)
                pack_failed_plans.append(plan)
                continue
            account = str(getattr(plan, "account", None) or params.get("account") or "")
            group = groups.setdefault(account, {"plans": [], "packs": []})
            group["plans"].append(plan)
            group["packs"].append(
                {
                    "plan_id": getattr(plan, "id", None),
                    "account": account,
                    "plan_name": getattr(plan, "name", None),
                    "pack": pack,
                }
            )
        return packed, 0, pack_failed_plans, wake_failed_plans, groups

    @staticmethod
    def _mark_missed_reflections(repo, plans) -> int:
        """上轮 due_at 后没有反思行 → overdue+1；首轮（due_at 为空）不追溯历史。"""
        overdue = 0
        for plan in plans:
            due_at = getattr(plan, "review_due_at", None)
            if due_at is None:
                continue
            if _missed_reflection_since_due(plan, due_at):
                repo.bump_overdue(plan.id)
                overdue += 1
        return overdue

    @staticmethod
    def _advance_due(repo, now: datetime, plans) -> None:
        for plan in plans:
            interval = int(getattr(plan, "review_interval_days", 1) or 1)
            repo.set_review_due(plan.id, now + timedelta(days=interval))

    # ── 默认装配 ──────────────────────────────────────────
    @staticmethod
    def _default_repo():
        from adapters.outbound.repositories.trading_plan_repository import (
            TradingPlanRepository,
        )

        return TradingPlanRepository()

    @staticmethod
    def _default_pack(repo):
        from adapters.outbound.repositories.plan_stats_repository import blocked_stats
        from qs_plan.application.reflection_pack_service import (
            ReflectionPackService,
            trades_provider_from_engine,
        )

        class _Stats:
            def blocked_stats(self, since_days=30, horizon=5):
                return blocked_stats(since_days=since_days, horizon=horizon)

        return ReflectionPackService(
            repo, stats_repo=_Stats(), trades_provider=trades_provider_from_engine()
        )


class PlanReflectionWeeklyJob(PlanReflectionJob):
    """周度深反思：不按交易日守卫（周六 10:00 运行），按账户聚合跨计划材料包。"""

    name = "plan_reflect_weekly"
    description = "交易计划周度深反思：跨计划材料包（周六 10:00）"

    def run(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = self._now()
        return self._run_due(now, params or {}, aggregate=True)


def build_agent_waker(
    notify_fn: Optional[Callable[..., Any]] = None, enabled: Optional[bool] = None
):
    """既有唤醒通道的薄包装（FR-1）：AgentNotificationService.notify_agent → POST /wake。

    返回 None 表示不唤醒（开关关闭 / 通道不可用）——任务仍组包落库，可观测。
    周度聚合包 plan_id=None：period/instruction 按包内 kind 区分。
    """
    if enabled is None:
        import os

        enabled = os.getenv("PLAN_REFLECTION_WAKE_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("反思唤醒已关闭（PLAN_REFLECTION_WAKE_ENABLED=false），只组包")
        return None
    if notify_fn is None:
        try:
            from qs_agenthub.application.services.agent_notification_service import (
                AgentNotificationService,
            )

            notify_fn = AgentNotificationService().notify_agent
        except Exception as e:  # noqa: BLE001 - 通道不可用不阻断注册
            logger.warning("反思唤醒通道装配失败（只组包）", error=str(e))
            return None

    def _waker(plan, pack) -> bool:
        plan_id = getattr(plan, "id", None)
        account = getattr(plan, "account", None)
        period = _utcnow().date().isoformat()
        kind = "daily"
        summary: Dict[str, Any] = {}
        if isinstance(pack, dict):
            kind = str(pack.get("kind") or kind)
            period = str(pack.get("period") or period)
            entries = pack.get("plans")
            if isinstance(entries, list):
                summary["plan_count"] = len(entries)
                summary["inputs_ready"] = sum(
                    1
                    for item in entries
                    if isinstance(item, dict)
                    and isinstance(item.get("pack"), dict)
                    and item["pack"].get("inputs_ready")
                )
            else:
                for key in ("modifications", "missed", "wins", "losses"):
                    seg = pack.get(key)
                    summary[key] = len(seg) if isinstance(seg, (list, dict)) else seg
        data = {
            "plan_id": plan_id,
            "account": account,
            "kind": kind,
            "period": period,
            "pack_summary": summary,
            "answers_required": ["q1", "q2", "q3", "q4", "q5"],
            "instruction": (
                "请用 trading_plan 工具读取本账户全部到期计划与材料包，按五问作答并提交周度反思。"
                if kind == "weekly"
                else "请用 trading_plan 工具读计划与材料包，按五问作答并提交反思（reflect）。"
            ),
        }
        target = "agent-dh" if account in (None, "", "agent_brain") else "agent-ts"
        return bool(notify_fn("plan_reflection", data, target))

    return _waker


def build_plan_jobs(waker: Optional[Callable[[Any, Dict[str, Any]], Any]] = None):
    """组合根注册入口（main.py）：两个反思任务实例。

    waker 未显式注入时按 PLAN_REFLECTION_WAKE_ENABLED 走既有唤醒通道（FR-1）。
    """
    if waker is None:
        waker = build_agent_waker()
    return [PlanReflectionJob(waker=waker), PlanReflectionWeeklyJob(waker=waker)]
