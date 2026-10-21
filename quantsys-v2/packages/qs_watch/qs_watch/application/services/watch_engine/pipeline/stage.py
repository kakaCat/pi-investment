"""阶段协议：流水线的最小契约。

约定（保持 `_process_condition` 原语义）：
  · 阶段只读写注入的 `TriggerContext`，不自行调度后续阶段；
  · 返回 `None` / `StageResult.done(...)` = 继续；
  · 返回 `StageResult.stop(reason)` = 终止整条流水线（对应原实现里的 `return`）；
  · 阶段异常不吞：流水线在 trace 里标 `error` 后原样抛出，与改造前
    「异常从 _process_condition 冒出去」的行为一致。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:  # 仅类型标注，避免 context ↔ stage 的运行时循环
    from .context import TriggerContext


@dataclass(frozen=True)
class StageResult:
    """一次阶段执行的结论。`stopped=True` 等价于原实现里的 `return`。"""

    stopped: bool = False
    reason: str = ''

    @classmethod
    def done(cls, reason: str = '') -> 'StageResult':
        return cls(False, reason)

    @classmethod
    def stop(cls, reason: str) -> 'StageResult':
        if not reason:
            raise ValueError('终止阶段必须给出 reason（trace 依赖它定位路径）')
        return cls(True, reason)


#: 显式「继续」单例（阶段也可以直接返回 None，两者等价）。
CONTINUE = StageResult()


@runtime_checkable
class Stage(Protocol):
    """一个流水线阶段。

    实现方只需：类属性 `name`（注册表与 trace 的唯一标识，全局唯一）+ `run(ctx)`。
    阶段必须**无状态**（不持有跨触发数据）——注册表在模块级只构造一次。
    """

    name: str

    def run(self, ctx: 'TriggerContext') -> Optional[StageResult]:
        ...
