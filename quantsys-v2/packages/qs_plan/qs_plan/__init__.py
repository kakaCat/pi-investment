"""qs_plan — 交易计划与反思闭环包（REQ-261021222905-6dff · S-1~S-15）。

定位：把「交易计划」立为一等实体。计划（本包 domain/plan）= 决策对象；编译成
watch_rules（application/plan_compiler）由 WatchEngine 执行；成交与复盘数据回流推进
计划状态，定时反思产提案，经确认通道改计划并重编译，形成日级闭环。

本包骨架期只提供目录与包标识（t-180c05）；实体/状态机/服务/编译器由后续卡落入
`qs_plan/domain/plan/` 与 `qs_plan/application/`。

依赖方向（单向，方案卡 import-linter 守门）：
``qs_plan → qs_watch / qs_trading / qs_sourcing / qs_market_data / qs_kernel``；
反向回调（FillSync 推进计划状态）走端口注入，不反向 import。
"""
__version__ = "0.1.0"
