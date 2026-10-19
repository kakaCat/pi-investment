# qs_watch — 实时盯盘包

> 抽离记录：quantsys-v2 单体 S8（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S8。

## 本包是什么

**AI 工作区 L2**：本目录=「盯盘」项目（盘中守门员）。上下文只要本文件，不要去根工作区。

- **定位**：WatchEngine 常驻实时盯盘——规则加载/触发判定（trigger_judge&rule_evaluator）/去重/分级通知（L1/L2）/回执聚合/待办闭环（todo_service）/降噪自愈（noise_self_heal）/影子模式时钟/介入台账（intervention_ledger）
- **机会转规则**：`opportunity_to_watch_rule_service` 把 intel 的机会评分转成盯盘规则
- **宿主契约**：引擎唯一宿主 = FastAPI 5001 进程 lifespan（bootstrap 留 app 壳 `adapters/inbound/fastapi_app/watch_bootstrap.py`，pytest 自动跳过；契约守护测试在 `tests/api/test_watch_engine_bootstrap.py`）
- **通知走 qs_notification 包**（三件套），不直连 Feishu

## 目录结构

```
qs_watch/
├── application/services/
│   ├── watch_engine/              引擎子包（24 文件）
│   │   ├── engine.py              WatchEngine 主循环
│   │   ├── trigger_judge.py / rule_evaluator.py / conditions.py  判定层
│   │   ├── deduplication_manager.py / noise_self_heal_service.py 降噪自愈
│   │   ├── notifier.py / watch_channels.py / digest_service.py   通知层（走 qs_notification）
│   │   ├── receipt_service.py / todo_service.py / escalation_coordinator.py
│   │   ├── disposition_engine.py / intervention_ledger.py / shadow_mode_clock.py
│   │   └── observe_aggregator.py / position_lifecycle_service.py / watch_loop_wiring.py / factory.py / dto.py / state_manager.py ...
│   └── opportunity_to_watch_rule_service.py
└── domain/watch/                  盯盘域（15 文件）
```

## 依赖边界（方案卡 §11.3）

- 允许：本包 → kernel、→ `qs_market_data`（行情 quote tick / K 线收盘价）、→ `qs_notification`（通知三件套，白名单既定）、→ `qs_trading`（trading 回调，本就是白名单边 `watch→trading`）、→ `qs_ops`（TradingDayGuard）、→ `qs_agenthub`（AgentNotificationService 唤醒通道）
- pyproject.toml 已声明上述兄弟包依赖（2026-10-19 收口：此前只写 requests/structlog，离开本工作区即坏）
- **不依赖**：不许包内直连 broker 下单——交易动作仍由 trading 项目依事件/回执决策
- 暂留 L1 引用（后续收口）：watch 系仓储（watch_rule/watch_receipt/watch_todo/watch_runtime_state/watch_rule_change/watch_rule_noise/stock_name_resolver 仍在 `adapters/outbound/repositories/`）、持仓/模拟账户仓储（simulation_*，归 qs_trading 项目化时迁出）、`infrastructure.persistence.orm.close_session`（归 kernel S11）、app 壳 bootstrap（L1 原则）
- 2026-10-19 已收口的原越界项：`WatchSlaJob` 下沉本包（`watch_engine/sla_job.py`，旧 inbound 路径为 shim）；TradingDayGuard → qs_ops；AgentNotificationService → qs_agenthub；K 线收盘价 → qs_market_data 的 DataProviderManager；标的名解析 → StockNameResolver 端口注入（factory 装配 PgStockNameResolver）
- 旧路径兼容 shim 在 L1：`application/services/watch_engine/`（__path__）、`application/services/opportunity_to_watch_rule_service.py`（sys.modules 别名）、`domain/watch/__init__.py`（__path__）、`adapters/inbound/fastapi_app/watch_sla_job.py`（转发），30 天观察期后删除
- `watch_triggers` varchar(50) 截断告警（launchd-stderr 预存）：本包域内 dto谁触发谁收，截断问题在 watch 项目化时修

## 常见任务路径

- **加触发规则类型/条件** → `watch_engine/conditions.py`（条件 DSL）+ `trigger_judge.py`（分级判定）
- **改通知文案/落群** → `watch_engine/watch_channels.py`（频道映射）——群选择规则见根 CLAUDE.md「飞书通知分群」
- **降噪调参** → `watch_engine/deduplication_manager.py` / `noise_self_heal_service.py`
- **改机会转规则** → `opportunity_to_watch_rule_service.py`
