---
title: 盯盘执行闭环三接缝 · 接口设计（REQ-261021194640-69b8）
status: draft
owner: agent（本窗口）
reviewers: 投资人
prd: docs/requirements/REQ-261021194640-69b8/requirement.md
serves: FR-1, FR-3, FR-5, FR-6, FR-7
created: 2026-10-21
updated: 2026-10-21
---

# 盯盘执行闭环三接缝 · 接口设计  serves: FR-1, FR-3, FR-5, FR-6, FR-7

## 摘要  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- **问题**：三条接缝缺的是「可被机器消费的契约」：成交事实怎么交、消息怎么变待办、不执行怎么变规则、统计怎么读。
- **方案**：一个进程内成交通知端口 + 两个 HTTP 接口扩展 + 一个内部消息桥 + 一条只读统计端点；全部 additive，不破坏旧调用。
- **影响面**：交易包、盯盘包、宿主路由各一处；外部调用方只有 agent（close 时可带结构化动作）。

## 背景与问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 需求来源  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 卖出成交要回写 | IF-1/IF-2：成交落库后同步发事件 |
| FR-3 | critical 消息要变待办 | IF-5：消息桥把命中转成 P1 待办并唤醒 |
| FR-5 | 不执行要改规则 | IF-3：close 增加结构化 `rule_change` |
| FR-6 | 超时要收敛 | IF-3/IF-4 之外由 SLA 巡检消费期限字段 |
| FR-7 | 统计可读 | IF-4：只读聚合端点 |

### 现状与代价  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

现状没有成交通知契约：唯一监听点在模拟撮合引擎，真实成交写点零通知。close 接口只有自由文本，规则联动拿不到可执行动作。执行统计端点不存在，只能用触发统计近似。

### 为什么是现在  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

接口是设计与实施的分界：契约定不死，拆分阶段无法估工作量，实施会各写一套。

## 目标与非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

### 目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 成交事件字段固定、幂等键明确、失败语义明确（不影响成交）。
- close 与 stats 的字段一次定死，后续只增不改。
- 所有新字段可空或新增端点，旧调用方零改动。

### 非目标  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 不新增交易下单接口（D-1）。
- 不把消息桥开放成外部 HTTP 接口：它是进程内方法。
- 不做分页/批量查询：统计端点只返回聚合值。

## 方案总览  serves: FR-1, FR-3, FR-5, FR-7

```text
AccountTradingService ──notify_fill(FillEvent)──▶ 进程内注册表 ──▶ FillSyncService
NewsWatchService/PolicyWatchService ──dispatch(alerts)──▶ NewsTodoBridge ──▶ TodoService
agent ──POST close{rule_change}──▶ TodoService ──▶ RuleChangeLinkage
人/agent ──GET exec/stats──▶ 聚合查询 ──▶ 三态计数 + 时延分位
```

**关键概念**：`FillEvent` 是成交事实；`rule_change` 是结构化处置动作；`evidence` 是消息待办的追溯证据。

## 架构与依赖  serves: FR-1, FR-3

- **端口位置**：`packages/qs_trading/qs_trading/application/ports/fill_listener.py`——交易包自有，不依赖盯盘。
- **依赖方向**：盯盘实现端口；交易包只认协议。宿主路由只调服务。
- **降级**：未注册监听者 = 空操作；消息桥未注入 = 只发卡；`rule_change` 不传 = 旧行为。

## 数据模型  serves: FR-3

- `watch_todos.evidence jsonb NULL`：消息待办的证据（来源、标题、命中词、告警 id）。
- 部分索引 `(symbol, action_kind) WHERE terminal IS NULL`：消息去重查询。
- 其余为既有表复用：`watch_rule_changes`（审计）、`watch_receipts`（超时回执）、`watch_triggers.detail.exec`（时延）。
- 字段与迁移细节见 `design/data-model.md`。

## 接口设计  serves: FR-1, FR-3, FR-5, FR-7

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `IFillListener.on_fill(event)` 进程内协议 | FillEvent | 任意结构化结果（调用方不消费） | 实现不得抛错 | 新增协议 |
| IF-2 | `notify_fill(event)` 进程内函数 | FillEvent | `bool`（是否有监听者消费） | 永不抛错，内部记日志 | 新增函数 |
| IF-3 | `POST /api/watch/todos/{todo_id}/close` | 既有字段 + 可选 `rule_change` | `{success, data:{todo, receipt, rule_change}}` | 400/404/409/422 | additive |
| IF-4 | `GET /api/watch/exec/stats` | `since`/`until` | 三态计数 + p50/p95 | 400/500 | 新增端点 |
| IF-5 | `NewsTodoBridge.dispatch(alerts)` 进程内方法 | 告警列表 | `{created, skipped, errors}` | 永不抛错 | 新增方法 |

## 接口清单  serves: FR-1, FR-3, FR-5, FR-7

| 接口 id | 名称 | 类型 | 调用方 | 实现落点 |
|---|---|---|---|---|
| IF-1 | 成交回调协议 | 进程内端口 | 交易服务 | `qs_trading/application/ports/fill_listener.py` |
| IF-2 | 成交通知函数 | 进程内函数 | 交易服务 | 同上 |
| IF-3 | 待办关闭（扩展） | HTTP POST | agent | `routes/watch_todo_async.py` |
| IF-4 | 执行闭环统计 | HTTP GET | 人/agent | `routes/watch_async.py` |
| IF-5 | 消息→待办桥 | 进程内方法 | 消息扫描服务 | `qs_watch/.../news_todo_bridge.py` |
| IF-6 | sidecar 盘中/盘后分段 | 内部调度边界 | 引擎自身 | `qs_watch/.../watch_engine/engine.py` |
| IF-7 | 待办证据数据契约 | 数据列 | 消息桥写 / 读接口读 | `quant.watch_todos.evidence` |
| IF-8 | 迁移脚本 CLI | 命令行 | 运维 | `infrastructure/persistence/migrations/20261021_watch_todos_evidence.py` |

> 编号口径：IF-6 的判定语义见 `design/test-cases.md`，IF-7 / IF-8 的字段与迁移细则见 `design/data-model.md`；本文件只定义跨模块契约（IF-1～IF-5）。

#### IF-1 成交回调协议  serves: FR-1, FR-3, FR-5, FR-7

**语义**

定义一条成交事实的结构与消费方式：交易服务在成交落库后把事件交给已注册的监听者。事件只描述事实（账户、标的、方向、数量、价格、成交号、时间、来源、决策审计号），不含下单意图。监听者实现收敛动作，不产生新订单。

**错误码**

无错误码。实现方必须自吞异常；违反契约（抛错）由调用方兜住并记 `fill_listener_error`。调用方不因回调失败改变成交结果。

**兼容性**

新增协议，旧代码无引用。`application/trading/paper_trading_engine.py` 继续导出同名符号（转发），旧 import 路径不破。

**幂等与重试**

调用方不重试。实现方按 `trade_id` 幂等：重复事件不二次收敛、不二次写时延。

#### IF-2 成交通知函数  serves: FR-1, FR-3, FR-5, FR-7

**语义**

进程内唯一出口：读取模块级注册表，存在监听者则同步调用一次，返回是否被消费。注册/注销各一个函数；注册时只做结构校验（有 `on_fill`），不 import 实现方。

**错误码**

函数本身不抛错。监听者异常被捕获并记日志，返回 `False`。未注册返回 `False`，不告警。

**兼容性**

新增函数。原模拟撮合引擎的 `_notify_fill` 改为调用它，外部行为不变。

#### IF-3 待办关闭（扩展）  serves: FR-1, FR-3, FR-5, FR-7

**语义**

在既有 close 语义上增加可选 `rule_change`：

- `change_kind`：`adjust_threshold` / `postpone` / `disable` / `retire`
- `params`：调阈值 `{price, direction}`；延期 `{days}`
- `reason`：必填，进审计

仅当 `terminal=ignored` 且带 `rule_change` 时触发规则联动：更新规则字段 + 写一条 `watch_rule_changes`（含 `trigger_id`、`todo_id`、`decision_audit_id`），两者同一事务。缺 `trigger_id` 的联动请求在写任何东西之前拒绝。

**错误码**

| 情形 | 码 | 调用方处理 |
|---|---|---|
| 终态非法 / ignored 缺 next_condition | 400 | 修正入参 |
| 待办不存在 | 404 | 放弃 |
| 待办已收敛 | 409 | 不重试，读终态 |
| 动作项非法（未知 change_kind / 缺 params / 缺 reason / 缺 trigger_id） | 422 | 修正或去掉 `rule_change` |
| 联动写库失败 | 422 + 原因 | 事务已回滚，可重试一次 |

**兼容性**

`rule_change` 可空；不传时与现状逐字一致。响应新增 `data.rule_change`（null 或结果），旧消费方忽略即兼容。

#### IF-4 执行闭环统计  serves: FR-1, FR-3, FR-5, FR-7

**语义**

只读聚合，服务于复盘与验收：

- `executed`：终态 handled 且 action_kind 属执行类
- `declined`：终态 ignored 且带结构化动作
- `unresolved`：未收敛且属执行类
- `timeout`：已发超时回执的执行类待办数
- `latency_p50` / `latency_p95`：触发证据 `detail.exec.latency_sec` 分位（单位秒）

治理类（规则重叠、元复核）不计入分母；空数据返回 0。

**错误码**

| 情形 | 码 | 调用方处理 |
|---|---|---|
| 时间窗无法解析或结束早于开始 | 400 | 修正入参 |
| 聚合查询异常 | 500 | 稍后重试，不返回半份数字 |

**兼容性**

新增端点，无版本变更。字段名一次定死，后续只增不改。

#### IF-5 消息→待办桥  serves: FR-1, FR-3, FR-5, FR-7

**语义**

输入一批已分级的消息命中（账户、标的、级别、标题、命中词、告警 id、来源）。仅 `tier=critical` 建 P1 待办：`action_kind=rule_change`、`evidence` 写证据、按账户路由 owner 并唤醒；`soft` 跳过。同一 `(symbol, action_kind)` 已有未收敛待办时不重复建（或窗口内不重复）。

**错误码**

方法不抛错，返回 `{created: [todo_id], skipped: [...], errors: [...]}`。单条失败不影响整轮扫描；扫描任务据 `errors` 计数告警。

**兼容性**

新增方法。消息服务未注入桥时行为与现状一致（只发卡）。

## 备选方案  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| 什么都不做 | 保持现状 | 零改动 | 三条接缝继续断 | 统计与保护失真不可接受 |
| 成交事件走消息队列 | 引入 MQ 异步解耦 | 削峰、可重放 | 新基础设施与运维成本 | 单进程内一条同步回调足够，YAGNI |
| close 用自由文本让 agent 描述动作 | 不改接口 | 零契约成本 | 机器无法执行，联动写不出来 | 正是现状的问题 |

## 四风险与证据  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 契约补齐能否让闭环真正收敛？ | 收敛器已实现且 221 例绿，缺的只是事件源 | 成立 |
| 可用性 | 新字段/新端点会不会让旧调用方出错？ | 全部 additive、可空、忽略即兼容 | 低风险 |
| 可行性 | 字段能否从现有写点直接拿到？ | 成交写点已持有账户/标的/数量/价格/成交号 | 可行 |
| 商业可行性 | 维护面是否可控？ | 5 个接口面，均在既有模块内 | 可控 |

## 失败模式与回滚  serves: FR-1, FR-3, FR-5

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 监听实现抛错 | 代码缺陷 | 成交正常，待办未收敛 | 日志 + 回写结果计数 | 注销监听 | 值班 |
| 消息桥单条建单失败 | 待办库异常 | 该条消息无待办 | `errors` 计数 | 桥置空 | 值班 |
| close 联动失败 | 规则/审计写失败 | 返回 422，待办未收敛 | 错误码 + 回滚日志 | 去掉 `rule_change` | 值班 |
| 统计查询超时 | 数据量大/缺索引 | 端点 500 | 接口监控 | 加时间窗限制或下线端点 | 值班 |

## 跨关注点  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增外部写接口 | close 仍走既有鉴权与审计；stats 只读 |
| 性能 | 回调同步开销 < 50ms | 单表更新 + 单条审计；无网络调用 |
| 可观测 | 每次调用有结构化结果 | 返回 `{status, errors}`，日志带 trade_id/todo_id |
| 兼容 | additive 优先 | 新字段可空、新端点新增、旧响应字段不变 |

## 交付拆分与里程碑  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 成交契约 | IF-1/IF-2 + 真实成交发事件 | 端到端用例绿 | agent | 2026-10-22 |
| M2 close 扩展 | IF-3 + 规则联动 | 关闭后规则变、审计 1 条 | agent | 2026-10-22 |
| M3 统计端点 | IF-4 + 聚合查询 | 计数与台账一致 | agent | 2026-10-23 |

## 需求追溯  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | IF-1/IF-2 | 卖出成交→收敛 | 收敛率 100% |
| FR-3 | IF-5 | critical→待办 1 条 | 待办创建数 |
| FR-5 | IF-3 | ignored+rule_change→审计 1 条 | 审计行数 |
| FR-6 | IF-3/SLA | 期限前后用例 | 误报数 0 |
| FR-7 | IF-4 | 统计对账 | 计数差 0 |

## 常见问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 回答 |
|---|---|
| 为什么不用 webhook 而用进程内函数？ | 交易与盯盘在同一个 5001 进程，进程内同步调用没有网络失败与重试语义，最简单。 |
| 事件里为什么带 decision_audit_id？ | 有则写进审计做血缘，没有则退化用成交号并标注降级，不虚报。 |
| close 的 rule_change 与既有 action_kind 什么关系？ | `action_kind` 仍是粗分类（trade/rule_change），`rule_change` 是具体动作项。 |
| 统计为什么不用新表？ | 台账已在 watch_todos 与 triggers.detail，聚合即可，避免第二套事实源。 |
| 消息桥为什么只建 P1？ | 用户裁定 D-3；P1 直达 L3，能进 SLA 与唤醒链路。 |
| 旧调用方不传 rule_change 会怎样？ | 完全旧行为：只收敛待办、发回执、不写审计。 |

## 开放问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| close 的 rule_change 是否要支持批量动作 | 单动作 / 数组 | agent（实施时定） | 2026-10-22 |
| stats 是否按级别分组 | 只总量 / 加 by_level | agent（实施时定） | 2026-10-23 |

## 附录  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8

- 架构与文件结构：`design/architecture.md`
- 字段与迁移：`design/data-model.md`
- 需求：`docs/requirements/REQ-261021194640-69b8/requirement.md`
