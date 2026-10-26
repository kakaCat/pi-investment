---
title: 盯盘引擎 V2 · 数据模型设计
status: draft
owner: 用户（PI Investment）
reviewers: agent
prd: docs/requirements/REQ-261022235419-2299/requirement.md
serves: FR-6, FR-7, FR-11, FR-8
created: 2026-10-23
updated: 2026-10-23
---

# 盯盘引擎 V2 · 数据模型设计  serves: FR-6, FR-7, FR-8, FR-11

## 摘要  serves: FR-6, FR-7, FR-11
- **问题**：触发路由的「10 次循环 + 每日重置」与失效判定需要规则级状态字段支撑，V1 表里没有。
- **方案**：`watch_rules` 新增三列——`trigger_channel`（是否触发 agent，默认 agent）、`process_state`（处理状态）、`cycle_count`（循环计数 0..9）；复用已落的 rule_state / invalidation_threshold_pct / confirm_count。
- **影响面**：一次幂等加列迁移（生产库 + 测试库）；回滚=删列。

## 背景与问题  serves: FR-7, FR-11
### 需求来源  serves: FR-6, FR-7, FR-11
| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-6 | 「设定涨多少或跌多少这个规矩就作废的能力」 | 复用 invalidation_threshold_pct；失效结果落 rule_state=invalid + invalid_reason/invalid_at |
| FR-7 | 「10次一个循环」「第一次触发都要发给agent」 | cycle_count + process_state 承载循环 |
| FR-11 | 「添加一个字段是否触发agent（默认agent触发）」 | trigger_channel 字段，默认 agent |
| FR-8 | 「失效投递给agent，让agent判断」 | rule_state/invalid_reason/invalid_at 已落（2026-10-22） |

### 现状与代价  serves: FR-7
现状：触发后 agent 是否处理过无字段承载，循环节奏只能靠内存态（重启即丢）。代价：重启后循环计数清零会导致 agent 被重复打扰。

### 为什么是现在  serves: FR-7
循环与处理状态是 V2 触发路由的判定依据，必须落库才能跨进程重启保持。

## 目标与非目标  serves: FR-6, FR-7, FR-11
### 目标  serves: FR-7, FR-11
- 循环计数与处理状态落库，重启不丢
- 失效标记三字段（rule_state/invalid_reason/invalid_at）语义不变
- 迁移幂等、可回滚

### 非目标  serves: FR-6
- 不改 watch_triggers / watch_todos 结构（触发与待办表不动）
- 不做规则版本表（rule_state 流转足够）
- 不引入独立循环历史表（计数是当前态，不存历史）

## 方案总览  serves: FR-7, FR-11
**一句话方案**：watch_rules 加三列承载「触发通道 + 处理状态 + 循环计数」，迁移幂等加列，回滚删列。

```text
watch_rules
  ├─ trigger_channel  'agent'(默认) | 'direct'
  ├─ process_state    'pending'(待处理) | 'processed'(已处理)
  └─ cycle_count      0..9（第10次归零）
```

**关键概念**：循环计数 per-rule 独立（D-19）；每日收盘定时任务统一清零（D-18）。

## 架构与依赖  serves: FR-7
- **模块划分**：仓储层 `watch_rule_repository` 承载读写；判定层只读
- **依赖方向**：v2 引擎 → 仓储 → PostgreSQL；单向无环
- **外部依赖**：quant.watch_rules 表
- **与既有架构的差异**：沿用 NEW_RULE_COLUMNS 缺列 fail-open 模式（缺列库降级旧行为，不炸）

## 数据模型  serves: FR-6, FR-7, FR-11
- **实体与字段**：
  - `trigger_channel VARCHAR(16) NOT NULL DEFAULT 'agent'`——CHECK ∈ ('agent','direct')
  - `process_state VARCHAR(16) NOT NULL DEFAULT 'pending'`——CHECK ∈ ('pending','processed')
  - `cycle_count INTEGER NOT NULL DEFAULT 0`——CHECK 0<=x<=9
- **约束与不变量**：rule_state 状态机 active→invalid→archived、invalid→active（裁决回写）不变；cycle_count 归零由第 10 次触发或每日任务执行
- **迁移与回填**：新迁移文件 `20261023_watch_rules_v2_routing.py`；加列 + CHECK + 列注释；存量 trigger_channel='agent'、process_state='pending'、cycle_count=0；生产库与 quant_test 各执行一次；回滚=删列（DROP COLUMN）
- **生命周期**：触发时 cycle_count 递增；agent 处理置 process_state='processed'；每日收盘任务**只清活跃规则**（rule_state='active' 且启用且未过期，与引擎判定集合同源）的计数与处理状态，非活跃规则保持原样（2026-10-23 用户裁定）；规则 archived 后字段冻结不再更新

## 接口设计  serves: FR-7, FR-11
| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `repository.update_cycle(rule_id, count, state)` | 计数+状态 | 更新后规则 | 缺列 → fail-open 跳过 | 新增，走 NEW_RULE_COLUMNS 降级 |
| IF-2 | `repository.reset_daily_cycles()` | 无 | 重置条数 | 部分失败记日志继续 | 新增 |

#### IF-1 repository.update_cycle  serves: FR-7
**语义**

写某规则的 cycle_count 与 process_state；纯计数更新不走处置守卫。

**错误码**

缺列库（未迁移）→ 记 warning 并跳过（行为退化为纯内存，重启丢失但不炸）。

**兼容性**

新增；缺列 fail-open。

#### IF-2 repository.reset_daily_cycles  serves: FR-11
**语义**

每日收盘定时任务调用：**仅活跃规则** cycle_count=0、process_state='pending'。活跃口径 = 引擎判定集合（rule_state='active' 且启用且未过期）；非活跃规则（invalid/archived/停用/过期）不进判定，不重置（2026-10-23 用户裁定）。实现方法名为 `reset_active_cycles()`，旧名 `reset_all_cycles()` 保留为别名（语义同活跃规则）。

**错误码**

单条失败记日志继续；整批失败返回 degraded 标记。

**兼容性**

新增。

## 备选方案  serves: FR-7
| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用）规则表加三列 | 状态随规则走 | 重启不丢、单点事实 | 一次迁移 | — |
| B 独立循环状态表 | watch_cycles 单独存 | 不动规则表 | 多一次 join，状态双写对账成本 | 计数与规则强绑定，分表引入一致性风险 |
| C：什么都不做 | 内存计数 | 零改动 | 重启即丢、agent 被重复打扰 | 生产曾实测内存态丢失问题 |

## 四风险与证据  serves: FR-7
| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 需要这个状态吗 | 用户 D-14~D-19 逐条裁定循环语义 | 已验证 |
| 可用性 | 状态可理解吗 | 三字段语义直白（通道/状态/计数） | 已验证 |
| 可行性 | 迁移可行吗 | 今日同模式迁移（rule_state 等四列）已双库成功 | 已验证 |
| 商业可行性 | 成本可接受吗 | 三列，存储可忽略 | 已验证 |

**未验证项的补课计划**：无。

## 失败模式与回滚  serves: FR-11
| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 迁移锁表 | 与在线读写冲突 | 迁移挂起 | pg_locks 监控 | 终止泄漏事务后重跑（幂等） | agent |
| 每日任务漏跑 | 调度故障 | 次日计数不清零、agent 被少打扰 | inprocess_job_runs 对账 | 手动触发任务；计数可手工清零 | agent |
| 计数错乱 | 并发写 | 多发/漏发 agent | 触发日志对账 | UPDATE 清零重来 | agent |

- **开关**：无新增（复用调度开关）
- **回滚演练**：迁移可回滚（DROP COLUMN）；今天同模式迁移已演练过锁等待处理
- **不可逆动作**：无

## 跨关注点  serves: FR-7, FR-11
| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增面 | 内部状态字段，无外部读写 |
| 隐私与合规 | 无新增采集 | 交易状态本机库存储 |
| 成本 | 可忽略 | 三列 × 数百行 |
| 可观测性 | 覆盖 | 计数/状态变化入日志与触发事件 |
| 性能与容量 | 可忽略 | 单表单行更新 |
| 文档与支持 | 本文 + 需求文档 | 字段语义在注释与本文件 |

## 交付拆分与里程碑  serves: FR-6, FR-7, FR-11
| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | 迁移文件 + 双库执行 | VERIFY OK；quant_test 同步 | agent | 拆分后第 1 天 |

## 需求追溯  serves: FR-6, FR-7, FR-8, FR-11
| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-6 | 数据模型（失效三字段复用） | tests/v2/test_invalidation.py | invalid 标记正确 |
| FR-7 | 数据模型（cycle_count/process_state） | tests/v2/test_trigger_routing.py | 循环行为确定 |
| FR-8 | 数据模型（invalid 留痕） | tests/v2/test_invalidation.py | invalid_reason 非空 |
| FR-11 | 数据模型（trigger_channel） | tests/v2/test_daily_reset.py | 每日清零生效 |

## 常见问题  serves: FR-7, FR-11
| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 计数清零后次日 agent 被重新打扰——这是设计本意（每日重新审视） |
| 6 个月后会成为什么负担 | 字段语义需保持注释同步——已在列注释落 |
| 流量涨 10 倍先坏在哪里 | 单行 UPDATE 频率——规则量级内无压力 |
| 谁半夜被叫起来、手上有什么 | 无人——迁移幂等可重跑 |
| 数据错了怎么修、修得回来吗 | UPDATE 修正即可，全部可逆 |
| 这个决定错了多久能发现 | 当日触发日志对账即可见 |

## 开放问题  serves: FR-11
| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 每日重置任务的时点 | A 15:00 收盘后 / B 16:30 与 health check 同档 | agent | 拆分阶段定 |

## 附录  serves: FR-6
- **原型与验证材料**：今日 rule_state/invalidation_threshold_pct 迁移（20261022_watch_rules_state.py）为同模式先例
- **相关文档**：[requirement.md](../requirement.md)、[architecture.md](architecture.md)
- **评审记录**：待设计确认门
- **变更历史**：v1.0 2026-10-23 初版
