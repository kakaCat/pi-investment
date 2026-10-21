"""流水线执行器：按注册顺序跑阶段，并落 trace。

行为契约（与 `_process_condition` 改造前逐条对应）：
  · 顺序 = 注册顺序；阶段之间没有隐式跳转；
  · 某阶段返回 `StageResult.stop(reason)` → 立即终止，后续阶段不执行；
  · 阶段抛异常 → trace 标 `error` 后原样上抛（不新增吞异常语义）；
  · 每次 run 的 trace 落在 `ctx.trace`，同时以不可变快照随 `PipelineResult` 返回。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .context import TRACE_ERROR, TRACE_STOP, StageTrace, TriggerContext
from .stage import Stage


@dataclass(frozen=True)
class PipelineResult:
    """一次流水线执行的结果（可观测出口）。"""

    stopped: bool
    stop_reason: Optional[str]
    trace: Tuple[StageTrace, ...]

    @property
    def executed(self) -> Tuple[str, ...]:
        return tuple(entry.stage for entry in self.trace)

    @property
    def stopped_at(self) -> Optional[str]:
        return self.trace[-1].stage if self.stopped and self.trace else None

    def statuses(self) -> Tuple[str, ...]:
        return tuple(entry.status for entry in self.trace)


class Pipeline:
    """有序阶段链（Chain）。无状态：同一实例可被多个触发复用。"""

    def __init__(self, stages: Iterable[Stage], *, name: str = 'condition'):
        self.name = name
        self._stages: Tuple[Stage, ...] = tuple(stages)

    @property
    def stages(self) -> Tuple[Stage, ...]:
        return self._stages

    @property
    def stage_names(self) -> Tuple[str, ...]:
        return tuple(stage.name for stage in self._stages)

    def run(self, ctx: TriggerContext) -> PipelineResult:
        """按注册顺序执行；终止/异常都会在 ctx.trace 留下最后一个阶段的状态。"""
        for stage in self._stages:
            entry = StageTrace(stage=stage.name)
            ctx.trace.append(entry)
            try:
                outcome = stage.run(ctx)
            except Exception as exc:  # noqa: BLE001 - 记录后原样上抛，不改变失败语义
                entry.status = TRACE_ERROR
                entry.reason = '%s: %s' % (type(exc).__name__, exc)
                raise
            if outcome is None:
                continue
            if outcome.reason:
                entry.reason = outcome.reason
            if outcome.stopped:
                entry.status = TRACE_STOP
                ctx.stop_reason = outcome.reason or stage.name
                return PipelineResult(True, ctx.stop_reason, tuple(ctx.trace))
        return PipelineResult(False, None, tuple(ctx.trace))

    def __repr__(self) -> str:  # pragma: no cover - 排障用
        return 'Pipeline(%s, %d stages: %s)' % (
            self.name, len(self._stages), ' → '.join(self.stage_names))


__all__ = ['Pipeline', 'PipelineResult']
