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
    from adapters.outbound.repositories.watch_runtime_state_repository import (
        WatchRuntimeStateRepository,
    )
    return WatchRuntimeStateRepository()


def build_todo_repo() -> Any:
    from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
    return WatchTodoRepository()


def build_todo_service() -> Any:
    from application.services.watch_engine.todo_service import TodoService
    return TodoService(build_todo_repo())


def build_receipt_service() -> Any:
    """三段回执服务（sender 接 NotificationFacade，见 watch_channels）"""
    from adapters.outbound.repositories.watch_receipt_repository import WatchReceiptRepository
    from application.services.watch_engine.receipt_service import ReceiptService
    from application.services.watch_engine.watch_channels import send_watch_receipt
    return ReceiptService(WatchReceiptRepository(), sender=send_watch_receipt)


def build_self_heal_service(todo_service: Optional[Any] = None) -> Any:
    from adapters.outbound.repositories.watch_rule_change_repository import (
        WatchRuleChangeRepository,
    )
    from adapters.outbound.repositories.watch_rule_noise_repository import (
        WatchRuleNoiseRepository,
    )
    from application.services.watch_engine.noise_self_heal_service import NoiseSelfHealService
    return NoiseSelfHealService(
        WatchRuleNoiseRepository(), WatchRuleChangeRepository(),
        todo_service if todo_service is not None else build_todo_service())


def build_sla_job(todo_repo: Optional[Any] = None, receipt_service: Optional[Any] = None) -> Any:
    """到期巡检 job（唯一收敛权威，architecture §4）。

    WatchSlaJob 在 inbound 层（adapters/inbound/fastapi_app/watch_sla_job.py），
    本函数被 inbound 的定时任务与 application 的 factory 共用；为不引入
    application→inbound 的反向依赖，这里用惰性 import（运行时才解析）。
    """
    from adapters.inbound.fastapi_app.watch_sla_job import WatchSlaJob
    return WatchSlaJob(
        todo_repo if todo_repo is not None else build_todo_repo(),
        receipt_service=receipt_service if receipt_service is not None else build_receipt_service())
