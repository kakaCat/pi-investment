# 拆分计划（REQ-261007133807-eda6）· 「何时叫 agent」判据收敛与可见化

**需求ID**: REQ-261007133807-eda6
**类型**: feature（`sides: [backend]`）
**设计依据**: `docs/requirements/REQ-261007133807-eda6/design/`（architecture / data-model / interfaces / test-cases / use-cases / backend）
**需求依据**: `docs/requirements/REQ-261007133807-eda6/requirement.md`

## 1. 目标与做法（一段人话）

**目标**：让「这条盯盘触发为什么叫了 agent / 为什么没叫」有**唯一答案**——一个纯函数出口给出
`(是否叫, 理由码, 人话理由, 命中路径)`，理由码落库可查、卡片上能读到、规则上看得见；
且**唤醒量不增**（只做收敛与可见化，不放松也不收紧阈值）。

**做法**：新建 `domain/watch/services/escalation_verdict.py` 作为唯一裁决出口与码表事实源；
`EscalationChecker` 退为兼容壳、`disposition.decide` 退为「Verdict → disposition」映射（两者对外签名与文案不变）；
`engine.tick` 改成「一次裁决 → 处置 → 去重覆盖 → 落库/通知」单链路；`watch_triggers` 加两列；
飞书卡与分级模板各追加一行「升级原因」；规则写入口缺省写显式策略、读接口回显人话说明；修陈旧文案并让文档判据表与码表同源。

## 2. 改动盘点（对照设计文档）

### 2.1 新增 `serves: FR-1, FR-2`

| 文件 | 内容 |
|---|---|
| `domain/watch/services/escalation_verdict.py` | 码表 `EscalationCode`（15 值）+ `Verdict` + `decide_escalation` + `decide_escalation_paths` + `explain_escalation` |
| `infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py` | `watch_triggers` 加 `escalation_code` / `escalation_reason`（幂等 + `lock_timeout`，两库都跑） |
| `tests/services/test_watch_escalation_verdict.py` | 15 条判据真值表 + 跨入口一致性 |
| `tests/services/test_watch_trigger_escalation_columns.py` | 两列落库；"没叫"也有码 |
| `tests/notification/test_watch_escalation_reason_line.py` | 两条渲染路径各出「升级原因」行；无理由隐藏 |
| `tests/domain/test_escalation_policy_defaults.py` | 缺省显式化 + `explain_escalation` 文案 |
| `tests/adapters/test_watch_rules_api_policy.py` | 写入口缺省显式化 + 读接口回显 |
| `tests/services/test_watch_contract_parity.py` | 契约文档判据表 == 代码码表 |
| `tests/application/test_watch_escalation_e2e.py` | 端到端：触发 → 库有码 → 卡有理由行（桩外发） |

### 2.2 修改 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 模块/文件 | 改动 | 不改什么 |
|---|---|---|
| `domain/watch/services/escalation_checker.py` | 三条路径实现迁出；`should_escalate` 保留为兼容壳（返回类型与文案逐字不变） | 不删符号、不改签名 |
| `domain/watch/services/disposition.py` | `decide()` 增可选 `verdict` 参数，改为 Verdict → disposition 映射 | 不改 `disposition` 取值集合与既有文案 |
| `domain/watch/models.py` | `EscalationPolicy.default()` 显式化（`anomaly_change_pct` 取 checker 默认常量）；新增 `to_dict()` | 不删历史字段（只读兼容） |
| `application/services/watch_engine/engine.py` | 单链路接线；去重/抑噪覆盖裁决；事件带 `escalation_code` | 不改 tick 的取数与抑噪顺序 |
| `application/services/watch_engine/escalation_coordinator.py` | 退回数据收集（组装 `QuoteData` / `trigger_level`） | `check()` 保留兼容 |
| `application/services/watch_engine/notifier.py` | `TriggerPayload.escalation_code`；`_record()` 写两列 | 不改通知失败重试语义 |
| `application/services/watch_engine/dto.py` | 通知变量透传 `escalation_code` | 变量只增不改 |
| `application/notification/notification_facade.py` | `escalation_code` 透传 | 同上 |
| `infrastructure/notification/formatters/feishu_formatters.py` | 旧渲染追加「升级原因」行 | 不动 c392 四段行序 |
| `infrastructure/notification/formatters/watch_level_templates.py` | `WatchCardItem` 两字段 + `_skeleton_lines` 追加行 | 不动 P0–P3 模板骨架 |
| `adapters/outbound/repositories/watch_rule_repository.py` | `WatchTrigger` 两列；`record()` 两参数 | 不改既有列语义 |
| `adapters/inbound/fastapi_app/routes/watch_async.py` | 写入口缺省显式化；读列表追加 `escalation_explain` | 不删既有响应字段 |
| `application/services/opportunity_to_watch_rule_service.py` | 修陈旧 docstring | 不改其建规则行为 |
| `docs/architecture/watch-notification-contract.md` | §6 换成判据表（与码表同源） | 不动 §5 卡面契约 |

### 2.3 删除 `serves: FR-1`

**无**。本需求不删除任何文件或符号（兼容壳全保留，避免牵动既有 12 个调用方与既有测试）。

## 3. 接口清单 ↔ 接收卡 key（对照表）

| 接口 id | 接口 | 接收卡 key |
|---|---|---|
| IF-1 | `decide_escalation`（唯一裁决出口） | t2 |
| IF-2 | `explain_escalation`（规则侧说明） | t3 |
| IF-3 | `EscalationChecker.should_escalate`（兼容壳） | t4 |
| IF-4 | `disposition.decide`（Verdict → disposition） | t5 |
| IF-5 | `WatchTriggerRepository.record`（两列落库） | t8 |
| IF-6 | `GET /api/watch/rules`（追加 `escalation_explain`） | t11 |
| IF-7 | 规则写入口（缺省显式化，含 batch） | t10 |
| IF-8 | 卡面渲染契约（两条渲染路径） | t9 |
| IF-9 | 迁移脚本（加两列） | t7 |

## 4. 任务表

| 计划 key | 标题 | 依赖 | 验收标准 | 工作量 |
|---|---|---|---|---|
| t1 | 落码表与裁决结果契约（`EscalationCode` + `Verdict`） | — | `pytest tests/services/test_watch_escalation_verdict.py -q -k code_table` 全绿；码表 15 值、`Verdict` 冻结不可变 | S（files 2 / anchors 3） |
| t2 | 收敛出唯一裁决出口 `decide_escalation`（15 条顺序表） | t1 | `pytest tests/services/test_watch_escalation_verdict.py -q` 全绿；15 条判据逐行命中对应码；同输入经两入口 `code` 相同 | M（files 3 / anchors 6） |
| t3 | 规则侧显式化与人话说明（`explain_escalation` + 默认值显式化） | t1 | `pytest tests/domain/test_escalation_policy_defaults.py -q` 全绿；`EscalationPolicy.default().to_dict() == {"auto_escalate": true, "anomaly_change_pct": 5.0}` | S（files 3 / anchors 4） |
| t4 | 兼容壳：`EscalationChecker.should_escalate` 委托出口 | t2 | `pytest tests/services/test_escalation_checker.py tests/services/test_metric_contract.py -q` 全绿且**用例未改** | S（files 2 / anchors 3） |
| t5 | 处置映射：`disposition.decide` 接受 Verdict | t2 | `pytest tests/application/test_watch_disposition.py tests/application/test_watch_disposition_engine.py -q` 全绿；`escalated` 条数不变 | S（files 2 / anchors 4） |
| t6 | `tick()` 单链路接线（裁决 → 处置 → 去重覆盖 → 通知） | t2, t4, t5 | `pytest tests/services/test_watch_engine.py -q` 全绿；事件含 `escalation_code`；去重覆盖后仍保留「原判」 | M（files 3 / anchors 5） |
| t7 | 迁移：`watch_triggers` 加两列（两库） | — | 两库 `--apply` 退出码 0；`pytest tests/test_orm_db_drift.py -q` 全绿 | S（files 3 / anchors 3） |
| t8 | 落库两列 + 通知变量透传 | t6, t7 | `pytest tests/services/test_watch_trigger_escalation_columns.py -q` 全绿；`deduped`/`auto_observed` 行**也有码** | M（files 4 / anchors 4） |
| t9 | 卡面「升级原因」行（旧渲染 + 分级渲染两条） | t6 | `pytest tests/notification/test_watch_escalation_reason_line.py -q` 全绿；两条路径同形；无理由该行不出现 | M（files 5 / anchors 5） |
| t10 | 规则写入口缺省显式化（含 batch 与校验） | t3 | `pytest tests/adapters/test_watch_rules_api_policy.py -q` 全绿；不传策略落显式默认值；非对象 400；`anomaly_change_pct ≤ 0` → 400 | M（files 3 / anchors 5） |
| t11 | 规则读接口回显「何时会叫我」 | t3, t10 | 同上一并全绿；响应含非空 `escalation_explain`；存量 NULL 策略显示「策略未声明（按默认口径）」；原字段不变 | S（files 3 / anchors 4） |
| t12 | 判据文档与码表同源（修陈旧文案 + 契约 §6 判据表） | t2 | `pytest tests/services/test_watch_contract_parity.py -q` 全绿；`grep -rn "触发频率异常" application/ domain/ docs/architecture/` 0 命中 | S（files 3 / anchors 3） |
| t13 | 端到端验收：触发 → 库有码 → 卡有理由（含唤醒量回归锁） | t8, t9, t11, t12 | `pytest tests/application/test_watch_escalation_e2e.py -q` 全绿；零真实外发（守卫记账）；结构判据 `grep` 0 命中；不破现状全套全绿 | M（files 2 / anchors 6） |

> **工作量口径**：S/M/L 只表示"一轮装不装得下"的粗读；权威读数是 `footprint` 的
> `detailUnits = files×1 + anchors×0.5 + chars/2000`（容量 16 DU）。本计划 13 张卡全部未超容量。

## 5. 批次与并发（依赖安全序）

| 批次 | 卡 | 说明 |
|---|---|---|
| 1 | t1、t7 | 契约与 schema 先行；两者互不依赖，可并行 |
| 2 | t2、t3 | 裁决出口与规则侧说明；依赖 t1 |
| 3 | t4、t5 | 两个兼容壳；依赖 t2（t4/t5 互不依赖，可并行） |
| 4 | t6 | 单链路接线；依赖 t2/t4/t5 |
| 5 | t8、t9 | 落库与渲染；t8 依赖 t6/t7，t9 依赖 t6 |
| 6 | t10、t11 | 规则 API 写入与读出；t10 依赖 t3，t11 依赖 t10 |
| 7 | t12、t13 | 文档同源与端到端验收；t13 依赖 t8/t9/t11/t12 |

**伪依赖说明**：本计划的依赖边多为"语义依赖"而非文件重叠（例如 t4 的兼容壳与 t2 的出口在不同文件），
逐条理由见 `tasks[].dep_reasons`。

## 6. 不做什么（与需求边界一致）

1. 不新增/恢复被删除的历史升级路径（频率 / 量能 / 价格偏差 / 核心区域 / 共振）；
2. 不改既有阈值口径（异常波动 5% / 预算 8 / 金额 1% / 增量 4h / 经济 k=3）；
3. 不动 `level_resolver` 的级别映射（渲染与 SLA 口径不受本需求影响）；
4. 不为「命中路径」单开第三列；不新增索引；不新增开关；
5. 不回填存量规则与存量触发行（`NULL` 如实表示"改造前未记录"）；
6. 不做前端/看板页面（`sides: [backend]`）；不改 agent 侧实现。
