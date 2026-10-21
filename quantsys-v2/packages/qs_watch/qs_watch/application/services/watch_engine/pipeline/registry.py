"""阶段注册表 —— **唯一的阶段装配点**。

维护纪律（详细步骤见 `docs/guides/watch-pipeline-stages.md`）：
  · 加阶段：在 `stages.py` 写阶段类，然后在 `DEFAULT_STAGES` 元组插入一行；
  · 删阶段：从 `DEFAULT_STAGES` 删掉那一行（阶段类可留可删）；
  · 调顺序：移动 `DEFAULT_STAGES` 里的行位置。
`engine.py` 的 `_process_condition` 只调 `PIPELINE.run(ctx)`，不认识任何具体
阶段——所以上面三种改动**一律不需要动 engine 的 tick 骨架**。
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from .pipeline import Pipeline
from .stage import Stage
from .stages import (
    ConfirmVerifyStage, DailyCapStage, DailyEmitCountStage, DedupStage,
    DeliverStage, DispositionStage, EnvironmentGateStage, EscalationStage,
    FinalizeStage, LatchStage, MarketGateStage, NoiseSuppressStage,
    SettleStage, StaleResidencyStage, TodoStage,
)

#: 阶段注册顺序 = 执行顺序（15 步，与 engine `_process_condition` 原顺序一一对应）。
#: 这里就是「加 / 删 / 调」唯一要改的表；顺序即语义，移动一行即调整流程。
DEFAULT_STAGES: Tuple[Stage, ...] = (
    LatchStage(),           #  1 闩锁/冷却/迟滞
    StaleResidencyStage(),  #  2 陈旧驻留
    EnvironmentGateStage(),  #  3 全局环境闸
    ConfirmVerifyStage(),   #  4 确认核验（staged_break）
    DailyCapStage(),        #  5 每日通知上限
    NoiseSuppressStage(),   #  6 抑噪期短路
    EscalationStage(),      #  7 升级检查
    DispositionStage(),     #  8 处置决策
    MarketGateStage(),      #  9 per-rule 市场门
    DedupStage(),           # 10 去重/重叠治理
    DeliverStage(),         # 11 通知或聚合缓冲
    DailyEmitCountStage(),  # 12 日通知计数
    TodoStage(),            # 13 落待办
    SettleStage(),          # 14 送达后结算（去重标记/介入记账/止损退役）
    FinalizeStage(),        # 15 闩锁回退 + 事件记录
)


class StageRegistry:
    """有序阶段注册表：重名即拒（trace 与测试都靠 name 定位路径）。"""

    def __init__(self, stages: Iterable[Stage] = ()):
        self._stages: List[Stage] = []
        self._names: set = set()
        for stage in stages:
            self.register(stage)

    def register(self, stage: Stage, *, position: Optional[int] = None) -> Stage:
        name = str(getattr(stage, 'name', '') or '').strip()
        if not name:
            raise ValueError('阶段必须声明非空的 name（注册表/trace 的唯一标识）')
        if name in self._names:
            raise ValueError('阶段名重复：%r（注册表要求全局唯一）' % name)
        if position is None:
            self._stages.append(stage)
        else:
            self._stages.insert(position, stage)
        self._names.add(name)
        return stage

    def unregister(self, name: str) -> Stage:
        for i, stage in enumerate(self._stages):
            if stage.name == name:
                self._names.discard(name)
                return self._stages.pop(i)
        raise KeyError('未注册的阶段：%r' % name)

    @property
    def stages(self) -> Tuple[Stage, ...]:
        return tuple(self._stages)

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(stage.name for stage in self._stages)

    def __len__(self) -> int:
        return len(self._stages)

    def build(self, *, name: str = 'condition') -> Pipeline:
        return Pipeline(self._stages, name=name)

    def __repr__(self) -> str:  # pragma: no cover - 排障用
        return 'StageRegistry(%d: %s)' % (len(self._stages), ' → '.join(self.names))


def build_default_registry() -> StageRegistry:
    """按 `DEFAULT_STAGES` 构造注册表（测试可另建实例，不污染全局）。"""
    return StageRegistry(DEFAULT_STAGES)


#: 进程级注册表与流水线：阶段无状态，单例可被全部触发复用。
STAGE_REGISTRY = build_default_registry()
PIPELINE = STAGE_REGISTRY.build(name='condition')
