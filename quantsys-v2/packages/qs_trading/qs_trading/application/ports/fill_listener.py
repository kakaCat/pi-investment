"""成交回调端口（交易包中立侧，RFC 017 §2.1.4 / REQ-261021194640-69b8 IF-1、IF-2）

依赖方向不可倒：`qs_watch → qs_trading` 是已声明的单向依赖，反向不存在。
所以本模块只提供**薄端口 + 模块级注册位**，绝不 import 任何消费方实现：

  · 端口：`IFillListener.on_fill(event)`（结构化 `FillEvent`，不是自由文本）；
  · 注册：`register_fill_listener()/get_fill_listener()/unregister_fill_listener()`，
    缺省 `None` = no-op；
  · 出口：`notify_fill(event)` —— 进程内唯一分发点，返回「是否被消费」。

消费侧（qs_watch 的 FillSyncService）由组合根主动注册；本模块不感知 watch。
旧路径 `application/trading/paper_trading_engine.py` 继续导出同名符号（转发），
旧 import 不破。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    'FillEvent',
    'IFillListener',
    'notify_fill',
    'register_fill_listener',
    'get_fill_listener',
    'unregister_fill_listener',
]


@runtime_checkable
class IFillListener(Protocol):
    """成交回调端口：成交落库后收到一条结构化事件（实现方 = qs_watch.FillSyncService）。

    Contract（三条，缺一即破坏可观测性）：
      · 不得抛错穿透回调用方——实现侧自吞并记日志（分发点还会再包一层 try/except）；
      · 必须幂等——同一 trade_id 的重复事件不二次收敛、不二次写时延；
      · 不产生订单/交易动作（RFC §2.4：闭环 = 指令 → agent 执行 → 成交回执）。
    """

    def on_fill(self, event: "FillEvent") -> Any:
        ...


@dataclass(frozen=True)
class FillEvent:
    """一条成交事实（RFC 017 §2.1.4 的字段表）。

    `decision_audit_id` 由调用方按可核验口径给：能拿到决策审计号就传，
    拿不到留 None（消费侧退化为 `trade:<trade_id>` 并在 detail 标 `audit_degraded`，
    **不虚报审计**）。`source` 是成交来源（watch 指令 / IntradayMonitor / 人工 /
    策略名……）：消费侧对**任何来源**都收敛，source 只进留痕。
    """

    account_name: str
    symbol: str
    action: str
    shares: int
    price: float
    trade_id: Optional[int] = None
    order_id: Optional[int] = None
    decision_audit_id: Optional[str] = None
    filled_at: Optional[datetime] = None
    source: str = 'paper_trading'
    reason: Optional[str] = None
    #: REQ-261021222905-6dff：计划归因（None = 计划外成交，不影响计划状态）
    plan_id: Optional[int] = None
    plan_version: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe 投影（供日志/留痕；消费侧也接受这个形状）。"""
        filled_at = self.filled_at
        return {
            'account_name': self.account_name,
            'symbol': self.symbol,
            'action': self.action,
            'shares': self.shares,
            'price': self.price,
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'decision_audit_id': self.decision_audit_id,
            'filled_at': filled_at.isoformat() if hasattr(filled_at, 'isoformat') else filled_at,
            'source': self.source,
            'reason': self.reason,
            'plan_id': self.plan_id,
            'plan_version': self.plan_version,
        }


#: 模块级注册位（组合根写入；None = 未注册 = 成交路径一行也不多跑）。
_FILL_LISTENER: Optional[IFillListener] = None


def register_fill_listener(listener: Optional[IFillListener]) -> None:
    """注册成交回调（组合根唯一入口；传 None = 注销）。

    校验只做最小结构检查（有 `on_fill` 即可），不 import 任何实现方——
    交易与 watch 之间只靠这份协议约定耦合。
    """
    global _FILL_LISTENER
    if listener is not None and not callable(getattr(listener, 'on_fill', None)):
        raise TypeError('fill listener 必须实现 on_fill(event)（IFillListener）')
    _FILL_LISTENER = listener
    logger.info('fill_listener_registered',
                listener=type(listener).__name__ if listener is not None else None)


def get_fill_listener() -> Optional[IFillListener]:
    """当前注册的成交回调（未注册返回 None）。"""
    return _FILL_LISTENER


def unregister_fill_listener() -> None:
    """注销成交回调（测试/回滚用；等价 register_fill_listener(None)）。"""
    register_fill_listener(None)


def notify_fill(event: FillEvent, *, listener: Optional[IFillListener] = None) -> bool:
    """进程内唯一分发出口：把一条成交事实交给监听者一次。

    Returns:
        True  —— 有监听者且消费成功（监听者未抛错）；
        False —— 未注册监听者（静默 no-op，不告警），或监听者抛错（已记日志）。

    纪律（对应 IF-2「永不抛错」）：
      · 本函数**绝不向上抛**：监听者的异常在这里被吞掉并记 `fill_listener_error`；
      · 未注册返回 False，不告警——成交路径与改造前逐字一致；
      · `listener` 为显式的**实例级**覆盖（引擎按实例注入监听器时用）：
        传 None 时回落到模块级注册位，语义与旧实现
        `getattr(self, '_fill_listener', None) or get_fill_listener()` 等价。
    """
    target = listener if listener is not None else _FILL_LISTENER
    if target is None:
        return False
    try:
        target.on_fill(event)
    except Exception as e:  # noqa: BLE001 - 回执失败绝不影响成交（成交已提交）
        logger.error('fill_listener_error（成交已落库，回执失败只记日志）',
                     account=getattr(event, 'account_name', None),
                     symbol=getattr(event, 'symbol', None),
                     action=getattr(event, 'action', None),
                     trade_id=getattr(event, 'trade_id', None),
                     error=str(e))
        return False
    return True
