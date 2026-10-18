"""qs_watch — 实时盯盘包（WatchEngine：规则判定→分级触发→通知→回执→降噪自愈）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S8）。
包内布局沿用原领域结构：
- qs_watch.application.services.watch_engine.*  引擎子包（24 文件：engine/conditions/rule_evaluator/
  trigger_judge/deduplication/notifier/receipt/todo/digest/disposition/escalation/noise_self_heal/...）
- qs_watch.application.services.opportunity_to_watch_rule_service
- qs_watch.domain.watch.*                       盯盘域（15 文件）

宿主装配：FastAPI lifespan 经 adapters/inbound/fastapi_app/watch_bootstrap.py（留在 app 壳，方案卡装配层原则）
启动引擎，pytest 下自动跳过。
"""

__version__ = "0.1.0"
