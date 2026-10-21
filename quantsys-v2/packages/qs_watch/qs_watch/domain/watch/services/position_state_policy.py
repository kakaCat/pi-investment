"""持仓状态读/写口径（正典实现 · 2026-10-21 从 watch_rule_repository 收口迁移）

此前这两个纯逻辑函数挂在 shell 仓储模块（adapters.outbound.repositories.
watch_rule_repository）里，qs_watch 引擎侧只能惰性跨包 import——仓储层却只
提供"读口径"不提供数据；本质是领域策略。现正典落域名，仓储模块转发导出
（单一实现不变，shell 侧 import 路径全兼容）。

**None 不等于 'none'**：'none' 是"确认无持仓"，None 是"状态不可知"。
调用方拿到 None 必须退回旧行为（不按状态分支、照常评估），而不是当成无持仓。
"""
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

POSITION_STATE_NONE = 'none'
POSITION_STATE_HOLDING = 'holding'


def normalize_position_state(value) -> str:
    """写入口径：None/空 → 'none'；只接受 none/holding（大小写不敏感）。

    非法值抛 ValueError —— 静默落库一个引擎读不懂的状态，等于让规则的分支行为
    变成抽奖；让调用方（API → 400）当场知道。
    """
    if value is None:
        return POSITION_STATE_NONE
    text_value = str(value).strip().lower()
    if text_value in ('', 'none', 'null'):
        return POSITION_STATE_NONE
    if text_value == POSITION_STATE_HOLDING:
        return POSITION_STATE_HOLDING
    raise ValueError("position_state 只接受 none/holding（收到的：%r）" % (value,))


def rule_position_state(rule) -> Optional[str]:
    """读口径（fail-open）：'none'/'holding'；NULL、缺列、未知值 → None。

    纯逻辑（只 getattr，不碰 DB）：分离态/过期对象/缺列懒加载失败都按未知处理。
    """
    try:
        raw = getattr(rule, 'position_state', None)
    except Exception:  # noqa: BLE001 - 分离态/过期对象/缺列懒加载失败都按未知处理
        raw = None
    if raw is None:
        return None
    try:
        return normalize_position_state(raw)
    except ValueError:
        logger.debug('未知 position_state，按状态不可知 fail-open',
                     rule_id=getattr(rule, 'id', None), value=raw)
        return None
