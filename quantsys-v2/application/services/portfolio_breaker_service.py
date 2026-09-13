"""组合级回撤熔断状态服务（M4 硬拦截的数据层，2026-09-10，w-f4aa1f6a）

背景：M4 熔断的"禁止新开仓"此前只写在 agent osMemory（决策层标记），
v2 交易撮合网关（trade_guard）完全不感知——熔断期直接调交易 API 买入照样成交。
本服务把熔断状态下沉到 v2 DB（quant.portfolio_circuit_breaker），
供 trade_guard 买入方向硬拦截 + M4 工具触发/解除时双写。

降级策略：状态读取失败（表缺失/DB 故障）→ fail-open 放行并记 warning
（与 M4 工具"API 故障不触发熔断"同哲学：宁可放行+告警，不阻断交易链路）。

2026-09-14（w-32314d00，REQ-24e15d B4-b）：2 处 db_cursor + 裸 SQL → 仓储
（PortfolioCircuitBreakerRepository）。**upsert 的 CASE/COALESCE 语义逐表达式照搬**，
降级策略与返回形状不变。
"""

from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


def _repo():
    from adapters.outbound.repositories.portfolio_circuit_breaker_repository import (
        PortfolioCircuitBreakerRepository,
    )
    return PortfolioCircuitBreakerRepository()


def get_status(account_name: str = 'agent_virtual') -> Dict[str, Any]:
    """读取组合熔断状态。无记录 → {'account_name': ..., 'active': False}。"""
    out = _repo().get_status(account_name)
    if not out:
        return {'account_name': account_name, 'active': False}
    return out


def is_active(account_name: str = 'agent_virtual') -> bool:
    """交易网关硬拦截用：熔断激活 → True（拒买入）。读取失败 fail-open。"""
    try:
        return bool(get_status(account_name).get('active'))
    except Exception as e:  # noqa: BLE001 —— 网关路径绝不因状态读取失败而 500
        logger.warning('portfolio_breaker 状态读取失败，降级放行买入', error=str(e), account=account_name)
        return False


def set_status(
    account_name: str,
    active: bool,
    triggered_drawdown: Optional[float] = None,
    actions_taken: Optional[list] = None,
    unblock_condition: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """写入/更新熔断状态（upsert）。active=False 即解除熔断。

    actions_taken 直接传 Python list（jsonb 列），不再手工 json.dumps。
    """
    _repo().upsert_status(
        account_name=account_name,
        active=active,
        triggered_drawdown=triggered_drawdown,
        actions_taken=actions_taken,
        unblock_condition=unblock_condition,
        note=note,
    )
    logger.info('portfolio_breaker 状态更新', account=account_name, active=active, note=note)
    return get_status(account_name)
