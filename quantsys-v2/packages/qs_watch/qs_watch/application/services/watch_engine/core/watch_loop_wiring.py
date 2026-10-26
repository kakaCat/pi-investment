"""盯盘闭环装配（REQ-c9f899 t12，2026-09-18）——唯一接线点

引擎装配（factory.py）与进程外定时任务（daily_jobs_bootstrap）必须用同一份装配
函数，否则两处各建一套服务/仓储，开关一开会出现「两条真相」（本次重构反复强调的教训）。

开关语义（默认值一律不改，切换由父 agent / 部署侧做）：
  · WATCH_TODO_ENABLED       默认 false —— 新闭环总闸（建待办/巡检/回执）
  · WATCH_SELF_HEAL_ENABLED  默认 false —— 规则自愈（抑噪 + 修规则待办）
  · WATCH_RUNTIME_PERSIST_ENABLED 默认 false —— 运行态落库（闩锁/冷却跨重启）

本模块只做装配，不做判定、不发通知；失败一律向上抛，由调用方决定降级
（引擎装配失败不得静默变成「没有闭环」）。
"""
import os
from typing import Any, Optional

import structlog

from qs_watch.application.services.watch_engine._repo_resolver import (
    name_resolver,
    receipt_repo,
    rule_change_repo,
    rule_noise_repo,
    runtime_state_store,
    todo_repo,
)

logger = structlog.get_logger(__name__)

TODO_ENABLED_ENV = 'WATCH_TODO_ENABLED'
SELF_HEAL_ENABLED_ENV = 'WATCH_SELF_HEAL_ENABLED'
RUNTIME_PERSIST_ENV = 'WATCH_RUNTIME_PERSIST_ENABLED'


def env_flag(name: str, default: bool = False) -> bool:
    """布尔环境变量（1/true/yes/on 为真）；缺省用 default，不抛错。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def watch_todo_enabled() -> bool:
    """新闭环总闸（WATCH_TODO_ENABLED，默认 false）"""
    return env_flag(TODO_ENABLED_ENV, False)


def watch_self_heal_enabled() -> bool:
    """规则自愈开关（WATCH_SELF_HEAL_ENABLED，默认 false）"""
    return env_flag(SELF_HEAL_ENABLED_ENV, False)


def watch_runtime_persist_enabled() -> bool:
    """运行态持久化开关（WATCH_RUNTIME_PERSIST_ENABLED，默认 false）"""
    return env_flag(RUNTIME_PERSIST_ENV, False)


# ── 装配函数（惰性 import：开关关闭时不加载 ORM/适配器链路）──────

def build_runtime_store() -> Any:
    """IWatchRuntimeStateStore 的 PostgreSQL 实现（运行态落库/恢复）"""
    return runtime_state_store()


def build_todo_repo() -> Any:
    return todo_repo()


def build_todo_service(assigner: Optional[Any] = None,
                       rule_change_linkage: Optional[Any] = None) -> Any:
    """待办服务；缺省接上"建单即派给 owner agent"（2026-10-16 补缺环）。

    assigner 显式给 None 时**仍接真实派单**（生产语义）；要关派单请在测试里传假
    assigner 或直接构造 TodoService。派单实现自己吞异常，不会打挂建单。
    """
    from qs_watch.application.services.watch_engine.todo_service import TodoService
    from qs_watch.application.services.watch_engine.watch_channels import wake_todo_assignment
    if rule_change_linkage is None:
        try:
            from qs_watch.application.services.watch_engine.disposition_engine import (
                RuleChangeLinkage,
            )
            from qs_watch.application.services.watch_engine._repo_resolver import (
                rule_change_repo, watch_rule_repo,
            )
            rule_change_linkage = RuleChangeLinkage(watch_rule_repo(), rule_change_repo())
        except Exception as e:  # noqa: BLE001 - 联动失败降级为「不执行不改规则」
            import structlog
            structlog.get_logger(__name__).warning(
                '规则变更联动装配失败（只收敛待办，不改规则）', error=str(e))
    return TodoService(build_todo_repo(), assigner=assigner or wake_todo_assignment,
                       rule_change_linkage=rule_change_linkage)


def build_receipt_service() -> Any:
    """三段回执服务（sender 接 NotificationFacade，见 watch_channels）

    agent_waker（2026-10-16）：agent 自有待办的超时升级改唤醒 owner agent，
    而不是把"请处置"推给用户；wake 未送达时由 wake_todo_owner 退回盯盘群卡片。
    """
    from qs_watch.application.services.watch_engine.receipt_service import ReceiptService
    from qs_watch.application.services.watch_engine.watch_channels import (
        send_watch_receipt,
        wake_todo_owner,
    )
    return ReceiptService(receipt_repo(), sender=send_watch_receipt,
                          agent_waker=wake_todo_owner)


def build_self_heal_service(todo_service: Optional[Any] = None) -> Any:
    from qs_watch.application.services.watch_engine.noise_self_heal_service import NoiseSelfHealService
    def _suppress_notify(payload):
        # 静音告知卡：走盯盘群回执通道（失败抛错 → 服务内兜住记日志）
        from qs_watch.application.services.watch_engine.watch_channels import send_watch_receipt
        return send_watch_receipt(payload)

    # 标的名解析走 StockNameResolver 端口（与 notifier/SLA 巡检同一实现，单一取数口径）；
    # 装配失败降级 None → 告知卡只显示代码（名称是渲染增益，不阻断自愈装配）。
    try:
        _name_resolver = build_name_resolver()
    except Exception:  # noqa: BLE001
        _name_resolver = None
    return NoiseSelfHealService(
        rule_noise_repo(), rule_change_repo(),
        todo_service if todo_service is not None else build_todo_service(),
        suppress_notifier=_suppress_notify,
        name_resolver=_name_resolver)


def build_name_resolver() -> Any:
    """标的名解析（REQ-ad0a t4，FR-13）：回执/聚合卡一轮一次批量联查 quant.stocks"""
    return name_resolver()


def build_sla_job(todo_repo: Optional[Any] = None, receipt_service: Optional[Any] = None,
                  name_resolver: Optional[Any] = None,
                  todo_service: Optional[Any] = None) -> Any:
    """到期巡检 job（唯一收敛权威，architecture §4）。

    WatchSlaJob 已下沉本包（qs_watch...watch_engine.sla_job，2026-10-19）——
    消除了 application→inbound 的反向依赖；旧 inbound 路径只剩兼容 shim。
    name_resolver 显式传 None 时缺省构建真实实现（要关名称解析须传假实现/在测试注入）。
    """
    from qs_watch.application.services.watch_engine.sla_job import WatchSlaJob
    return WatchSlaJob(
        todo_repo if todo_repo is not None else build_todo_repo(),
        receipt_service=receipt_service if receipt_service is not None else build_receipt_service(),
        name_resolver=name_resolver if name_resolver is not None else build_name_resolver(),
        # 2026-10-20：L3 超期自动归档要走过领域校验的 close 通道
        todo_service=todo_service if todo_service is not None else build_todo_service())
