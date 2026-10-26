---
title: 盯盘执行闭环三接缝 · 架构设计（REQ-261021194640-69b8）
status: draft
owner: agent（本窗口）
reviewers: 投资人
prd: docs/requirements/REQ-261021194640-69b8/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8
created: 2026-10-21
updated: 2026-10-21
---

# 盯盘执行闭环三接缝 · 架构设计  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

## 摘要  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **问题**：盯盘能发指令，agent 成交后没有任何回写；消息命中不投递、不执行没有规则联动、超时口径失真。
- **方案**：在三条接缝上补「事件源 / 投递 / 闭环」：成交事件从交易服务发出，消息命中建待办并唤醒，不执行走规则联动，超时按真实时限收敛。
- **影响面**：交易包新增中立成交端口；盯盘包新增消息桥、扩展待办与 SLA；宿主侧新增统计端点与一列可空字段；不改既有表语义。

## 背景与问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 需求来源  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | agent 卖出后系统要知道，并收敛待办与退出规则 | 交易服务成交落库后发结构化成交事件，盯盘收敛器幂等收敛 |
| FR-2 | 买入后状态要立刻变持有，别反复喊建仓 | 复用成交事件驱动状态翻转，秒级生效 |
| FR-3 | critical 消息要建 P1 待办并叫醒 agent | 新增消息→待办桥，复用既有 owner 路由与唤醒 |
| FR-4 | 盘后公告也要能扫到 | sidecar 拆盘中/盘后两段，消息窗口独立 |
| FR-5 | 不执行要真改规则并留审计 | close 接口扩展结构化动作，接既有规则联动 |
| FR-6 | 超时要按真实期限发一次，别误报 | 统一时间基准 + 执行期限巡检 + 回执幂等 |
| FR-7 | 要能读到三态计数与时延 | 新增只读统计端点与仓储聚合 |
| FR-8 | 自动补挂的止盈规则要能触发 | 补挂时写持仓状态，状态门不再跳过 |

### 现状与代价  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

盯盘的成交回调唯一填报点在模拟撮合引擎，agent 走真实成交接口时零通知；`watch_triggers.detail` 含执行明细 0 行、P0 待办悬空（生产证据）。消息命中只发飞书卡，不建待办也不唤醒，判断环节空转。规则联动类已实现但零生产调用，超时巡检因时间基准不一致产生误报。

### 为什么是现在  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

未执行止损被 `expired` 归档并计入「已收敛」，统计口径与真实风险脱节；越晚修，历史样本越不可信。

## 目标与非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 任一来源的成交在落库后 50ms 内通知盯盘，收敛结果可查询（P95 < 50ms，日志时延统计）。
- critical 消息命中持仓后，agent 在 1 个扫描周期内收到待办与唤醒。
- 不执行与超时都有终态或催办，且同一事件不重复打扰。
- 执行闭环三态计数可读，且与台账一致。

### 非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 不做 v2 侧自动下单（D-1）：下单与最终判断在 agent，v2 只发指令与兜底。
- 不做交易计划实体、盘中实时资金流、减仓数量化（D-2）：本期只补三条接缝。
- 不改自动兜底止损（30 分钟百分比）的行为：保留作为最后防线。
- 不改既有待办状态机枚举：三态映射复用 `handled/ignored/expired`。

## 方案总览  serves: FR-1, FR-2, FR-3, FR-5, FR-6

**一句话方案**：把「成交」「消息」「不执行」三类事实都变成盯盘可消费的结构化事件，由既有收敛器/待办/SLA 闭环承接。

```text
agent ──下单──▶ 交易服务（成交落库）
                   │ notify_fill（新中立端口）
                   ▼
             盯盘 FillSyncService ──▶ 待办 handled / 退出规则退役 / 状态翻转
消息扫描 ──critical──▶ NewsTodoBridge ──▶ P1 待办 + 唤醒 agent
agent ──close(ignored, rule_change)──▶ TodoService ──▶ RuleChangeLinkage ──▶ 规则 + 审计
SLA 巡检 ──期限到──▶ 超时回执（一次）──▶ L3 催办
```

**关键概念**：成交事件（FillEvent）= 落库后的事实投影，不是下单请求；消息待办 = 消息命中的处置载体，不是交易动作。

## 架构与依赖  serves: FR-1, FR-3

### 模块划分与文件结构  serves: FR-1, FR-3

| 文件 | 新建/修改 | 职责（一句话） |
|---|---|---|
| `packages/qs_trading/qs_trading/application/ports/fill_listener.py` | 新建 | 中立成交端口：FillEvent、监听协议、注册表、notify_fill 出口 |
| `application/trading/paper_trading_engine.py` | 修改 | 保留同名导出做兼容转发；成交后改调端口出口 |
| `packages/qs_trading/qs_trading/application/services/account_trading_service.py` | 修改 | 真实成交落库后发事件，异常只记日志 |
| `packages/qs_watch/.../watch_engine/news_todo_bridge.py` | 新建 | critical 消息→P1 待办+唤醒，窗口内去重 |
| `packages/qs_watch/.../watch_engine/news_watch_service.py` | 修改 | 扫描后把 critical 命中交给桥（未注入=旧行为） |
| `packages/qs_watch/.../watch_engine/policy_watch_service.py` | 修改 | 政策命中持仓板块时同上 |
| `packages/qs_watch/.../watch_engine/engine.py` | 修改 | sidecar 拆盘中/盘后两段，消息窗口独立 |
| `packages/qs_watch/.../watch_engine/position_lifecycle_service.py` | 修改 | 自动补挂止损/止盈时写持仓状态 |
| `packages/qs_watch/.../watch_engine/todo_service.py` | 修改 | create 支持证据；close 成功后触发规则联动 |
| `packages/qs_watch/.../watch_engine/sla_job.py` | 修改 | 执行期限巡检 + 时间基准统一 |
| `packages/qs_watch/.../watch_engine/factory.py` | 修改 | 装配消息桥、规则联动、成交监听 |
| `adapters/inbound/fastapi_app/routes/watch_async.py` | 修改 | 新增执行统计端点 |
| `adapters/inbound/fastapi_app/routes/watch_todo_async.py` | 修改 | close 透传结构化规则变更 |
| `adapters/outbound/repositories/watch_todo_repository.py` | 修改 | 证据读写、未收敛查询、统计聚合 |
| `infrastructure/persistence/orm/models/watch_todo.py` | 修改 | 待办表映射新增可空 evidence |
| `infrastructure/persistence/migrations/20261021_watch_todos_evidence.py` | 新建 | 加列 + 部分索引，可回滚 |
| `adapters/inbound/fastapi_app/watch_bootstrap.py` | 不改 | 宿主契约不变（装配仍在 factory） |

### 依赖方向  serves: FR-1, FR-3

- 交易包只依赖「端口」，不知道盯盘实现；盯盘已声明依赖交易包，实现监听接口，方向不变。
- 消息桥在盯盘包内，依赖既有待办服务与 owner 路由，不新增跨包依赖。
- 宿主路由只调应用服务，不直接碰 ORM。

### 外部依赖与降级  serves: FR-1, FR-3

- 成交监听未注册 = 旧行为（成交照常落库，只是不回写）。
- 消息桥未注入 = 消息只发卡（与现状一致）。
- 规则联动未装配 = close 只收敛待办（与现状一致）。

## 数据模型  serves: FR-3

- 仅改一张表：`quant.watch_todos` 新增可空 `evidence jsonb`（消息摘要、命中词、来源、告警 id），用于消息待办的可追溯；其余表不动。
- 新增部分索引：`(symbol, action_kind) WHERE terminal IS NULL`，服务消息去重查询。
- 详细字段、约束、迁移与回滚见 `design/data-model.md`。

## 接口设计  serves: FR-1, FR-3, FR-5, FR-6, FR-7

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | 成交回调端口 `IFillListener.on_fill` | FillEvent（账户/标的/买卖/数量/价格/成交号/时间/来源） | 任意（实现方结构化结果，调用方不消费） | 实现不得抛错；调用方兜底，失败只记日志 | 新增端口，旧引擎导出保持转发 |
| IF-3 | `POST /api/watch/todos/{id}/close` | 既有字段 + additive `rule_change` | `{todo, receipt, rule_change}` | 400 非法终态/缺 NEXT；404 不存在；409 已收敛；422 动作非法 | 不传 `rule_change` 时行为与现状逐字一致 |
| IF-4 | `GET /api/watch/exec/stats` | `since` / `until`（可选） | 三态计数 + p50/p95 时延 | 400 时间非法；500 聚合失败 | 新增只读端点，不影响旧端点 |

#### IF-1 成交回调端口  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

交易服务在成交**落库之后**调用 `notify_fill(event)`；端口把事件同步分发给已注册的唯一监听者（当前为盯盘收敛器）。事件是事实投影，不含任何下单意图；监听者失败不得影响已提交的成交。

**错误码**

无返回码。实现方必须自吞异常并记日志；`notify_fill` 外再包一层 try/except，失败只记 `fill_listener_error`。交易调用方不因回调失败回滚或重试成交。

**兼容性**

端口新增在交易包内；`application/trading/paper_trading_engine.py` 继续导出同名符号，旧 import 不破。未注册监听者时为一行的空操作。

**幂等与重试**

同一 `trade_id` 重复投递必须只收敛一次；实现方按待办终态与成交号去重，时延只写一次，不设自动重试。

#### IF-3 待办关闭（扩展）  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

在既有收敛语义上增加可选结构化规则变更：`{change_kind: adjust_threshold|postpone|disable|retire, params, reason}`。只在 `terminal=ignored` 且带 `rule_change` 时触发规则联动，写规则与审计同一事务；缺 `trigger_id` 的联动请求拒绝。

**错误码**

`400` 终态非法或缺 NEXT；`404` 待办不存在；`409` 已收敛；`422` 动作项非法（未知 change_kind / 缺 params / 缺 reason）；联动失败整体回滚，返回 `422` 与可读原因。

**兼容性**

`rule_change` 为可空 additive 字段；旧调用方不传即完全旧行为。审计表沿用既有 `watch_rule_changes`（已有 `trigger_id` 列），不加列。

#### IF-4 执行闭环统计  serves: FR-1, FR-3, FR-5, FR-6, FR-7

**语义**

只读聚合：按终态与执行动作统计待办数量，并按触发证据里的执行时延计算 p50/p95。治理类待办（规则重叠、元复核）不计入分母；空数据返回 0。

**错误码**

`400` 时间窗非法（结束早于开始 / 无法解析）；`500` 聚合异常（返回结构化错误，不返回半份数字）。

**兼容性**

新增端点，无版本变更；字段名一次定死，后续只增不改。

## 备选方案  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| 什么都不做 | 保持现状，靠人看群消息与日频对账 | 零改动 | 待办永远悬空、统计失真 | 资损口径错误不可接受 |
| 盯盘轮询持仓表判断成交 | 不起事件，靠每拍对比持仓变化 | 不动交易包 | 无法区分买卖来源，时延以分钟计，重复卖会误判 | 收敛不及时且不可溯源 |
| 交易服务直接 HTTP 调盯盘 | 成交后同步调盯盘接口 | 链路直观 | 引入服务间网络依赖与失败重试，交易被盯盘可用性绑架 | 违反依赖方向与降级原则 |

## 四风险与证据  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 没有回写时，待办是否真的悬空？ | 生产 `watch_triggers.detail` 含执行明细 0 行；P0 待办仍 open；3 天后被 expired | 价值成立 |
| 可用性 | 回调会不会拖慢或打断成交？ | 成交落库与回调分离；既有端口契约要求自吞异常 | 可控，需压测与异常注入 |
| 可行性 | 既有端口与收敛器能否直接复用？ | 收敛器已实现买卖两向、幂等与时延落账；单测 221 例绿 | 可行 |
| 商业可行性 | 维护成本是否可接受？ | 全部为附加能力，开关关闭即回旧行为 | 可接受 |

## 失败模式与回滚  serves: FR-1, FR-3, FR-6

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 成交回调抛错 | 监听实现缺陷/DB 异常 | 成交已落库，待办未收敛 | 日志 `fill_sync_error` + 回写结果计数 | 注销监听（一行配置）恢复旧行为 | 值班 |
| 消息桥建单失败 | 待办库不可用 | 消息只发卡，无待办 | 扫描结果 `errors` 计数与日志 | 桥置空即回旧行为 | 值班 |
| 规则联动写审计失败 | 审计表异常 | 待办不收敛，返回 422 | 接口错误码 + 事务回滚日志 | 去掉 `rule_change` 字段即旧行为 | 值班 |
| 超时误报 | 时间基准不一致 | 重复催办骚扰 | 回执计数与 overdue 读数 | 关闭执行期限巡检开关 | 值班 |

## 跨关注点  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增对外写能力 | 成交端口仅进程内调用；统计端点只读 |
| 性能 | 回写对成交主链路的额外耗时 P95 < 50ms | 事件同步分发、无网络、单表更新；压测断言 |
| 可观测 | 三类事件都有结构化日志与计数 | 日志字段固定（trade_id/todo_id/rule_id/status） |
| 兼容 | 不破坏既有接口与表语义 | 新字段可空、新端点新增、开关关闭即旧行为 |
| 依赖方向 | 交易→端口←盯盘，无环 | import-linter 校验；盯盘不反向依赖宿主 |

## 交付拆分与里程碑  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 成交回写 | 端口 + execute_trade 发包 + 收敛验证 | 端到端用例绿；生产 exec 明细 ≥1 行 | agent | 2026-10-22 |
| M2 消息投递 | 消息桥 + 盘后窗口 + 去重 | critical 建待办/soft 不建用例绿 | agent | 2026-10-22 |
| M3 待办闭环 | 规则联动 + 超时修正 + 统计 | 三态 e2e 与统计对账绿 | agent | 2026-10-23 |

## 需求追溯  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | 方案总览 / IF-1 | 成交清仓→待办 handled | 收敛率 100% |
| FR-2 | 架构与依赖 | 买入→状态持有 | 状态一致率 100% |
| FR-3 | IF-3 / 数据模型 | critical→待办+唤醒 | 待办创建数 1 |
| FR-4 | 架构与依赖（sidecar） | 16:30 扫描执行 | 盘后扫描轮次 ≥1 |
| FR-5 | IF-3 | 不执行→规则+审计 | 审计行数 1 |
| FR-6 | 失败模式与回滚 | 期限前后/时区矩阵 | 误报数 0 |
| FR-7 | IF-4 | 统计与台账对账 | 计数差 0 |
| FR-8 | 架构与依赖 | 补挂→可求值 | 被跳过数 0 |

## 常见问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 回答 |
|---|---|
| 为什么不直接让盯盘查持仓表？ | 轮询无法区分来源且时延以分钟计，做不到「成交即可见」，也无法把时延写进证据。 |
| 成交回调会不会影响下单？ | 不会。回调在成交落库之后同步执行，异常被两层兜住；最坏情况只是没回写。 |
| 为什么消息待办只对 critical？ | 用户裁定 D-3：soft 量大，建待办会淹没队列，soft 维持发卡。 |
| 盘后扫描会不会抢其它任务资源？ | 只把消息扫描与收盘日报移到盘后段，其余日频任务节奏不变。 |
| 超时为什么不再写 expired？ | 未执行不是「已处置」；写 expired 会让统计把未执行止损算成已收敛。 |
| 统计口径为什么排除治理类待办？ | 规则重叠/元复核不是执行动作，计入分母会拉低执行率、掩盖真实问题。 |
| 这套改动能单独回滚吗？ | 能。三条接缝各有开关或空实现，关闭即与现状逐字一致。 |

## 开放问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 消息待办去重窗口取多长 | 同一交易日 / 4 小时 | agent（实施时定） | 2026-10-22 |
| 执行统计是否包含历史回填 | 只统计上线后 / 回填 30 天 | agent（实施时定） | 2026-10-22 |

## 附录  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 需求：`docs/requirements/REQ-261021194640-69b8/requirement.md`
- 设计口径来源：`docs/rfcs/017-watch-execution-loop-position-state-per-rule-interval.md`
- 相关文档：`docs/guides/watch-pipeline-stages.md`、`packages/qs_watch/CLAUDE.md`
- 章节职责：本文只讲架构与文件结构；字段与迁移见 `design/data-model.md`；契约明细见 `design/interfaces.md`。
