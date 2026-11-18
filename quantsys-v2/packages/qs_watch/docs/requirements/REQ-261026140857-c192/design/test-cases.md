---
title: 账户级交易计划统一与数据库化重构 · 测试设计
status: draft
owner: PI Investment
reviewers: 用户（最终决策人）
prd: ../requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
created: 2026-10-26
updated: 2026-10-26
---

# 账户级交易计划统一与数据库化重构 · 测试设计

## 1. 测试原则

- 领域状态机和 diff 使用纯单元测试。
- 应用服务使用 fake provider/repo/clock/waker，但编排必须走生产代码。
- 数据库约束、事务、迁移和并发必须使用 `quant_test`，不能用 fake 替代。
- 路由契约使用 FastAPI TestClient 和真实测试仓储。
- 禁止真实下单、真实行情外呼、真实 agent 唤醒和生产数据库写入。
- 旧测试若与新需求冲突，应改成新行为断言，不得为了保留旧测试而恢复文件或单标执行模型。

## 2. 测试结构

```text
tests/plan/
  test_account_plan_migration_contract.py
  test_account_plan_migration.py
  test_plan_item_state_machine.py
  test_plan_generation.py
  test_plan_generation_concurrency.py
  test_plan_activation_transaction.py
  test_plan_compiler.py
  test_plan_fill_loop.py
  test_plan_readiness.py
  test_plan_reconciliation.py
  test_plan_routes.py
  test_plan_rollover.py
  test_plan_reflections.py
  test_plan_no_file_dependency.py
  test_plan_e2e.py
```

组合决策、成交和 WatchEngine 既有相关套件必须同步运行。

## 3. 测试矩阵

### TC-01 增量迁移离线契约

**验证：FR-1/FR-9**

- 加载 `20261105d_account_trading_plan.py`。
- 断言新表、字段、外键、CHECK、部分唯一索引和归因索引完整。
- 默认参数为 dry-run，只有 `--apply` 才进入写路径。
- 不修改旧迁移文件来替代新迁移。

### TC-02 测试库迁移幂等

**验证：FR-1/FR-9**

- 在 `quant_test` 首次 `--apply`，第二次重跑。
- 首次所有对象就绪；第二次无重复表、约束、索引和迁移数据。
- ORM 字段与实际表结构一致。

### TC-03 旧计划按账户分组迁移

**验证：FR-2/FR-9**

- 同账户构造两个旧单标计划，另一账户构造一个。
- 迁移后分别形成一个账户主计划，item 数量正确。
- `legacy_plan_id/migrated_to_plan_id/migrated event` 完整，旧版本和反思仍可查。

### TC-04 迁移减仓基线连续

**验证：FR-6/FR-9**

- 旧计划已有 30% 累计卖出和 70 股剩余。
- 迁移后 `initial_sold_qty/initial_position_qty` 正确。
- 新 item 再卖 20% 后，累计比例按基线 + 新成交计算，不从零开始。
- 历史成交的 plan_id 不变。

### TC-05 异常账户拒绝自动迁移

**验证：FR-9**

- 构造持仓账户不唯一、缺 symbol、规则映射冲突和数量读取失败。
- 对应账户整体回滚并进入异常清单；其他正常账户可迁移。
- 不得生成“迁移成功”run。

### TC-06 多标计划领域校验

**验证：FR-2**

- 一个 revision 包含 buy/sell/hold/avoid 多 item。
- 权重越界、重复未关闭 symbol、非法 action 和无效条件被拒绝。
- avoid 不生成入场规则。

### TC-07 item 状态机

**验证：FR-2/FR-6**

- 覆盖 planned→ready→entering→holding→reducing→exited 和 cancelled。
- 非法终态回退、无持仓 holding、单 item 清仓关闭主计划均被拒绝。
- 每个合法迁移产生正确事件上下文。

### TC-08 每日生成完整落库

**验证：FR-3**

- fake provider 返回两个目标，fake positions 返回一个已有持仓。
- 生成一个 revision、全部 item versions、conditions、states、event 和 succeeded run。
- 生成结果为 draft，不自动激活、不写规则、不下单。

### TC-09 生成事务故障回滚

**验证：FR-3/FR-4**

- 分别在 item version、condition、state、event 写入时注入异常。
- 计划内容全部回滚；run 通过独立事务记 failed。
- 修复后重试可生成完整计划。

### TC-10 串行与并发生成幂等

**验证：FR-3**

- 相同 `account/trade_date/idempotency_key` 串行调用返回 existing。
- 两个数据库 session 并发生成，最终只有一个有效主计划和一个同日待处理 revision。
- 不出现唯一约束异常冒泡成 500 或重复 item。

### TC-11 数据新鲜度与账户校验

**验证：FR-3/FR-7**

- provider 返回错误 account、错误 trade_date、旧 data_as_of、缺风险预算。
- 分别拒绝并不写 revision；错误码和 run 原因准确。
- 生成时间较新不能掩盖行情时点过旧。

### TC-12 持仓合并不自动卖出

**验证：FR-2/FR-3**

- 当前持仓不在 provider targets 中。
- 生成待审核持仓管理项，不自动产生 sell 条件或卖出委托。
- provider 明确 sell 建议仍需审核和激活。

### TC-13 跨日滚动

**验证：FR-3/FR-8**

- 第一天 item 已部分成交，第二天生成新 revision。
- item_id、累计成交和剩余数量连续；新 revision.version 增加。
- 旧 active revision superseded 后仍可查，已完成 item 不被重新激活。

### TC-14 PATCH/APPLY 审核与 CAS

**验证：FR-4**

- PATCH 按 item_id 补条件，只改变草稿并返回 diff。
- agent 缺 audit id、观察窗横跳无说明分别被拒。
- APPLY 后状态 approved，线上 active revision 不变。
- 过期 expected_version 返回 409，重复 APPLY 不重复写版本。

### TC-15 激活前置检查

**验证：FR-4/FR-7**

- draft/reviewing 直接激活、pending entry、缺 exit、数据过期和迁移异常均被拒。
- 返回 PLAN_REVIEW_REQUIRED 或 PLAN_NOT_READY + 具体 reasons。
- 无 enabled 规则产生。

### TC-16 激活统一事务故障注入

**验证：FR-4/FR-5**

- 在第一条规则、第二条规则、映射、审计、版本指针更新分别注入异常。
- 每次均无半激活 revision、孤儿规则、部分映射或成功事件。
- 修复后同一 approved revision 可安全重试。

### TC-17 多标编译与幂等

**验证：FR-5**

- 两个 item，各含 entry/stop/两批 reduce。
- 规则 item_id、plan_version、role、batch 和 position_state 正确。
- 重放编译规则数不变；修改一个 item 不改变另一个 item。
- drift 和孤儿规则能被双向 diff 检出。

### TC-18 新成交必须 item 归因

**验证：FR-6**

- FillEvent 缺 item_id 或 plan_version 时返回 PLAN_ITEM_ATTRIBUTION_REQUIRED。
- 不按 symbol 推进其他 item，不写 receipt。
- 有计划外手工成交时产生未管理持仓对账结果。

### TC-19 多 item 成交与重复回执

**验证：FR-6**

- 两个 item 分别买卖，状态、数量和规则互不影响。
- 同一 trade_id 重放返回 duplicate，filled_qty、规则和事件不重复。
- 原始成交存在但 receipt 缺失时可安全补放。

### TC-20 累计减仓与读取失败

**验证：FR-6**

- 多笔部分卖出按累计比例逐批退役，已退役批次不重复记成功。
- 持仓或成交读取失败返回 degraded，不提交 receipt、不臆造清仓。
- 跨日和迁移基线场景连续。

### TC-21 readiness 原因矩阵

**验证：FR-7**

逐项注入并断言机器原因：

- REVISION_MISSING、DATA_STALE、REVIEW_REQUIRED。
- ENTRY_INCOMPLETE、EXIT_INCOMPLETE、WEIGHT_INVALID。
- RULE_MISSING、RULE_ORPHAN、RULE_VERSION_MISMATCH、RULE_DRIFT。
- POSITION_UNMANAGED、POSITION_MISMATCH、FILL_PROGRESS_MISSING、GENERATION_FAILED。

全部解除后才 ready；不能仅删除错误记录使结果变 ready。

### TC-22 today 语义

**验证：FR-7**

- 正常账户返回当前 revision、全部 items 和 ready=true。
- 无今日 revision 返回 200 + ready=false + REVISION_MISSING，不再只返回 empty。
- 环境闸/待办读取失败分别为明确原因或 null，不伪造 0。
- 批量查询测试防止按 item N+1。

### TC-23 规则与持仓对账

**验证：FR-7**

- 缺失规则、额外规则、错误版本、真实持仓无 item、item holding 但实际无持仓均被检出。
- 对账不自动修改成交或持仓事实。
- 补放缺失成交后，再次对账才清除对应原因。

### TC-24 无文件依赖结构测试

**验证：FR-1/FR-9**

- 临时移走 `core_plan.json`，执行生成、today、激活、成交和反思测试全部通过。
- 扫描生产代码不存在 `OUT.write_text`、`CorePlanAdapter` 或文件回读路径。
- `/api/core-plan` 使用数据库，返回 deprecated 且无 plan_file。

### TC-25 API 完整契约

**验证：FR-3/FR-4/FR-7/FR-8**

- generate 新建 201、重放 200；today/detail 返回规范化 items。
- PATCH/APPLY/ACTIVATE 版本语义正确，所有错误码 HTTP 状态符合 interfaces.md。
- readiness 检查不就绪返回 200 + ready=false；激活不就绪返回 422。
- from-core-plan 不再存在。

### TC-26 反思与知识边界

**验证：FR-8**

- 材料包含账户 revision 和 item 级成交/修改；缺数据段标 missing。
- 反思只生成新草稿提案，不直接覆盖 active revision。
- 唤醒失败不推进 due；知识同步失败不回滚反思。
- 进化层结构扫描无计划写调用。

### TC-27 调度与重启恢复

**验证：FR-3/FR-7/FR-8/FR-10**

- fake scheduler 重跑每日生成、readiness、对账和反思均幂等。
- 在生成后、审核前、激活后和成交回调前分别模拟服务重启。
- 仅凭数据库恢复后续流程；review_pending 可重建唤醒，真实 waker 不被调用。

### TC-28 agent 双端契约

**验证：FR-7/FR-8/FR-9**

- agent-dh 与 agent-ts 使用同一 today/item/readiness fixture。
- item 修改携带 item_id 和 expected_version；错误码和 reasons 原样透传。
- ready=false 时新入场被阻止，风险退出通道仍可用。

### TC-29 策略注册与消费者切换

**验证：FR-9**

- strategy registry、loop report 和 candidate-hunt 提示不再引用 plan_file。
- 策略生命周期重新注册 overlay 时也只写 qs_plan 消费方式。
- 研究测试使用显式 fixture，不要求生产生成 JSON。

### TC-30 端到端闭环

**验证：全部 FR**

走真实路由、`quant_test`、生产组合根同款装配和 fake 外部通道：

```text
generate → patch → apply → activate → today ready
→ item A 买入、item B 部分卖出 → duplicate fill
→ intraday reconcile → close reconcile → reflection
→ 次日 generate → rollover → 新 revision
```

断言每一步数据库事实、归因、事件、运行记录和最终状态；全流程无文件、无真实下单、无真实唤醒。

## 4. 性能与容量检查

- 构造 50 个 item 的账户计划，today 批量查询条数保持常数级，P95 目标 <500ms（测试环境基线需记录硬件与数据量）。
- 编译 50 个 item 不逐条重复查询账户或全部规则。
- 并发测试使用独立数据库事务和真正连接，不以线程调用同一 fake 冒充数据库并发。

## 5. 回归命令

在仓库根目录使用项目完整包路径：

```bash
PYTHONPATH=.:packages/qs_plan:packages/qs_kernel:packages/qs_market_data:packages/qs_sourcing:packages/qs_trading:packages/qs_watch:packages/qs_ops:packages/qs_agenthub:packages/qs_intel:packages/qs_strategy:packages/qs_quantlib python -m pytest tests/plan -q

PYTHONPATH=.:packages/qs_plan:packages/qs_kernel:packages/qs_market_data:packages/qs_sourcing:packages/qs_trading:packages/qs_watch:packages/qs_ops:packages/qs_agenthub:packages/qs_intel:packages/qs_strategy:packages/qs_quantlib python -m pytest tests/test_core_plan_service.py tests/repositories/test_watch_todo_repository.py -q

PYTHONPATH=.:packages/qs_plan:packages/qs_kernel:packages/qs_market_data:packages/qs_sourcing:packages/qs_trading:packages/qs_watch:packages/qs_ops:packages/qs_agenthub:packages/qs_intel:packages/qs_strategy:packages/qs_quantlib python -m pytest tests/application/test_fill_sync_service.py tests/scenarios/test_watch_exec_loop_e2e.py -q
```

组合服务测试重命名后使用新文件路径。按项目配置运行 `black --check`、`py_compile` 和可用的 lint；`ruff` 不存在时必须明确记录未执行，不得写成已通过。

## 6. 验收证据

每个 TC 必须留下：

- 测试文件、测试名和覆盖的 FR。
- 实际命令、退出码和通过数量。
- 数据库迁移/并发/端到端的关键只读查询结果。
- 故障注入的回滚证据，而不只是异常返回值。
- 文件退出和 agent 外部修改的实际证据；未验证项明确列出。

生产迁移、生产调度、真实 agent 和真实下单不属于本轮测试证据，不得用测试库结果替代。
