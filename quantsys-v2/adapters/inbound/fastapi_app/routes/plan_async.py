"""交易计划 API（IF-1~IF-9、IF-11 · REQ-261021222905-6dff t6）

薄壳：参数校验 + 调 PlanService/PlanCompiler + PLAN_* 错误码映射。
执行不在这里发生：激活只是把计划编译成 watch_rules，盯盘与触发归 WatchEngine（D-8）。

路由：
  POST   /api/plans                        IF-1 创建
  GET    /api/plans                        IF-2 列表
  GET    /api/plans/{plan_id}              IF-3 详情
  PATCH  /api/plans/{plan_id}              IF-4 修改暂存 + 编译预览
  POST   /api/plans/{plan_id}/apply        IF-5 修改生效 + 重编译
  POST   /api/plans/{plan_id}/activate     IF-6 激活 + 首编译
  POST   /api/plans/{plan_id}/pause        IF-7 暂停（规则停用）
  POST   /api/plans/{plan_id}/resume       IF-8 恢复
  POST   /api/plans/{plan_id}/close        IF-9 关闭（规则退役）
  GET    /api/plans/{plan_id}/compile-preview  IF-11 编译预览（不落库）
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from qs_plan.application.core_plan_adapter import CorePlanAdapter, CorePlanUnavailable
from qs_plan.application.plan_aggregator import PlanAggregator
from qs_plan.application.reflection_pack_service import (
    ReflectionPackService,
    trades_provider_from_engine,
)
from qs_plan.application.plan_compiler import PlanCompiler
from qs_plan.application.plan_service import PlanError, PlanService

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Trading Plan - 交易计划"])


# ── DI ──────────────────────────────────────────────────────
def _build(repo=None, compiler_port=None) -> Dict[str, Any]:
    from adapters.outbound.repositories.trading_plan_repository import TradingPlanRepository
    from adapters.outbound.repositories.plan_rule_port import PlanRulePort

    plan_repo = repo or TradingPlanRepository()
    port = compiler_port or PlanRulePort(plan_repo=plan_repo)
    try:
        from adapters.outbound.repositories.plan_rule_port import PlanRulePort

        _rule_port = PlanRulePort()
    except Exception:  # noqa: BLE001 - 端口装配失败不影响计划读取
        _rule_port = None
    svc = PlanService(plan_repo, position_provider=_position_provider, rule_port=_rule_port)
    return {"repo": plan_repo, "svc": svc, "compiler": PlanCompiler(port), "port": port}


def _position_provider(account: str, symbol: str) -> bool:
    """持仓真值：simulation_positions 有正持仓即 True（读失败按无持仓处理，不臆造）。"""
    if not symbol:
        return False
    try:
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        bare = symbol.split(".")[0]
        with get_engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM quant.simulation_positions p "
                    "WHERE coalesce(p.shares_total,0) > 0 "
                    "AND split_part(p.symbol,'.',1) = :sym "
                    "AND (NULLIF(btrim(p.account_name),'') IS NULL OR btrim(p.account_name)=btrim(:acct)) "
                    "LIMIT 1"
                ),
                {"sym": bare, "acct": account or ""},
            ).scalar()
        return bool(row)
    except Exception as e:  # noqa: BLE001
        logger.warning("持仓真值读取失败（按无持仓）", symbol=symbol, error=str(e))
        return False


def _state_provider(account: str):
    return lambda symbol: "holding" if _position_provider(account, symbol) else "none"


def _env_gate_provider() -> Dict[str, Any]:
    """市场环境闸事实（只读）：取 MarketState 快照后做纯判定，异常由聚合器降级。"""
    from qs_market_data.adapters.outbound.datasources.market_state_provider import (
        MarketStateProvider,
    )
    from qs_watch.application.services.watch_engine.market.environment_gate_service import (
        EnvironmentGateService,
    )

    state = MarketStateProvider().get_state()
    decision = EnvironmentGateService().evaluate(state)
    out = decision.as_dict()
    out["status"] = decision.verdict
    return out


def _pending_todo_count(account: str) -> int:
    from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository

    return WatchTodoRepository().count_pending(account=account)


def _err(e: PlanError) -> JSONResponse:
    return JSONResponse(
        status_code=e.http_status, content={"success": False, "code": e.code, "error": e.message}
    )


def _ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": True, "data": data})


def _resolve_names(symbols) -> Dict[str, str]:
    """标的名解析（一次批量查 quant.stocks；失败降级空表，不编造名字）。"""
    bare = sorted({str(s).split(".")[0] for s in symbols if s})
    if not bare:
        return {}
    try:
        from qs_kernel.infrastructure.persistence.database.engine import get_engine
        from sqlalchemy import text as _text

        with get_engine().connect() as conn:
            rows = (
                conn.execute(
                    _text(
                        "SELECT symbol, name FROM quant.stocks WHERE symbol = ANY(:syms)"
                        " UNION SELECT symbol, name FROM quant.stocks"
                        " WHERE symbol = ANY(:syms_full)"
                    ),
                    {
                        "syms": bare,
                        "syms_full": [b + ".SH" for b in bare] + [b + ".SZ" for b in bare],
                    },
                )
                .mappings()
                .all()
            )
        return {str(r["symbol"]).split(".")[0]: r["name"] for r in rows if r.get("name")}
    except Exception as e:  # noqa: BLE001 - 名称是增益，不阻断计划读取
        logger.warning("标的名解析失败（返回 symbol 原文）", error=str(e))
        return {}


def _with_named_targets(spec, names):
    if not isinstance(spec, dict) or names is None:
        return spec
    out = dict(spec)
    if isinstance(spec.get("targets"), list):
        out["targets"] = _apply_names([dict(t) for t in spec["targets"]], names)
    return out


def _apply_names(targets, names: Dict[str, str]):
    for t in targets or []:
        sym = str(t.get("symbol") or "")
        t["name"] = names.get(sym.split(".")[0]) if sym else None
    return targets


def _plan_dict(plan, names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    return {
        "id": plan.id,
        "account": plan.account,
        "name": plan.name,
        "horizon": plan.horizon,
        "status": plan.status,
        "version": plan.version,
        "spec": _with_named_targets(plan.spec, names),
        "draft_spec": _with_named_targets(plan.draft_spec, names),
        "stats": plan.stats,
        "review_interval_days": plan.review_interval_days,
        "review_due_at": plan.review_due_at.isoformat() if plan.review_due_at else None,
        "last_reflected_at": (
            plan.last_reflected_at.isoformat() if plan.last_reflected_at else None
        ),
        "reflection_overdue_count": plan.reflection_overdue_count,
        "activated_at": plan.activated_at.isoformat() if plan.activated_at else None,
        "closed_at": plan.closed_at.isoformat() if plan.closed_at else None,
        "close_reason": plan.close_reason,
        "created_by": plan.created_by,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _reflection_pack_service(repo) -> ReflectionPackService:
    from adapters.outbound.repositories.plan_stats_repository import blocked_stats

    class _Stats:
        def blocked_stats(self, since_days=30, horizon=5):
            return blocked_stats(since_days=since_days, horizon=horizon)

    return ReflectionPackService(
        repo, stats_repo=_Stats(), trades_provider=trades_provider_from_engine()
    )


def _sync_reflection_knowledge(repo, report_id: int) -> Dict[str, Any]:
    """反思知识同步：失败不反滚反思，只如实返回 failed 并尽量写计划事件。"""
    result: Dict[str, Any] = {"upserted": 0, "skipped": 0, "failed": 0}
    row = repo.get_reflection(report_id)
    if row is None or not row.knowledge_updates:
        return result
    try:
        from qs_agenthub.application.services.evolution.plan_reflection_consumer import (
            PlanReflectionConsumer,
        )

        result = PlanReflectionConsumer().consume([row]) or result
    except Exception as e:  # noqa: BLE001 - 知识沉淀是增益链，不打断反思保存
        logger.error("反思知识同步失败", report_id=report_id, error=str(e))
        result = {**result, "failed": max(int(result.get("failed") or 0), 1), "error": str(e)}
    try:
        repo.record_event(
            row.plan_id,
            "reflection_knowledge",
            "system",
            reason=("反思知识同步失败" if result.get("failed") else "反思知识已同步"),
            detail=result,
        )
    except Exception as e:  # noqa: BLE001 - 事件补写失败不改变知识同步事实
        logger.error("反思知识同步事件写入失败", report_id=report_id, error=str(e))
    return result


# ── IF-12 / IF-13 / IF-17-pack 反思 ───────────────────────
FIVE_QUESTIONS = ("q1", "q2", "q3", "q4", "q5")
FIVE_LABELS = {
    "q1": "盈亏对质",
    "q2": "修改评估",
    "q3": "错过对质",
    "q4": "逻辑存活",
    "q5": "修改决议",
}
VERDICTS = ("keep", "adjust", "close", "observe")


@router.post("/api/plans/{plan_id}/reflections")
async def record_reflection(plan_id: int, body: Dict[str, Any] = Body(...)):
    answers = body.get("answers") or {}
    missing = [
        ("%s(%s)" % (q, FIVE_LABELS[q]))
        for q in FIVE_QUESTIONS
        if not str(answers.get(q) or "").strip()
    ]
    if missing:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "REFLECTION_INCOMPLETE",
                "error": "反思五问缺项：%s" % "、".join(missing),
            },
        )
    verdict = str(body.get("verdict") or "").strip().lower()
    if verdict not in VERDICTS:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "REFLECTION_INCOMPLETE",
                "error": "verdict 必须是 %s 之一" % "/".join(VERDICTS),
            },
        )
    reasoning = body.get("reasoning")
    actions = body.get("actions") or []
    if verdict in ("keep", "observe") and not str(reasoning or "").strip():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "REFLECTION_INCOMPLETE",
                "error": "verdict=%s 必须写明维持理由" % verdict,
            },
        )
    if verdict in ("adjust", "close") and not actions:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "REFLECTION_INCOMPLETE",
                "error": "verdict=%s 必须附修改提案（actions）" % verdict,
            },
        )
    d = _build()
    try:
        d["svc"].get(plan_id)
        evidence_pack = body.get("evidence_pack") or {}
        if not evidence_pack:
            try:
                evidence_pack = _reflection_pack_service(d["repo"]).build(plan_id)
            except Exception as e:  # noqa: BLE001 - 空证据包不得静默落库
                logger.error("反思材料包自动组装失败", plan_id=plan_id, error=str(e))
                return JSONResponse(
                    status_code=422,
                    content={
                        "success": False,
                        "code": "REFLECTION_PACK_UNAVAILABLE",
                        "error": "反思材料包组装失败：%s" % e,
                    },
                )
        rid = d["repo"].record_reflection(
            plan_id=plan_id,
            kind=body.get("kind") or "daily",
            period=body.get("period") or datetime.now(timezone.utc).date().isoformat(),
            evidence_pack=evidence_pack,
            answers=answers,
            verdict=verdict,
            reasoning=reasoning,
            actions=actions or None,
            knowledge_updates=body.get("knowledge_updates"),
            agent_session_id=body.get("agent_session_id"),
        )
        d["repo"].mark_reflected(plan_id, datetime.now(timezone.utc))
        knowledge_sync = (
            _sync_reflection_knowledge(d["repo"], rid) if body.get("knowledge_updates") else None
        )
        return _ok(
            {"report_id": rid, "plan_id": plan_id, "knowledge_sync": knowledge_sync},
            status_code=201,
        )
    except PlanError as e:
        return _err(e)


@router.get("/api/plans/{plan_id}/reflection-pack")
async def get_reflection_pack(plan_id: int):
    d = _build()
    try:
        d["svc"].get(plan_id)
        pack = _reflection_pack_service(d["repo"]).build(plan_id)
        return _ok(pack)
    except PlanError as e:
        return _err(e)
    except Exception as e:  # noqa: BLE001 - 材料包缺数据段由服务标注，装配失败显式 422
        logger.error("反思材料包读取失败", plan_id=plan_id, error=str(e))
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "code": "REFLECTION_PACK_UNAVAILABLE",
                "error": "反思材料包组装失败：%s" % e,
            },
        )


@router.get("/api/plans/{plan_id}/reflections")
async def list_reflections(plan_id: int):
    d = _build()
    try:
        d["svc"].get(plan_id)
        rows = d["repo"].list_reflections(plan_id, limit=20)
        return _ok(
            {
                "reflections": [
                    {
                        "id": r.id,
                        "kind": r.kind,
                        "period": r.period,
                        "version": r.version,
                        "verdict": r.verdict,
                        "reasoning": r.reasoning,
                        "answers": r.answers,
                        "actions": r.actions,
                        "evidence_pack": r.evidence_pack,
                        "knowledge_updates": r.knowledge_updates,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
                "count": len(rows),
            }
        )
    except PlanError as e:
        return _err(e)


# ── IF-15 core_plan 适配（P2） ─────────────────────────────
@router.post("/api/plans/from-core-plan")
async def from_core_plan(body: Dict[str, Any] = Body(...)):
    account = body.get("account")
    batch = body.get("batch")
    if not account or batch is None:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "PLAN_SPEC_INVALID",
                "error": "account 与 batch 必填",
            },
        )
    d = _build()
    adapter = CorePlanAdapter(d["svc"])
    try:
        return _ok(adapter.from_batch(account, int(batch), actor=body.get("actor") or "agent"))
    except CorePlanUnavailable as e:
        return JSONResponse(
            status_code=422,
            content={"success": False, "code": "CORE_PLAN_UNAVAILABLE", "error": str(e)},
        )


# ── IF-14 / IF-16 统计 ────────────────────────────────────
@router.get("/api/plans/{plan_id}/stats")
async def plan_stats_route(plan_id: int):
    from adapters.outbound.repositories.plan_stats_repository import plan_stats

    d = _build()
    try:
        plan = d["svc"].get(plan_id)
    except PlanError as e:
        return _err(e)
    return _ok(plan_stats(plan_id, account=plan.account))


@router.get("/api/watch/outcomes/blocked-stats")
async def blocked_stats_route(request: Request):
    from adapters.outbound.repositories.plan_stats_repository import blocked_stats

    since_days = int(request.query_params.get("since_days") or 30)
    horizon = int(request.query_params.get("horizon") or 5)
    return _ok(blocked_stats(since_days=since_days, horizon=horizon))


# ── IF-10 today 视图 ───────────────────────────────────────
@router.get("/api/plans/today")
async def plans_today(request: Request):
    account = request.query_params.get("account")
    if not account:
        return JSONResponse(
            status_code=400,
            content={"success": False, "code": "PLAN_ACCOUNT_REQUIRED", "error": "account 必填"},
        )
    d = _build()
    agg = PlanAggregator(
        d["repo"],
        env_gate_provider=_env_gate_provider,
        position_provider=lambda acct, sym: "holding" if _position_provider(acct, sym) else "none",
        todo_provider=_pending_todo_count,
    )
    view = agg.build(account)
    names = _resolve_names(
        [t.get("symbol") for item in view.get("plans") or [] for t in (item.get("targets") or [])]
    )
    for item in view.get("plans") or []:
        _apply_names(item.get("targets"), names)
    return _ok(view)


# ── IF-1 / IF-2 / IF-3 ─────────────────────────────────────
@router.post("/api/plans")
async def create_plan(request: Request, body: Dict[str, Any] = Body(...)):
    d = _build()
    try:
        plan = d["svc"].create(
            account=body.get("account", ""),
            name=body.get("name", ""),
            horizon=body.get("horizon", "day"),
            spec=body.get("spec") or {},
            created_by=body.get("created_by") or body.get("actor") or "agent",
            actor=body.get("actor"),
        )
        return _ok({"plan": _plan_dict(plan)}, status_code=201)
    except PlanError as e:
        return _err(e)


@router.get("/api/plans")
async def list_plans(request: Request):
    account = request.query_params.get("account")
    if not account:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "PLAN_ACCOUNT_REQUIRED",
                "error": "account 必填（单计划单账户，不跨账户聚合）",
            },
        )
    status_param = request.query_params.get("status")
    statuses = [s for s in status_param.split(",") if s] if status_param else None
    d = _build()
    plans = d["svc"].list(account, statuses=statuses)
    names = _resolve_names([t.get("symbol") for p in plans for t in (p.spec.get("targets") or [])])
    return _ok({"plans": [_plan_dict(p, names) for p in plans], "count": len(plans)})


@router.get("/api/plans/{plan_id}")
async def get_plan(plan_id: int):
    d = _build()
    try:
        plan = d["svc"].get(plan_id)
        names = _resolve_names([t.get("symbol") for t in (plan.spec.get("targets") or [])])
        return _ok(
            {
                "plan": _plan_dict(plan, names),
                "versions": [
                    {
                        "version": v.version,
                        "created_at": v.created_at.isoformat() if v.created_at else None,
                        "window_ends_at": (
                            v.window_ends_at.isoformat() if v.window_ends_at else None
                        ),
                    }
                    for v in d["repo"].list_versions(plan_id, limit=10)
                ],
                "events": [
                    {
                        "kind": e.kind,
                        "from_status": e.from_status,
                        "to_status": e.to_status,
                        "reason": e.reason,
                        "actor": e.actor,
                        "at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in d["repo"].list_events(plan_id, limit=10)
                ],
            }
        )
    except PlanError as e:
        return _err(e)


# ── IF-4 / IF-5 / IF-11 ────────────────────────────────────
@router.patch("/api/plans/{plan_id}")
async def patch_plan(plan_id: int, body: Dict[str, Any] = Body(...)):
    d = _build()
    try:
        out = d["svc"].patch(
            plan_id=plan_id,
            expected_version=int(body.get("expected_version") or 0),
            patch_spec=body.get("spec_patch") or body.get("patch_spec") or {},
            reason=body.get("reason"),
            actor=body.get("actor") or "agent",
            decision_audit_id=body.get("decision_audit_id"),
        )
        return _ok(out)
    except PlanError as e:
        return _err(e)


@router.post("/api/plans/{plan_id}/apply")
async def apply_plan(plan_id: int, body: Dict[str, Any] = Body(...)):
    d = _build()
    try:
        out = d["svc"].apply(
            plan_id=plan_id,
            expected_version=int(body.get("expected_version") or 0),
            actor=body.get("actor") or "agent",
            decision_audit_id=body.get("decision_audit_id"),
            reason=body.get("reason"),
            hypothesis=body.get("hypothesis"),
            window_days=int(body.get("window_days") or 10),
        )
        plan = d["repo"].get_plan(plan_id)
        # 只有已在运行/持仓/退出中的计划才重编译；草稿改 spec 不产生任何盯盘规则
        compiled = None
        if plan.status in ("active", "holding", "closing"):
            compiled = d["compiler"].apply(
                plan,
                position_state_for=_state_provider(plan.account),
                reason=body.get("reason") or "修改生效",
            )
        return _ok({**out, "compiled": compiled})
    except PlanError as e:
        return _err(e)


@router.get("/api/plans/{plan_id}/compile-preview")
async def compile_preview(plan_id: int):
    d = _build()
    try:
        plan = d["svc"].get(plan_id)
        spec = plan.draft_spec if plan.draft_spec is not None else plan.spec
        diff = d["compiler"].diff(plan, spec=spec, position_state_for=_state_provider(plan.account))
        return _ok(
            {"plan_id": plan_id, "diff": diff, "counts": {k: len(v) for k, v in diff.items()}}
        )
    except PlanError as e:
        return _err(e)


# ── IF-6 / IF-7 / IF-8 / IF-9 ──────────────────────────────
@router.post("/api/plans/{plan_id}/activate")
async def activate_plan(plan_id: int, body: Dict[str, Any] = Body(default={})):
    d = _build()
    try:
        plan = d["svc"].get(plan_id)
        if plan.status != "draft":
            raise PlanError("PLAN_STATE_ILLEGAL", "只有草稿计划可以激活")
        position_state = _state_provider(plan.account)
        compiled = d["compiler"].apply(plan, position_state_for=position_state, reason="激活编译")
        try:
            d["svc"].activate(
                plan_id,
                expected_version=int(body.get("expected_version") or plan.version),
                actor=body.get("actor") or "agent",
            )
        except Exception:
            # 状态迁移失败时按旧 spec 再对齐一次；编译器内部通常已补偿，
            # 这里兜底处理「创建成功但后续写入/审计失败」这类残留。
            try:
                d["compiler"].apply(plan, position_state_for=position_state, reason="激活失败回滚")
            except Exception as rollback_error:  # noqa: BLE001 - 回滚失败不掩盖原始错误
                logger.error(
                    "激活失败后的规则回滚也失败", plan_id=plan_id, error=str(rollback_error)
                )
            raise
        return _ok({"plan_id": plan_id, "status": "active", "compiled": compiled})
    except PlanError as e:
        return _err(e)


@router.post("/api/plans/{plan_id}/pause")
async def pause_plan(plan_id: int, body: Dict[str, Any] = Body(default={})):
    d = _build()
    try:
        d["svc"].pause(
            plan_id, reason=body.get("reason") or "暂停计划", actor=body.get("actor") or "agent"
        )
        for r in d["port"].list_managed(plan_id):
            if r["enabled"]:
                d["port"].retire_rule(r["rule_id"], "计划暂停（规则停用，保留可恢复）")
        return _ok({"plan_id": plan_id, "status": "paused"})
    except PlanError as e:
        return _err(e)


@router.post("/api/plans/{plan_id}/resume")
async def resume_plan(plan_id: int, body: Dict[str, Any] = Body(default={})):
    d = _build()
    try:
        plan = d["svc"].get(plan_id)
        d["svc"].resume(
            plan_id,
            expected_version=int(body.get("expected_version") or plan.version),
            actor=body.get("actor") or "agent",
        )
        compiled = d["compiler"].apply(
            plan, position_state_for=_state_provider(plan.account), reason="恢复编译"
        )
        return _ok({"plan_id": plan_id, "status": "active", "compiled": compiled})
    except PlanError as e:
        return _err(e)


@router.post("/api/plans/{plan_id}/close")
async def close_plan(plan_id: int, body: Dict[str, Any] = Body(default={})):
    d = _build()
    try:
        d["svc"].close(
            plan_id,
            reason=body.get("reason") or "关闭计划",
            actor=body.get("actor") or "agent",
            close_disposition=body.get("close_disposition"),
        )
        for r in d["port"].list_managed(plan_id):
            if r["enabled"]:
                d["port"].retire_rule(r["rule_id"], "计划关闭（规则退役）")
        plan = d["svc"].get(plan_id)
        return _ok({"plan_id": plan_id, "status": plan.status})
    except PlanError as e:
        return _err(e)


@router.post("/api/plans/{plan_id}/archive")
async def archive_plan(plan_id: int, body: Dict[str, Any] = Body(default={})):
    d = _build()
    try:
        d["svc"].archive(
            plan_id,
            expected_version=(
                int(body["expected_version"]) if body.get("expected_version") is not None else None
            ),
            actor=body.get("actor") or "agent",
        )
        return _ok({"plan_id": plan_id, "status": "archived"})
    except PlanError as e:
        return _err(e)
