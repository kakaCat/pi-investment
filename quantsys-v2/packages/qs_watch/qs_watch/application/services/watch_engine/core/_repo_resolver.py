"""qs_watch 出向仓储/来源唯一绕行点（2026-10-21 · 反向越层阶段1）

本包不再直引 `adapters.outbound.repositories.*`（包引内部适配器越层）；
改经 DI 注册表按键取实现。键 = 端口类（qs_watch.domain.watch.ports 11 类 +
qs_kernel 2 类）。生命周期：仓储一律 transient（保持旧行为「现场 new、per-use
实例」）；SimulationORMRepository 复用 'simulation' 既有 singleton 条目。

前置：进程经 ServiceFactory.initialize() 引导（main lifespan 已接线；测试由
conftest._bootstrap_service_factory 承担）。未注册键 resolve 抛 ValueError——
这是被守住的契约（不返回 None，静默降级已清除）。
"""
from __future__ import annotations

from qs_kernel.domain.ports import IStockRepository, ISimulationRepository
from qs_watch.domain.watch.ports import (
    IStockNameResolver,
    IPoolMemberSource,
    INewsSource,
    ISimulationPositionRepository,
    IWatchDigestStateRepository,
    IWatchInterventionRepository,
    IWatchNewsAlertRepository,
    IWatchOutcomeRepository,
    IWatchPoolBindingRepository,
    IWatchReceiptRepository,
    IWatchRuleChangeRepository,
    IWatchRuleNoiseRepository,
    IWatchRuleRepository,
    IWatchRuntimeStateStore,
    IWatchTodoRepository,
    IWatchTriggerRepository,
)
from infrastructure.services.service_factory import ServiceFactory


def _resolve(key):
    return ServiceFactory.resolve(key)


# 仓储（transient：与旧行为等价）
def watch_rule_repo():
    return _resolve(IWatchRuleRepository)


def watch_trigger_repo():
    return _resolve(IWatchTriggerRepository)


def watch_digest_state_repo():
    return _resolve(IWatchDigestStateRepository)


def watch_intervention_repo():
    return _resolve(IWatchInterventionRepository)


def watch_outcome_repo():
    return _resolve(IWatchOutcomeRepository)


def sim_position_repo():
    return _resolve(ISimulationPositionRepository)


def sim_repo():
    return _resolve(ISimulationRepository)  # 'simulation' 既有 singleton 条目


def stock_repo():
    return _resolve(IStockRepository)  # 'stock' 既有 singleton 条目


def watch_pool_binding_repo():
    return _resolve(IWatchPoolBindingRepository)


def news_alert_repo():
    return _resolve(IWatchNewsAlertRepository)


def runtime_state_store():
    return _resolve(IWatchRuntimeStateStore)


def todo_repo():
    return _resolve(IWatchTodoRepository)


def receipt_repo():
    return _resolve(IWatchReceiptRepository)


def rule_change_repo():
    return _resolve(IWatchRuleChangeRepository)


def rule_noise_repo():
    return _resolve(IWatchRuleNoiseRepository)


# 来源适配（同样经端口键取实现）
def pool_member_source():
    return _resolve(IPoolMemberSource)


def news_source():
    return _resolve(INewsSource)


def name_resolver():
    return _resolve(IStockNameResolver)
