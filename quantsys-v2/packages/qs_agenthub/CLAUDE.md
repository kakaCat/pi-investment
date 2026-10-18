# qs_agenthub — Agent Hub 包

> 抽离记录：quantsys-v2 单体 S10（2026-10-19）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S10。

## 本包是什么

**AI 工作区 L2**：本目录=「Agent Hub」项目——v2 侧承载的 agent 支持域。上下文只要本文件。

- **Agent OS 对接**：`agent_os_client`（HTTP 客户端：register/trigger/report_result）、`agent_scheduler_tool`、`scheduler_handlers`（30+ 任务 handler）、`agent_notification_service`（Agent OS 通知渠道，agent 优先/飞书降级，受 `AGENT_OS_NOTIFY_ENABLED` 控制）
- **LLM**：`llm_service`（DeepSeek 调用/配置/超时）
- **知识沉淀**：`knowledge_service`（agent_knowledge 表读写）、`chan_knowledge_distiller`（缠论知识蒸馏）
- **决策档案**：`decision_service`（agent_decisions 决策日志/结果回填）、`decision_evaluator`（决策质量评估）
- **进化学习**：`evolution/`（daily_snapshot / decision_score / evolution_fitness / fitness_calculator / lesson_generator / missed_opportunity / score_calculator）

## 目录结构

```
qs_agenthub/
└── application/services/
    ├── agent_os_client.py · agent_scheduler_tool.py · agent_notification_service.py · scheduler_handlers.py
    ├── llm_service.py · knowledge_service.py · chan_knowledge_distiller.py
    ├── decision_service.py · decision_evaluator.py
    └── evolution/                 学习进化子包（8 文件）
```

## 依赖边界（方案卡 §11.3）

- 允许：→ kernel、→ 业务包 public API（qs_notification 通知三件、qs_strategy 策略面…）
- **登记面**：hub→`api/internal/scheduler_webhook.py`（Agent OS webhook 收件器留 app 壳，handlers 经它共享 JOB_HANDLERS 注册表——方向异常（包→app 壳），agent-hub 进一步项目化时收口）
- 暂留 L1：`application/jobs/`（调度任务协议层 JobRegistry 分发面，后续增量卡归并 qs_ops）、`session_service.py`（agent 会话，agent-dh 项目化的耦合件）
- 旧路径 shim：9 alias + `application/services/evolution/`（__path__），30 天观察期

## 常见任务路径

- **加 Agent OS 任务 handler** → `scheduler_handlers.py` `@register_job_handler` 装饰器 + web-hook 分派
- **换 LLM 供应商/参数** → `llm_service.py`（get_config → DEEPSEEK_API_KEY）
- **决策回填/归因** → `decision_service`（update_decision_outcome）+ `decision_evaluator`
- **进化打分/教训生成** → `evolution/decision_score_service` / `evolution/lesson_generator`

## 已修缺陷（2026-10-19）

- ~~`session_service` 测试线程事务挂死~~：根因为 pytest 线程无人调用 `close_session()`（scoped_session 契约），ai_diagnosis 缓存命中路径的 SELECT 开事务后 defer——fixture teardown 补 `close_session()`（test_ai_diagnosis.py / test_session_service.py），运行态（FastAPI 中间件 + jobs 收口）本就健全。分支 `fix/session-service-conn-leak`。
