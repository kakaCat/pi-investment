"""qs_intel — 市场情报博弈包（对手行为·操纵检测·风格·情绪·微观结构·LHB·热点图·机会评分）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S5）。
包内布局沿用原领域结构：
- qs_intel.application.services.*   19 个情报服务
- qs_intel.domain.competition.*     博弈分析域（零 I/O）
- qs_intel.domain.industry_chain.*  产业链域（model/ports/seed/service）

刻意保持薄 init：本包成员按完整模块路径 import（调用方多为 ServiceFactory/DI 装配）。
"""

__version__ = "0.1.0"
