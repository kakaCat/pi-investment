# 技术设计 · 数据契约（REQ-c9f899）

## 1. 表结构变更总览

| 表 | 动作 | 用途 |
|----|------|------|
| quant.watch_todos | 新增 | 待办（闭环状态机载体） |
| quant.watch_runtime_state | 新增 | 闩锁/冷却/去重/事件窗口（R10 持久化） |
| quant.watch_rule_changes | 新增 | 规则变更审计（自愈与授权留痕） |
| quant.watch_receipts | 新增 | 三段回执留痕（升级即/处置后/超时） |
| quant.watch_triggers | 加列 | metric/metric_unit、level、todo_id、suppressed |
| quant.watch_rules | 加列 | noise_state、suppress_until、self_heal_count、last_repair_at |
| quant.watch_interventions | 复用 | 介入预算计数（改为按级别分别计） |

所有新增均为 additive（不改既有列语义、不硬删），满足 R-020「删聚合前先查谁还指着它」。

## 2. quant.watch_todos（核心）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | serial | PK | |
| trigger_id | int | FK → watch_triggers(id) ON DELETE SET NULL | 来源触发（冗余保存 symbol/rule_id） |
| rule_id | int | | 冗余（触发删除后仍可追溯） |
| symbol | varchar(20) | NOT NULL | |
| account | varchar(64) | | 规则归属账户（空=数据缺陷） |
| level | varchar(2) | CHECK in (P0,P1,P2,P3) | 级别 |
| flow_state | varchar(2) | CHECK in (L1,L2,L3) | 流转态 |
| owner_kind | varchar(8) | CHECK in (agent,user) | 谁接手 |
| owner_ref | varchar(64) | | agent 标识或用户标识 |
| autonomy | varchar(16) | CHECK in (autonomous,remind_only) | 授权等级 |
| sla_seconds | int | NOT NULL | 由级别映射 |
| due_at | timestamptz | NOT NULL, INDEX | 晋升/回执判定基准 |
| claimed_at / closed_at | timestamptz | | |
| terminal | varchar(16) | CHECK in (handled,ignored,expired) | 终态（NULL=未收敛） |
| close_reason | text | | 为什么不动/动了什么 |
| next_condition | text | | ignored 必填（NEXT 条件） |
| action_kind | varchar(24) | | trade / rule_change / observe / none |
| decision_audit_id | varchar(64) | | I4：L3 关闭必须有值 |
| escalate_count | int | default 0 | 晋升次数 |
| created_at / updated_at | timestamptz | | |

**索引**：(terminal, due_at)（巡检扫描）、(account, level, terminal)（看查询）、(rule_id, created_at)（自愈统计）。

**约束（可证伪的不变式落到 DB/应用双保险）**：
- terminal 非空 ⇒ closed_at 非空；terminal=ignored ⇒ next_condition 非空。
- terminal 非空且 action_kind 落在 (trade, rule_change) ⇒ decision_audit_id 非空。

## 3. quant.watch_runtime_state（R10）

| 字段 | 说明 |
|------|------|
| rule_id + cond_idx | 联合主键 |
| latched | bool（闩锁） |
| last_triggered_at | timestamptz（冷却基准） |
| cooldown_effective_sec | int（自愈临时延长后的有效冷却） |
| updated_at | timestamptz |

另存 quant.watch_runtime_meta（单行）：heartbeat、current_date、事件窗口裁剪水位；去重窗与触发事件窗口按 30 分钟裁剪。

## 4. quant.watch_rule_changes（审计）

| 字段 | 说明 |
|------|------|
| id / rule_id | |
| changed_by | agent / user / system |
| change_kind | cooldown / threshold / split / merge / retire / suppress / unsuppress |
| before / after | jsonb（仅变更字段） |
| reason | text（必填） |
| trigger_id / todo_id | 溯源 |
| decision_audit_id | agent 自主变更时必填 |
| created_at | |

## 5. quant.watch_receipts

| 字段 | 说明 |
|------|------|
| id / todo_id | |
| kind | escalate（升级即）/ result（处置后）/ timeout（超时）/ suppressed（抑噪通知） |
| channel | 逻辑频道码 |
| delivery_status | sent / failed（与 notification_logs 关联 message_id） |
| payload_digest | 渲染输入摘要（同一待办不重复发同一条回执，幂等） |
| created_at | |

## 6. watch_triggers 加列

- metric varchar(24)、metric_unit varchar(12)：判据产出的 metric（取代裸 value 语义）。
- level varchar(2)：触发时的级别（供统计与回溯）。
- todo_id int：指向待办（可空）。
- suppressed bool default false：该触发被抑噪（只进聚合）。

## 7. 兼容与回填

- 老数据：watch_triggers.metric 回填为 unknown；不做猜测（R-013：不编造）。
- 172 条积压：由迁移脚本按 I3 收敛——escalated/pending 建 todo（P1，owner 按账户）；meta_review 中「规则重叠」类建修规则 todo；其余置 expired 并写明理由。
- 旧 watch_digest_state 保留只读，不再写。
