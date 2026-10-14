# 用例与场景设计（REQ-261007101318-c392）（serves: FR-1, FR-2, FR-3, FR-4）

以"用户拿到一张卡之后会怎么想"为线索，逐场景给出**应当发生什么**与**怎么验**。
（场景 1 是本次真实发生的事故；场景 4 是本次取证的起点，也是最容易被忽略的一条。）

## UC-1 · 休市日被"提醒"（serves: FR-1）—— 本次事故原型

**情境**：2026-10-07（周三·国庆休市）10:03，用户收到飞书卡
「盯盘触发 - 688525 / 现价 192.35 ≤ 阈值 218.24（下破）」。

**应当发生**：休市日**零触发、零外发**；跳过必须留痕（`day / is_trading_day / in_session / trading_day_source`），
使"今天没开市"与"引擎没跑"可区分。

**怎么验**：
- 单测：`pytest tests/services/test_watch_engine_trading_day_gate.py -q`（冻结 2026-10-07 + 注入 `False`）；
- 线上：`quant.trading_calendar` 无 `2026-10-01~10-07`；日志应出现跳过留痕而非触发记录。

**现状（如实）**：FR-1 的闸门已实现并在 2026-10-07 12:50 随服务重启生效；
**但本次这张卡并非本机引擎所发**（`watch_rules` / `watch_triggers` / 保留日志均无记录），
故 UC-1 修的是"本机不再误推"，**不是**"这张卡被撤回"。

## UC-2 · 交易日真的跌穿了（serves: FR-2, FR-4）

**情境**：交易日盘中，688525 现价跌破规则阈值。

**应当发生**：一条**能自证**的卡——名称在前、意图明确、处置级别明确、下一步明确：

```
`🔔 需决策`
**🛑 止损盯盘｜佰维存储（688525）**
阶段：持仓中 · 归属：agent_brain · 手工
**触发**：现价 192.35 ≤ 阈值 218.24（下破）
**当前**：¥192.35
**这条提醒为了**：浮亏触及止损线 —— 宪法要求必须执行，不得延后
**处置**：L1 提醒（人工判断，不唤醒 agent）
**下一步**：评估清仓 / 下移止损线 218.24
—— v2-watch@<host>#<pid>
```

**怎么验**：`pytest tests/notification/test_req_c392_notification_contract.py -q`；
人工判读（已发一张真实卡给用户判读，2026-10-07）。

**注意**：意图由**规则**决定，系统不猜。同一句"下破"在 `entry`（进入买区）与 `exit_stop`（破止损线）
下必须产出**可区分**的正文（`test_entry_intent_reads_differently_from_stop_loss`）。

## UC-3 · 规则没标意图 / 名称查不到（serves: FR-2, FR-4）—— "不许编"

**情境**：规则 `intent` 为空；或 `quant.stocks` 查不到该标的名称。

**应当发生**：
- 意图缺失 → 卡面显式 `❓ 未标注意图`（无主规则=烂账，如实暴露），**不猜**；
- 名称缺失 → `{代码}（名称缺失）`，**不**把代码当名称、**不**臆造名称；
- `next_action_hint` 缺失 → 兜底「见触发条件」或 `INTENT_ACTION_HINT` 映射，**不留空**。

**怎么验**：契约用例 §2（`test_missing_name_degrades_explicitly_not_to_bare_symbol` 等）。

## UC-4 · 又收到一张"来路不明"的卡（serves: FR-3）—— 本次取证暴露的真需求

**情境**：用户收到一张盯盘卡，问"这是谁发的、为什么发"。

**应当发生**（两条独立手段）：
1. **卡面自证**：尾注 `—— v2-watch@<host>#<pid>`
   → 异地实例（不同 host）、本机别的进程（同 host 不同 pid）、手工 webhook（无尾注）**一眼可分**；
2. **台账可查**：一条 SQL 回答"谁在几点、为哪条规则、发了什么标题"：
   ```sql
   select occurred_at, notification_type, title, delivery_channel, delivered, sender_id
     from quant.notification_audit order by occurred_at desc limit 20;
   ```

**判定口径**：
- 有审计行且 `sender_id.host` = 本机 → 本机某进程所发（`pid` 段进一步定位）；
- 有审计行且 `host` ≠ 本机 → 异地实例所发；
- **无审计行** → 不是经 `NotificationService` 发的（手工 webhook / 绕过通知栈的调用）。

**怎么验**：`pytest tests/notification/test_notification_audit_repository.py -q`；
线上自检脚本（`/tmp/verify_audit_wiring.py`）实测输出：仓储 `NotificationAuditRepository`、写入 `True`、查回成功。

**已知边界（不许含糊）**：绕过通知栈、直接 POST 飞书 webhook 的发送方，审计**抓不到**——
只能靠卡面尾注缺失来间接识别。这不是遗漏，是本次范围内的能力上限，已登记在
`design/architecture.md`「不覆盖」一节。

## UC-5 · 闭环未开启时的措辞（serves: FR-4）

**情境**：`WATCH_TODO_ENABLED` 未开（本机现状）——没有待办看板、没有回执机制。

**应当发生**：卡片**照常**有意图/级别/下一步（用户知道该干什么），
但**不出现**「处置入口：打开待办看板」「处置后必有回执」「待办#」等承诺（指向不存在的东西）。

**怎么验**：`test_closed_loop_off_promises_nothing`（两态对比断言）。

## UC-6 · 审计库不可用 / 通知渠道抖动（serves: FR-3）

**情境**：审计表所在库不可用；或主渠道（agent）失败需降级飞书。

**应当发生**：
- 审计写失败 → error 留痕 + 返回 `False`，**通知照发**（绝不因审计把通知打挂）；
- 降级发送 → 审计记**最后出口渠道**（`feishu`）与 `delivered`、`fallback_cause`。

**怎么验**：`test_audit_failure_never_breaks_notification` +
`test_service_path_stamps_channel_and_delivered_into_audit`。

## UC-7 · 复市首日回执（serves: FR-1, FR-2, FR-3, FR-4）—— 时间型

**情境**：2026-10-08（节后首个交易日）。

**应当发生**：盯盘卡正常发出，且带名称、意图、处置级别、来源尾注；
审计表出现对应行（`notification_type='watch_triggered'`）。

**怎么验**：10-08 盘后跑 `design/test-cases.md` §5 的 SQL 与
`select ... from quant.watch_triggers where triggered_at::date='2026-10-08'`。
**在此之前不得宣称已交付**（时间型条件未到）。
