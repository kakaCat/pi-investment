"""router —— 触发路由（10 次循环 + 每日重置）（REQ-261022235419-2299 / t6）

用户裁定（D-14/16/19）：每规则独立 10 次一循环 ——

- 循环第 1 次触发 → 发 agent 判断（notify_agent）
- 第 2~9 次       → 不处理（skip，零投递）
- 第 10 次        → 直通盯盘群（notify_feishu）并**计数归零**
- 每日收盘定时任务 → **活跃规则**计数 + 处理状态清零（D-18 另一套运行方式；
  非活跃规则不进判定集合，不重置——2026-10-23 用户裁定）

止损不豁免循环节奏（D-17）；「必达」只保不被预算/降噪吞掉。

本模块只做**决策**（返回 RouteDecision），读写计数通过注入的 store 完成；
投递动作在 notify_agent / notify_feishu（t7/t8）。
"""
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 循环长度（用户裁定 10 次一个循环）
CYCLE_LEN = 10

#: 路由去向
ROUTE_AGENT = 'agent'
ROUTE_SKIP = 'skip'
ROUTE_DIRECT = 'direct'

#: 处理状态
PROCESS_PENDING = 'pending'
PROCESS_PROCESSED = 'processed'


@dataclass
class RouteDecision:
    """一次触发的路由决策。

    ``cycle_count`` 是**递增后**的计数（1..10）；0 表示本轮归零后无计数。
    """

    route: str
    cycle_count: int
    reason: str = ''


def next_route(cycle_count: Optional[int]) -> RouteDecision:
    """纯函数：给定当前计数，返回本轮路由决策（不读写存储）。

    计数语义（D-19 per-rule）：
        current 0..9 → next = current+1
        next == 1        → agent（循环首发）
        2 <= next <= 9   → skip
        next == 10       → direct + 归零（返回 cycle_count=10，调用方写 0）
    """
    current = int(cycle_count or 0)
    if current < 0 or current >= CYCLE_LEN:
        current = 0  # 脏数据兜底：按新循环首发处理（宁可多发一次 agent，不漏）

    nxt = current + 1
    if nxt == 1:
        return RouteDecision(route=ROUTE_AGENT, cycle_count=nxt,
                             reason='cycle_first')
    if nxt == CYCLE_LEN:
        return RouteDecision(route=ROUTE_DIRECT, cycle_count=nxt,
                             reason='cycle_tenth')
    return RouteDecision(route=ROUTE_SKIP, cycle_count=nxt, reason='cycle_middle')


def route_trigger(rule, store) -> RouteDecision:
    """按规则当前计数决策并写回（store 需有 get_cycle_count / set_cycle_count）。

    store 契约（可由仓储或内存实现）：
        get_cycle_count(rule_id) -> int | None
        set_cycle_count(rule_id, count) -> None
    读取失败按新循环首发处理（宁可多发一次 agent，不漏判断）。
    """
    rule_id = getattr(rule, 'id', None)
    try:
        current = store.get_cycle_count(rule_id)
    except Exception as exc:  # noqa: BLE001 - 计数读失败 fail-open 首发
        logger.warning('v2.cycle_read_failed', rule_id=rule_id, error=str(exc))
        current = 0

    decision = next_route(current)

    write_value = 0 if decision.cycle_count >= CYCLE_LEN else decision.cycle_count
    try:
        store.set_cycle_count(rule_id, write_value)
    except Exception as exc:  # noqa: BLE001 - 写失败不阻断本轮投递
        logger.warning('v2.cycle_write_failed', rule_id=rule_id, error=str(exc))

    return decision


def reset_daily_cycles(store) -> int:
    """每日收盘重置：**仅活跃规则** cycle_count=0、process_state='pending'。

    活跃口径由 store 实现决定（生产 = watch_rules 的 rule_state='active' 且启用且
    未过期，与引擎加载集合同源）。非活跃规则（invalid/archived/停用/过期）不进
    判定集合，不需要重置（2026-10-23 用户裁定）。

    store 契约：reset_active_cycles() -> int；旧名 reset_all_cycles() 仍兼容
    （语义同活跃规则，仅为既有内存实现保留）。

    返回重置条数（store 实现自报；失败记日志继续，不中断）。
    """
    reset = getattr(store, 'reset_active_cycles', None) or getattr(
        store, 'reset_all_cycles', None)
    if reset is None:
        logger.error('v2.daily_reset_failed', error='store 缺少 reset_active_cycles()')
        return 0
    try:
        count = reset()
    except Exception as exc:  # noqa: BLE001 - 部分失败不中断当日其他任务
        logger.error('v2.daily_reset_failed', error=str(exc))
        return 0
    logger.info('v2.daily_reset', reset_count=count)
    return int(count or 0)
