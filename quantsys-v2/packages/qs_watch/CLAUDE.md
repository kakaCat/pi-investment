# qs_watch — 实时盯盘包

> 抽离记录：quantsys-v2 单体 S8（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S8。

## 本包是什么

**AI 工作区 L2**：本目录=「盯盘」项目（盘中守门员）。上下文只要本文件，不要去根工作区。

- **定位**：V2 定时任务驱动股票级与市场级盯盘——条件求值/两段式伏击/失效判定/分级通知/失败重试；
  旁路继续承担回执聚合、待办闭环、降噪自愈、影子模式时钟和持仓生命周期。
- **机会转规则**：`opportunity_to_watch_rule_service` 把 intel 的机会评分转成盯盘规则
- **宿主契约**：唯一宿主 = FastAPI 5001 lifespan；V2 注册进 JobRegistry，旁路由独立 sidecar 承载
- **通知走 qs_notification 包**（三件套），不直连 Feishu

## 目录结构

```
qs_watch/
├── application/services/
│   ├── watch_engine/
│   │   ├── v2/                    股票/市场判定、条件上下文、归档路由、通知与调度
│   │   ├── core/                  旁路宿主与共享装配（无 V1 股票 tick/15 阶段管线）
│   │   ├── rules/                 共享条件 DSL、规则变更联动与治理
│   │   ├── market/                市场映射、政策监控与板块成分适配
│   │   ├── lifecycle/             持仓生命周期、成交回执、走势回填
│   │   └── notify/                待办、回执、摘要与通知频道
│   └── opportunity_to_watch_rule_service.py
└── domain/watch/                  盯盘域与纯领域判定
```

## 依赖边界（方案卡 §11.3）

- 允许：本包 → kernel、→ `qs_market_data`（行情 quote tick / K 线收盘价）、→ `qs_notification`（通知三件套，白名单既定）、→ `qs_trading`（trading 回调，本就是白名单边 `watch→trading`）、→ `qs_ops`（TradingDayGuard）、→ `qs_agenthub`（AgentNotificationService 唤醒通道）
- pyproject.toml 已声明上述兄弟包依赖（2026-10-19 收口：此前只写 requests/structlog，离开本工作区即坏）
- **不依赖**：不许包内直连 broker 下单——交易动作仍由 trading 项目依事件/回执决策
- 暂留 L1 引用（后续收口）：watch 系仓储（watch_rule/watch_receipt/watch_todo/watch_runtime_state/watch_rule_change/watch_rule_noise/stock_name_resolver/watch_pool_binding/watch_news 仍在 `adapters/outbound/repositories/`）；stock_pools 只读（PoolMemberSource，sourcing 领域表只读不写）、持仓/模拟账户仓储（simulation_*，归 qs_trading 项目化时迁出）、`infrastructure.persistence.orm.close_session`（归 kernel S11）、app 壳 bootstrap（L1 原则）
- 2026-10-19 已收口的原越界项：`WatchSlaJob` 下沉本包（`watch_engine/sla_job.py`，旧 inbound 路径为 shim）；TradingDayGuard → qs_ops；AgentNotificationService → qs_agenthub；K 线收盘价 → qs_market_data 的 DataProviderManager；标的名解析 → StockNameResolver 端口注入（factory 装配 PgStockNameResolver）
- 旧路径兼容 shim 在 L1：`application/services/watch_engine/`（__path__）、`application/services/opportunity_to_watch_rule_service.py`（sys.modules 别名）、`domain/watch/__init__.py`（__path__）、`adapters/inbound/fastapi_app/watch_sla_job.py`（转发），30 天观察期后删除
- `watch_triggers` varchar(50) 截断告警（launchd-stderr 预存）：本包域内 dto谁触发谁收，截断问题在 watch 项目化时修

## 常见任务路径

- **加触发规则类型/条件** → 共享 `watch_engine/conditions.py`（条件 DSL）；V2 由 `watch_engine/v2/condition_evaluator.py` 统一求值；两段式伏击状态机在 `watch_engine/v2/staged_break_manager.py`，20 日均量保护在 `watch_engine/v2/rule_evaluator.py`
- **改通知文案/落群** → `watch_engine/watch_channels.py`（频道映射）——群选择规则见根 CLAUDE.md「飞书通知分群」
- **降噪调参** → `watch_engine/noise_self_heal_service.py`；V2 抑噪期只留 suppressed 样本、不通知
- **改机会转规则** → `opportunity_to_watch_rule_service.py`
- **池级盯盘** → `watch_engine/pool_watch_service.py`（绑定表 watch_pool_bindings，`/api/watch/pool-bindings`）
- **消息监控** → `watch_engine/news_watch_service.py`（持仓新闻+公告两级词表，`POST /api/watch/news-scan` 手动，sidecar 15 分钟自动）
- **条件回测** → `watch_engine/condition_simulator.py`（`POST /api/watch/conditions/simulate`，建规则前看触发密度）
- **agent 接口** → `GET /api/watch/brief`（一屏简报）、`GET /api/watch/triggers?since=`（增量轮询）、`market_gate`（环境复合门，schema 端点有规格）
- **预判验证闭环** → `watch_engine/outcome_backfill_service.py`（触发后 5/10/20 交易日回填，sidecar 每日）+ 领域 `domain/watch/services/outcome_direction.py`（预判方向/命中判定）+ 仓储 L1 `watch_outcome_repository.py` + 查询 `GET /api/watch/outcomes/stats`
- **规则停用守卫** → 领域 `domain/watch/services/rule_guard.py`（`guard_disable_rule`：宪法级止损规则停用必须随附理由）卡点在仓储 `update_fields`（L1）；自愈裸 SQL 旁路在 `noise_self_heal_service._config_repair_after` 同源拦截
- **市场环境联动** → `watch_engine/v2/market_watch_service.py`（市场级规则扫描与 V2 路由）+ `watch_engine/held_sector_map.py`（持仓→板块映射，sidecar 每日重建）+ 领域 `domain/watch/services/market_rule_evaluator.py`（含 held_sector_pct 评估与校验）
