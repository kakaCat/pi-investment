"""qs_sourcing — 选股→信号流水线包（机会生产一条线：池管理+筛选+评分+信号产生+信号执行调度）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S4）。
包内两层沿用原领域布局：
- qs_sourcing.application.services.*          股票池/筛选/评分/信号服务
- qs_sourcing.adapters.outbound.repositories.*  stock_pool / signal / signal_execution 系仓储

刻意保持薄 init：本包成员按完整模块路径 import（调用方多为 ServiceFactory/DI 装配）。
"""

__version__ = "0.1.0"
