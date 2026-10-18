"""qs_agenthub — Agent Hub 包（agent-os 对接 / LLM / 知识沉淀 / 决策档案 / 进化学习）。

由 quantsys-v2 单体抽离（2026-10-19，方案卡 docs/plans/package-boundaries-import-linter.md S10）。
包内布局沿用原领域结构：
- qs_agenthub.application.services.*         agent_os_client / agent_scheduler_tool / agent_notification_service /
  scheduler_handlers / llm_service / knowledge_service / decision_service / decision_evaluator / chan_knowledge_distiller
- qs_agenthub.application.services.evolution 进化学习子包（daily_snapshot / decision_score / fitness / lesson_generator / ...）

通知链：NotificationFacade 的 agent 渠道由本包 agent_notification_service 承接（优先投 Agent OS，飞书降级，
AGENT_OS_NOTIFY_ENABLED 开关语义不变）。
"""

__version__ = "0.1.0"
