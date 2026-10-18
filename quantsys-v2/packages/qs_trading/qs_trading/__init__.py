"""qs_trading — 交易执行包（账户·订单·持仓·券商·风险·仿真·盘中止损·保护线·买入区间）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S7）。
包内布局沿用原领域结构：
- qs_trading.application.services.*  14 个交易服务
- qs_trading.domain.{accounts,trading,portfolio,brokers,legacy,risk}.*  六域（含 ports，按域内端口裁决归属）

刻意保持薄 init：本包成员按完整模块路径 import（调用方多为 ServiceFactory/DI 装配）。
"""

__version__ = "0.1.0"
