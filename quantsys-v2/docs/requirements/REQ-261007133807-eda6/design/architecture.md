---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# 架构设计（REQ-261007133807-eda6）· 「何时叫 agent」判据收敛与可见化

> 每章标题行带 `serves: FR-x` 标注（缺标注 = 孤儿章节被门禁拦）。
> 术语见 `docs/requirements/REQ-261007133807-eda6/requirement.md`（下称「需求文档」）。

## 目标与总体方案 `serves: FR-1`

**目标**：把「这条触发要不要打断 agent」从**两处判定 + 一处级别映射**收敛成**一个纯函数出口**，
并让出口的结论（码 / 理由 / 命中路径）贯穿落库与卡面。

```
            收敛前                                  收敛后
  EscalationChecker ──┐                  ┌──────────────────────────────┐
  （三条可信路径）     │                  │ decide_escalation(...)       │
                      ├─► decide()       │  · 宪法级 / 预算 / 规则显式   │
  disposition 规则 3 ─┘   （另一处）      │  · 异常波动 / L2 / 元触发     │
  （trigger_level=L2）                    │  · 五道门 / 去重（覆盖码）    │
                                          └──────────────┬───────────────┘
  level_resolver 第 4 条                                 │
  （L2 → P1，只做映射）                    Verdict(should_wake, code, reason, path, note)
                                                         │
                        ┌────────────────────────────────┼─────────────────────────┐
                        ▼                                ▼                         ▼
                 disposition 字符串            watch_triggers 两列           卡片「升级原因」行
                 （既有语义不变）              （一条 SQL 可查）        （旧渲染 + 分级渲染两条都写）
```

**为什么是纯函数**：并发重复与多调用方（tick / 补跑脚本 / 复核作业）要求同一输入必得同一裁决
（需求文档「失败与并发路径 §并发重复」1）；纯函数（无 I/O、无外部状态）同时满足可单测与可回放。

**为什么保留 `disposition` 字符串**：它已是跨表/跨接口的既有事实源（`watch_triggers.disposition`
被统计、查询、SLA 侧消费），本需求**不动它**，只让它由 Verdict 派生 —— 收敛 ≠ 换血。

## 模块改动地图 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 模块/文件 | 类型 | 改动内容 | serves |
|---|---|---|---|
| `domain/watch/services/escalation_verdict.py` | **新增** | 裁决出口 `decide_escalation` / 三条路径 `decide_escalation_paths` / 码表 `EscalationCode` / `Verdict` / 规则侧说明 `explain_escalation` | FR-1、FR-2、FR-4 |
| `domain/watch/services/escalation_checker.py` | 修改 | 三条路径的实现迁入新模块（文案逐字保留）；`should_escalate` 保留为**兼容壳**，内部委托新函数 | FR-1 |
| `domain/watch/services/disposition.py` | 修改 | `decide()` 改为「Verdict → disposition + reason」映射；签名向后兼容（新增 `verdict` 参数） | FR-1 |
| `domain/watch/models.py` | 修改 | `EscalationPolicy.default()` 显式化（含 `anomaly_change_pct`）；新增 `to_dict()` | FR-4 |
| `application/services/watch_engine/engine.py` | 修改 | `tick()` 内改为「一次裁决 → 处置 → 去重覆盖 → 落库/通知」单链路 | FR-1、FR-2 |
| `application/services/watch_engine/escalation_coordinator.py` | 修改 | 退回**数据收集**职责（组装 `QuoteData` / 取 `trigger_level`）；`check()` 保留兼容 | FR-1 |
| `application/services/watch_engine/notifier.py` | 修改 | `TriggerPayload` 增 `escalation_code`；`_record()` 写新列 | FR-2 |
| `application/services/watch_engine/dto.py` | 修改 | 通知变量透传 `escalation_code` | FR-3 |
| `application/notification/notification_facade.py` | 修改 | `escalation_code` 透传（与既有 `escalation_reason` 同路） | FR-3 |
| `infrastructure/notification/formatters/feishu_formatters.py` | 修改 | 旧渲染路径加「升级原因」行 | FR-3 |
| `infrastructure/notification/formatters/watch_level_templates.py` | 修改 | `WatchCardItem` 增两字段；`_skeleton_lines` 加「升级原因」行 | FR-3 |
| `adapters/outbound/repositories/watch_rule_repository.py` | 修改 | `WatchTrigger` 增两列；`record()` 增参数 | FR-2 |
| `adapters/inbound/fastapi_app/routes/watch_async.py` | 修改 | 规则写入口缺省写显式策略；列表追加 `escalation_explain` | FR-4 |
| `application/services/opportunity_to_watch_rule_service.py` | 修改 | 修陈旧 docstring（已删路径不再写成现行规则） | FR-5 |
| `docs/architecture/watch-notification-contract.md` | 修改 | §6 换成「判据表」并与码表同源 | FR-5 |
| `infrastructure/persistence/migrations/20261007_watch_trigger_escalation.py` | **新增** | 两个库各加两列（幂等 + `lock_timeout`） | FR-2 |

**删除**：无。本需求不删任何既有符号——`EscalationChecker.should_escalate`、`disposition.decide`、
`EscalationCoordinator.check` 全部保留（兼容壳），避免牵动既有 12 个调用方与既有测试。

## 裁决顺序（唯一事实源） `serves: FR-1`

`decide_escalation(rule, condition, quote, result, gate=None, cfg=None) -> Verdict` 的判定顺序
**自上而下、先命中先返回**，与收敛前两处判定的**合成语义逐条等价**（顺序不得调换，调换即行为变更）：

| # | 判据 | 命中码 | 是否叫 | 等价来源（收敛前） |
|---|---|---|---|---|
| 1 | `intent == 'exit_stop'` | `CONSTITUTIONAL_INTENT` | ✅（预算豁免） | `disposition.decide` 规则 0 |
| 2 | `daily_wake_count >= daily_budget` | `BUDGET_EXHAUSTED` | ❌ | `decide` 规则 1 |
| 3 | `level ∈ {L0,L1}` 且 `auto_escalate != False` 且规则显式 `escalate=true` | `RULE_EXPLICIT_ESCALATE` | ✅ | `EscalationChecker` 路径 1 |
| 4 | `level ∈ {L0,L1}` 且 `auto_escalate != False` 且 `|涨跌幅| ≥ 阈值` | `ANOMALY_CHANGE_PCT` | ✅ | `EscalationChecker` 路径 3 |
| 5 | `trigger_level == 'L2'` | `RULE_LEVEL_L2` | ✅ | `decide` 规则 3 |
| 6 | `trigger_kind == 'meta'`（过轻门） | `META_REVIEW` | ✅（复核队列） | `decide` 规则 4 |
| 7 | 意图门：`intent == 'trend_observe'` 或动作 ∈ {observe, message} | `OBSERVE_INTENT` | ❌ | `decide` 规则 5① |
| 8 | 金额门：`amount < 账户 × 1%` | `AMOUNT_BELOW_THRESHOLD` | ❌ | `decide` 规则 5② |
| 9 | 增量门：同标的同议题 4h 内已介入 | `SAME_TOPIC_COOLDOWN` | ❌ | `decide` 规则 5③ |
| 10 | 经济门：`期望收益 < k × 介入成本` | `ECONOMIC_BELOW_K` | ❌ | `decide` 规则 5⑤ |
| 11 | 动作 ∈ {buy, sell} | `GATES_PASSED_ACTION` | ✅ | `decide` 规则 5 尾 |
| 12 | 以上皆不命中 | `PENDING_NO_ACTION` | ❌（待处置） | `decide` 规则 5 尾 |
| 13 | 引擎侧去重命中（在裁决**之后**覆盖） | `DEDUPED` | ❌ | `engine` 的 `dedup.check` |
| 14 | 抑噪期（在裁决**之后**覆盖） | `SUPPRESSED` | ❌ | `engine` 抑噪分支 |
| 15 | 未接入/输入缺省 | `UNKNOWN` | ❌ | 新增（禁止臆造） |

**两条纪律**（E1/E3 的直接产物）：

- **第 3、4 条只对 `level ∈ {L0,L1}` 生效**——`L2` 规则不走 checker（收敛前 `EscalationCoordinator`
  第 33 行的短路），故 L2 规则的理由码是 `RULE_LEVEL_L2`（而不是"异常波动"）。
- **第 1 条不经过 `auto_escalate` 开关**（收敛前 `decide` 规则 0 就与开关无关）；同理第 5 条也不受开关影响。

## 数据流 `serves: FR-1, FR-2, FR-3`

```
engine.tick()
  ├─ quote / condition / result           （既有取数，不变）
  ├─ gate = GateContext(...)              （既有组装，不变）
  ├─ verdict = decide_escalation(rule, cond, quote, result, gate, cfg)      ← 唯一裁决点
  ├─ disposition, reason = disposition.decide(rule, cond, gate=gate, verdict=verdict)
  ├─ dedup 命中 → verdict = verdict.overridden(DEDUPED, reason=去重文案)
  ├─ notifier.notify(..., verdict=verdict)
  │     ├─ _record()    → watch_triggers(escalation_code, escalation_reason)
  │     └─ payload      → notification variables(escalation_code/escalation_reason)
  │            └─ 渲染：feishu_formatters（旧） / watch_level_templates（分级）
  └─ events.append(...)  → 事件带 disposition / disposition_reason（既有）+ code
```

**顺序不变式**：裁决 → 处置 → 去重覆盖 → 落库/通知。去重是**裁决之后的覆盖**，
因此 `DEDUPED` 的触发仍保留"它本来会被判成什么"（写进 `escalation_reason` 文本的「原判：…」段）。

## 单点入口与兼容壳 `serves: FR-1`

| 入口 | 收敛后角色 | 兼容性 |
|---|---|---|
| `decide_escalation(...)` | **唯一裁决**（新） | 新增 |
| `EscalationChecker.should_escalate(...)` | 兼容壳：委托 `decide_escalation_paths`，返回 reason 字符串或 `None` | 签名与**文案逐字不变**（既有 10+ 用例不改） |
| `disposition.decide(...)` | Verdict → disposition 映射；不传 `verdict` 时内部自行裁决 | 签名向后兼容（新增可选参数） |
| `EscalationCoordinator.check(...)` | 数据收集 + 兼容壳 | 返回类型不变（`Optional[str]`） |
| `level_resolver.resolve_level(...)` | **不变**：只管级别映射，不再参与"叫不叫" | 无改动 |

> **不做**：不把 `level_resolver` 折进裁决出口。它回答的是"这条触发该给 P0–P3 哪一档"（渲染与 SLA 用），
> 与"要不要打断 agent"是两个问题；把两者合并会把渲染口径与唤醒口径绑死（正是 c392 刚解耦的东西）。

## 错误处理与降级 `serves: FR-1, FR-2`

| 场景 | 行为 | 理由 |
|---|---|---|
| metric 契约不符 | **抛 `WatchMetricContractViolation`**（既有 `require_metric`） | 绝不把"算不出涨跌幅"降级成"不升级" |
| `escalation_code` 落库失败 | 通知与处置照常；`logger.error` 响亮留痕 | 理由可见性不得反噬通知主链 |
| 码不在受控枚举 | 输出 `UNKNOWN` + 保留原文 | 禁止臆造理由 |
| 规则无 `escalation_policy` | 按显式默认值裁决（与旧默认等价） | 存量 7 条规则语义不变 |
| 迁移未跑 | `test_orm_db_drift.py` 报红（既有门禁） | 漂移必须响亮 |

## 关键决策与取舍 `serves: FR-1, FR-2, FR-4`

1. **裁决出口放 domain 层纯函数**（不是 application 服务）：它与 `level_resolver`/`disposition` 同族，
   必须无 I/O 才能被单测穷举（既有 `tests/domain/test_level_router.py` 的真值表打法）。
2. **只加两列（`escalation_code` + `escalation_reason`），不为「命中路径」单开第三列**：
   路径标签是**码的静态属性**（`EscalationCode → PATH_LABEL` 一张表），单开一列等于把同一事实写两份，
   码改名时必然漂移。查询侧要路径就 JOIN 那张表（或按码前缀过滤）。
3. **`disposition` 字符串不废弃**：它是既有跨表事实源（统计/SLA/查询都在用）；本需求只让 Verdict 派生它。
4. **规则侧默认值走 `EscalationPolicy.default()` 显式化**，而不是在路由里手写 dict：
   默认值只有一个事实源，避免 API 与领域两处默认值分叉。
5. **卡面走追加行**：c392 的四段契约刚经用户裁定（其 D-9），本需求只加一行「升级原因」，不动既有行序。

## 测试策略 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

| 层 | 落点 | 覆盖什么 |
|---|---|---|
| 单元（域真值表） | `tests/services/test_watch_escalation_verdict.py` | 15 条判据逐行（含"没叫"的码）；同输入跨调用方一致 |
| 单元（兼容锁） | `tests/services/test_escalation_checker.py`、`tests/services/test_metric_contract.py`（既有，不改） | 三条路径文案与语义逐字不变 |
| 单元（处置映射） | `tests/application/test_watch_disposition.py`（既有） | Verdict → disposition 与既有断言一致 |
| 单元（规则侧） | `tests/domain/test_escalation_policy_defaults.py` | 缺省显式化 + `explain_escalation` 文案 |
| 集成（落库） | `tests/services/test_watch_trigger_escalation_columns.py` | `record()` 写入两列；"没叫"也写码 |
| 集成（渲染） | `tests/notification/test_watch_escalation_reason_line.py` | 旧渲染 + 分级渲染两条都写；无理由隐藏 |
| 端到端 | `tests/application/test_watch_escalation_e2e.py` | 一次触发 → 库有码 → 卡有理由行（见 test-cases.md TC-7） |
| 结构判据 | 判据 2（`grep` 无第二处 L2 叫醒）、判据 6（陈旧文案归零） | 收敛与文档同源 |

## 目录结构 `serves: FR-1, FR-5`

```
domain/watch/services/
  escalation_verdict.py      # 新增：唯一裁决出口 + 码表 + 规则侧说明（单一事实源）
  escalation_checker.py      # 修改：保留三条路径实现与兼容壳
  disposition.py             # 修改：Verdict → disposition 映射
application/services/watch_engine/
  engine.py                  # 修改：单链路接线
  escalation_coordinator.py  # 修改：退回数据收集
  notifier.py                # 修改：落库与变量透传
docs/architecture/
  watch-notification-contract.md  # 修改：§6 判据表（与码表同源）
```
