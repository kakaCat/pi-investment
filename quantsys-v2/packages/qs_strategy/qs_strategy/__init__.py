"""qs_strategy — 策略生命周期包（策略 CRUD/执行/回测编排/进化/验证/代码引擎）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S6）。
包内布局沿用原领域结构：
- qs_strategy.application.services.*          22 个策略服务 + strategy_engine 子包（代码引擎）
- qs_strategy.domain.strategies.*             策略域（base/registry/factory/value_objects + 内置策略实现）

刻意保持薄 init：本包成员按完整模块路径 import（调用方多为 ServiceFactory/DI 装配）。
"""

__version__ = "0.1.0"
