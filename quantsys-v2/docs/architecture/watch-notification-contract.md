---
id: watch-notification-contract
title: 盯盘通知契约（开市闸门 / 名称 / 级别 / 外发审计）
summary: 盯盘通知的四条硬契约：非交易日零事件、名称不得回落成代码、意图与处置级别恒有且闭环承诺按开关、每次外发可归因到发送方。
type: architecture
status: living
updated: 2026-10-07
owners: [w-c7b5b1ee]
tags: [watch, notification, audit, trading-day, reqboard]
---

# 盯盘通知契约（开市闸门 / 名称 / 级别 / 外发审计）

**来源**：`REQ-261007101318-c392`（2026-10-07）。起因是一张卡：
「盯盘触发 - 688525 / 现价 192.35 ≤ 阈值 218.24（下破）」——用户连问三件事
（这不是股票名称 / 这让我买还是卖、还是交给 agent / 今天没开市）。三问对应三条契约，
取证过程中又发现第四条（外发不可溯源）。

**一句话**：盯盘通知**只有在其口径成立时才发**，发出来必须能自证「谁发的、什么规则、什么意图、该谁处置」。

## 1. 开市闸门：非交易日零事件（判据唯一入口）

- `WatchEngine.tick()` 与 `run_forever()` **共用** `WatchEngine._resolve_trading_day(day)`
  → 默认 `application/services/trading_day_guard.TradingDayGuard.check`（含法定节假日 + `quant.trading_calendar`）；
- 非交易日或非交易时段：**不取规则、不评估、不落库、不外发**，只按「日 + 原因」去重留一条
  `盯盘 tick 跳过（未开市）`（此前是静默 `return []`，导致"今天没开市"与"引擎没跑"不可区分）；
- 判定异常（注入方抛错 / 判定器异常）**一律保守判非交易日**（`injected-error` / `compute-error`）。

**为什么闸门必须在 `tick()` 里**：任何旁路调用（补跑脚本 / 新服务 / 其他窗口）都绕过 `run_forever`；
把门留在循环层 = 只护住一条路径。历史事故：`tick()` 只判 `weekday()`，国庆休市期间照常判定并推送。

单测冻结时钟（不依赖真实日期）：
`pytest tests/services/test_watch_engine_trading_day_gate.py -q`（含 `run_forever` 整环与留痕去重）。

## 2. 名称：缺失就写「名称缺失」，绝不回落成代码

- 解析链：行情 `name` → `quant.stocks`（**端口实现** `PgStockNameResolver.resolve_batch`，与 SLA 回执同一份）
  → 仍无则传 `None`；
- 渲染层对 `None` 输出 `{代码}（名称缺失）`；**禁止** `name or symbol` 这类混同
  （旧写法让"查不到名称"看起来像"这只标的就叫 688525"）。

## 3. 意图与处置级别恒有；闭环承诺按开关

| 概念 | 含义 | 由谁决定 |
|---|---|---|
| 意图（`intent`） | 这条提醒为了什么：`entry`=买入跟踪 / `exit_stop`=止损盯盘 / `trend_observe`=趋势观察… | **规则**决定，卡面如实呈现，系统不猜 |
| 处置级别（`trigger_level`） | `L0` 纯信息 / `L1` 提醒（不唤醒 agent）/ `L2` 行动（需 agent 介入） | 规则 `action_hint` |
| 展示级别（`P0..P3`） | 卡片颜色 / 是否 @ / 是否可静默 | `domain/watch/services/level_resolver.py` 纯函数 |
| 闭环承诺 | 「处置入口 / 回执位 / 不可静默 / 待办#」 | `closed_loop`（= 闭环开关是否开） |

**铁律：级别与闭环解耦。** 旧实现 `_notify_level()` 在 `todo_service is None`（闭环未开）时直接
返回 `None` → **所有**盯盘卡退回旧渲染，只剩一句「现价 X ≤ 阈值 Y（下破）」——用户无法判断该买该卖。
现在级别**恒解析**（供渲染），闭环承诺由 `closed_loop` 单独门控：**闭环没开就不承诺**，
不给用户指向不存在的待办看板的入口。

## 4. 外发审计：每次外发可归因到发送方

**为什么需要**：v2 与 agent-ts 的 `FEISHU_WEBHOOK` **完全相同**（同一机器人/群），
且盯盘卡不带署名 ⇒ 飞书上无法区分发送方。取证时本机 v2 在保留日志窗口内**零条** `watch_triggered` 外发，
而 `NotificationService(repository=None)` ⇒ **外发零持久化**，导致"谁在几点发了什么"**无处可查**。

- 落点：`domain/notification/services/notification_service.py` 的 `send` / `send_with_fallback`
  三处 save 点（**覆盖所有调用方**：引擎 / 脚本 / 异地实例 / 手工调用）；
- 台账：`quant.notification_audit`（**一通知一行**，按 `notification_id` upsert；正文只留 sha1 + 前 500 字）；
- 来源标识：`application/notification/sender_identity.py` → `v2-watch@<host>#<pid>`
  （跨机靠 host 段、跨进程靠 pid 段），同时写进卡面尾注与 `metadata.sender_id`；
- 迁移：`infrastructure/persistence/migrations/20261007_notification_audit_table.py`（幂等 + `lock_timeout`，**两库都跑**）；
- 失败纪律：审计写失败**自吞并留痕**，绝不打挂通知（审计是增益，不是可用性前提）。

**被审计覆盖 / 不覆盖**：

```sql
-- 谁在几点、为哪条规则、发了什么标题
select occurred_at, notification_type, title, delivery_channel, delivered, sender_id
  from quant.notification_audit order by occurred_at desc limit 20;
```

- 覆盖：所有经 `NotificationService` 的外发；
- **不覆盖**：绕过通知栈、直接 POST 飞书 webhook 的发送方（只能靠卡面尾注缺失间接识别）——
  这是**能力上限**，不是遗漏。

## 5. 卡面内容契约（分级路径与旧路径同口径）

标题 `盯盘触发 - {名称}（{代码}）`；正文固定顺序：

```
`🔔 需决策`
**{意图标签}｜{名称}（{代码}）**
阶段：… · 归属：… · 规则#…
**触发**：现价 192.35 ≤ 阈值 218.24（下破）
**当前**：¥192.35
**这条提醒为了**：{intent 驱动的目的句}
**预案**：{rule.context}
**处置**：L1 提醒（人工判断，不唤醒 agent）
**下一步**：{next_action_hint 或 intent 映射}
—— v2-watch@<host>#<pid>
```

- 级别未知 → **隐藏**「**处置**：」行（不臆造）；
- 无 `sender_id` → 不渲染尾注（兼容旧调用方）。

## 6. 「何时叫 agent」判据表（REQ-261007133807-eda6；与代码码表**同源**）

判据的**唯一事实源**是 `domain/watch/services/escalation_verdict.py` 的 `EscalationCode`
与 `decide_escalation`（顺序表见 `docs/requirements/REQ-261007133807-eda6/design/architecture.md`）。
本表由 `tests/services/test_watch_contract_parity.py` 与代码码表机械对拍——**改一处必须改另一处**。

| 理由码 | 语义 | 是否叫 agent | 来源（收敛前等价点） |
|---|---|---|---|
| `CONSTITUTIONAL_INTENT` | 宪法级意图（`exit_stop` 止损铁律） | ✅ | `disposition.decide` 规则 0 |
| `BUDGET_EXHAUSTED` | 当日介入预算已耗尽 | ❌ | `decide` 规则 1 |
| `RULE_EXPLICIT_ESCALATE` | 规则显式声明 `action_hint.escalate=true` | ✅ | `EscalationChecker` 路径 1 |
| `ANOMALY_CHANGE_PCT` | 异常波动达阈值（缺省 5.0%，可被规则覆写） | ✅ | `EscalationChecker` 路径 3 |
| `RULE_LEVEL_L2` | 规则分级 L2（买卖节点需拍板） | ✅ | `decide` 规则 3 |
| `META_REVIEW` | 元触发过轻门（进复核队列） | ✅ | `decide` 规则 4 |
| `OBSERVE_INTENT` | 观察类（意图门） | ❌ | `decide` 规则 5① |
| `AMOUNT_BELOW_THRESHOLD` | 金额门未过 | ❌ | `decide` 规则 5② |
| `SAME_TOPIC_COOLDOWN` | 增量门（同标的同议题 4h 内已介入） | ❌ | `decide` 规则 5③ |
| `ECONOMIC_BELOW_K` | 经济门未过 | ❌ | `decide` 规则 5⑤ |
| `GATES_PASSED_ACTION` | 价格触发过五道门且声明买卖动作 | ✅ | `decide` 规则 5 尾 |
| `PENDING_NO_ACTION` | 过门但未声明动作（待处置） | ❌ | `decide` 规则 5 尾 |
| `DEDUPED` | 去重合并（**裁决之后覆盖**） | ❌ | `engine` 去重分支 |
| `SUPPRESSED` | 抑噪期归档（**裁决之后覆盖**） | ❌ | `engine` 抑噪短路 |
| `UNKNOWN` | 未接入裁决（**禁止臆造理由**） | ❌ | 新增 |

落库位置：`quant.watch_triggers.escalation_code` / `escalation_reason`（迁移 `20261007`）。
"没叫"也要有码是刻意的——只记录"叫"的理由等于把成本控制留成黑盒。

## 7. 已知瑕疵与后续

- `sender_id` 的 host 段在不同进程可能给 mDNS 名或 IP（跨机分辨不受影响；同机按 host 聚合会分裂）；
- `risk_stop` 渠道未注册（L1 卡每次先试 agent 通道失败再降级飞书，白跑一次往返）→ 用户裁定不修（D-11）；
- 「何时叫 agent」的判据收敛已由 `REQ-261007133807-eda6` 落地（见 §6）：单一裁决出口 + 理由码落库 + 卡面可读 + 规则侧显式。
