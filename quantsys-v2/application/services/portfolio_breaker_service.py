"""组合级回撤熔断状态服务（M4 硬拦截的数据层，2026-09-10，w-f4aa1f6a）

背景：M4 熔断的"禁止新开仓"此前只写在 agent osMemory（决策层标记），
v2 交易撮合网关（trade_guard）完全不感知——熔断期直接调交易 API 买入照样成交。
本服务把熔断状态下沉到 v2 DB（quant.portfolio_circuit_breaker），
供 trade_guard 买入方向硬拦截 + M4 工具触发/解除时双写。

降级策略：状态读取失败（表缺失/DB 故障）→ fail-open 放行并记 warning
（与 M4 工具"API 故障不触发熔断"同哲学：宁可放行+告警，不阻断交易链路）。
"""

from typing import Any, Dict, Optional

import structlog

from infrastructure.persistence.database.engine import db_cursor

logger = structlog.get_logger(__name__)


def get_status(account_name: str = 'agent_virtual') -> Dict[str, Any]:
    """读取组合熔断状态。无记录 → {'account_name': ..., 'active': False}。"""
    with db_cursor() as cur:
        cur.execute(
            "SELECT account_name, active, triggered_at, triggered_drawdown, "
            "actions_taken, unblock_condition, note, updated_at "
            "FROM quant.portfolio_circuit_breaker WHERE account_name = %s",
            (account_name,),
        )
        row = cur.fetchone()
    if not row:
        return {'account_name': account_name, 'active': False}
    out = dict(row)
    for k in ('triggered_at', 'updated_at'):
        if out.get(k) is not None:
            out[k] = out[k].isoformat()
    if out.get('triggered_drawdown') is not None:
        out['triggered_drawdown'] = float(out['triggered_drawdown'])
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
    """写入/更新熔断状态（upsert）。active=False 即解除熔断。"""
    import json as _json

    with db_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO quant.portfolio_circuit_breaker "
            "(account_name, active, triggered_at, triggered_drawdown, actions_taken, unblock_condition, note, updated_at) "
            "VALUES (%s, %s, CASE WHEN %s THEN NOW() ELSE NULL END, %s, %s, %s, %s, NOW()) "
            "ON CONFLICT (account_name) DO UPDATE SET "
            "active = EXCLUDED.active, "
            "triggered_at = CASE WHEN EXCLUDED.active THEN NOW() ELSE portfolio_circuit_breaker.triggered_at END, "
            "triggered_drawdown = COALESCE(EXCLUDED.triggered_drawdown, portfolio_circuit_breaker.triggered_drawdown), "
            "actions_taken = COALESCE(EXCLUDED.actions_taken, portfolio_circuit_breaker.actions_taken), "
            "unblock_condition = COALESCE(EXCLUDED.unblock_condition, portfolio_circuit_breaker.unblock_condition), "
            "note = EXCLUDED.note, updated_at = NOW()",
            (
                account_name, active, active, triggered_drawdown,
                _json.dumps(actions_taken, ensure_ascii=False) if actions_taken is not None else None,
                unblock_condition, note,
            ),
        )
    logger.info('portfolio_breaker 状态更新', account=account_name, active=active, note=note)
    return get_status(account_name)
