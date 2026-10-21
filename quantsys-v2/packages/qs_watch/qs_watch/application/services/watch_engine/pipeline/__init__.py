"""触发流水线（Pipeline/Chain）：阶段协议 + 上下文 + 注册表 + trace。

`WatchEngine._process_condition` 的 15 步「评估后」流程在这里拆成有序阶段，
engine 只负责构造 `TriggerContext` 并调用 `PIPELINE.run(ctx)`。

维护指南：`quantsys-v2/docs/guides/watch-pipeline-stages.md`
"""
from qs_watch.application.services.watch_engine.pipeline.context import (
    TRACE_DONE, TRACE_ERROR, TRACE_STOP, StageTrace, TriggerContext,
)
from qs_watch.application.services.watch_engine.pipeline.pipeline import (
    Pipeline, PipelineResult,
)
from qs_watch.application.services.watch_engine.pipeline.registry import (
    DEFAULT_STAGES, PIPELINE, STAGE_REGISTRY, StageRegistry, build_default_registry,
)
from qs_watch.application.services.watch_engine.pipeline.stage import (
    CONTINUE, Stage, StageResult,
)

__all__ = [
    'CONTINUE',
    'DEFAULT_STAGES',
    'PIPELINE',
    'STAGE_REGISTRY',
    'Pipeline',
    'PipelineResult',
    'Stage',
    'StageRegistry',
    'StageResult',
    'StageTrace',
    'TRACE_DONE',
    'TRACE_ERROR',
    'TRACE_STOP',
    'TriggerContext',
    'build_default_registry',
]
