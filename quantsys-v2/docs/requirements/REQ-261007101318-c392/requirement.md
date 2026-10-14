# REQ-261007101318-c392 · 盯盘触发：休市日闸门缺失 + 通知缺股票名称

**需求ID**: REQ-261007101318-c392
**类型**: feature
**作用域**: `quantsys-v2/`（`application/services/watch_engine/{engine.py,notifier.py,conditions.py,dto.py}`、`application/notification/notification_facade.py`、`infrastructure/notification/`、`adapters/outbound/repositories/watch_rule_repository.py`、`infrastructure/persistence/migrations/`、`tests/`）
**侧**: backend（产物是飞书卡片文案 + 判定链路，无前端页面产出，不交原型）
**档位**: 重档（依据见文末「档位依据」；新增外发审计落库 + 改通知内容契约 + 触碰真实外发链路）

## TL;DR

**2026-10-07（周三·国庆休市）用户收到一张飞书卡：「盯盘触发 - 688525 / 现价 192.35 ≤ 阈值 218.24（下破）」，并连问三件事——「688525 不是股票名称」「这是让买让卖、还是交给 agent 处理」「今天没有开市」。**

三问每一问都指向一个真缺陷：

```
   一张盯盘卡暴露的三个洞（外加取证时才发现的第四个）
  +---------------------+  +---------------------+  +---------------------+
  | ① 卡面只有代码      |  | ② 只有"≤阈值（下破）"|  | ③ 休市日照样可判定  |
  | notifier.py:179     |  | 这句事实可反读：     |  | engine.py:322 的   |
  | name 回落 symbol    |  | 下破=买区 也可能      |  | tick 自检只判       |
  |                     |  | 下破=破止损线         |  | "周末+时段"         |
  +---------------------+  +---------------------+  +---------------------+
             \                        |                        /
              \                       v                       /
               +----------------------------------------------+
               | ④（取证中发现）外发不可溯源                    |
               | 卡不带署名、外发不落审计；v2 与 agent-ts 共用   |
               | 同一飞书机器人 ⇒ 事后无法回答"谁在几点发了什么" |
               +----------------------------------------------+
```

**本需求要做的**：把盯盘通知从"看起来像事实的一行字"变成**可自证的通知**——
该不该发（交易日闸门进 `tick`）、叫得对（名称兜底）、读得懂（意图 + 级别 + 下一步）、查得到（外发审计 + 来源标识）。

> ⚠️ 关于本次这张卡本身：**本机 v2 引擎已排除**（见 E6/E7/R4），发送方在本机范围内**不可钉死**。
> 因此 FR-3（外发可溯源）不是"顺手加的"，而是本次取证过程的直接产物——**没有它，下一次同样的问题还会重演一遍这次的全盘取证。**

## L1 一句话目标 + 可证伪判定标准

**目标**：盯盘通知只在其口径成立时发出（交易日 + 交易时段），发出来必须能自证"谁发的、什么规则、什么意图、该谁处置"，并且名称不再退化成一串代码。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. **休市日零事件（FR-1）**：冻结时钟在**节假日 2026-10-07 10:00** 调 `WatchEngine.tick()` → 返回 `[]`，
   且不产生 `watch_triggers` 行、不发生任何外发；同一时钟在交易日 `2026-09-30 10:00` → 正常判定。
2. **名称兜底（FR-2）**：规则 `symbol='688525.SH'`、行情无 `name` 时，卡面标题必须是
   `盯盘触发 - 佰维存储（688525）`；`quant.stocks` 查不到时才允许回落代码，且正文显式标注"名称未知"。
3. **文案含意图与级别（FR-4）**：卡面必须出现「意图：…」与「级别：L0/L1/L2」两段；
   `intent='entry'`（下破=进入买区）与 `intent='exit_stop'`（下破=破止损线）的卡片正文**不得同形**。
4. **外发可溯源（FR-3）**：任何一次盯盘触发外发后，能用**一条查询**回答"谁在几点、为哪条规则、发了什么标题"，
   且卡面自带来源标识；把发送方换成一个手工 webhook 调用时，该查询能区分出"不是引擎发的"。
5. **不破现状**：`pytest tests/services/test_watch_engine.py tests/services/test_watch_conditions.py tests/notification tests/application/test_watch_disposition_engine.py -q` 全过。
6. **真实观察（时间型）**：`2026-10-08`（复市首日）盯盘卡正常发出且带名称、意图、级别、来源标识。

## 边界

### 做什么

1. **`tick()` 补日级闸门（FR-1）**：把交易日判定收敛到**唯一入口** `TradingDayGuard.check(day)`
   （`application/services/trading_day_guard.py`，已含节假日口径），使 `tick()` 与 `run_forever()` 同口径；
   闸门设在 `tick()` 内部，护住所有旁路调用方（脚本 / 新服务 / 其他窗口），并在跳过时留结构化痕迹（`source` / `reason`）。
2. **名称兜底前置到 payload（FR-2）**：`_build_payload` 阶段就解析名称（行情 `name` → `quant.stocks` 兜底），
   禁止把 `symbol` 当名称下发；查不到时下发空并由渲染层显式写"名称未知"，不再静默退化。
3. **卡片内容契约（FR-4）**：正文必须包含**触发事实 + 规则意图 + 触发级别 + 下一步**四段；
   意图措辞由 `intent` 驱动（沿用 `INTENT_META` 既有 7 类），级别来自 `action_hint.trigger_level`（L0/L1/L2）；
   禁止只下发 `现价 X ≤ 阈值 Y（下破）` 这类可反读的单句。
4. **外发审计 + 来源标识（FR-3）**：每次盯盘外发落一条审计（时间 / 标的 / 规则号 / 级别 / 标题 / 正文摘要 /
   渠道 / 发送方标识 `kind+instance`(进程)/ 送达结果），并在卡面写出来源标识；
   审计须覆盖"引擎直发"与"其他代码路径调用同一通知链"两种情形——**这正是本次无法归因的地方**。
5. **可测**：以上四条各配可跑用例；休市日判据用**冻结时钟**，不依赖真实日期（见「判定标准」）。

### 不做什么

1. **不查办本次这张卡的发送方本身**（裁定 D-7）：本机取证已到边界（E6/E7/R4），
   继续追需要外部主机信息；本需求只保证**下一次能查得到**，不为历史这一次做无限取证。
2. **不改其它仓的飞书发送实现**：`agent-ts` 的 `FeishuNotificationService` 与 `agent-dh` 的
   `FeishuNotifyTool` / `NotificationSendTool` 已有署名机制，本需求不动它们；
   只要求 **v2 侧**外发可自证来源（并让"无来源标识的盯盘卡"在审计上可被判为可疑）。
3. **不合并/统一各仓的飞书机器人**（那是运维口径变更，涉及群与权限，需单独裁定）。
4. **不改交易日历数据本身**：闸门**依赖** `quant.trading_calendar` 正确，不由本需求刷新日历。
5. **不做规则治理（重叠规则 / 阈值失真 / 静默去重）**：属 `REQ-f08def` 系列既有范围。
6. **不做前端 / 看板页面**（side=backend，不交原型）：卡片是飞书 Markdown 文本，非本仓前端页面。
7. **不引入"自动下单/自动处置"**：盯盘引擎仍只做"判定 → 落库 → 通知"，绝不产生委托（既有铁律，不因本需求改变）。
8. **不定义「何时叫 agent」的判据**（裁定 D-10）：本需求只保证卡片**如实呈现**级别与意图；
   「什么条件下该唤醒 agent」属 `REQ-261007133807-eda6`《「何时叫 agent」判据收敛与可见化》的范围（已派给新窗口）。
9. **不修 `risk_stop` 渠道未注册**（裁定 D-11）：该现象成立（L1 卡先试 agent 通道被拒后才降级飞书，白跑一次往返），
   但用户裁定**不需要**修复、也不另立需求；本需求不碰渠道注册与路由。

### 边界理由

- **为什么闸门要进 `tick()` 而不是只留在 `run_forever()`**：`tick()` 的时段自检注释自己写明"任何旁路调用
  （补跑脚本/新服务/其他窗口）都会在盘后照样判定并推送"——但那次只补了"周末 + 时段"，**漏了节假日**；
  闸门只有落在被调函数层才对旁路有效（与 `REQ-261006190953-fc43` 的"门设在被调函数层"同一判据）。
- **为什么名称要在 payload 阶段解**：`notifier.py` 现在把 `name or symbol` 当名称下发，
  等于把"查不到名称"与"这条标的就是代码"混为一谈；渲染层再兜底已经分不清该显示什么。
- **为什么文案必须由 `intent` 驱动**：同一句"下破"在 `entry`（进入买区）与 `exit_stop`（破止损线）下**方向相反**，
  历史已有真实翻车记录（注释在 `infrastructure/notification/formatters/feishu_formatters.py:35-36`）。
- **为什么必须加外发审计**：本次用户能给的唯一判据是"发送者是谁"，而**同一机器人被 v2 与 agent 侧共用**，
  卡面又不带署名 ⇒ 结构上不可归因。补审计比"再查一次"更省，且是一次性投入。

## 产品定义

### 一句话

盯盘通知是一份**契约**而不是一句口号：只有口径成立时才发；发出来必须写清"它是谁、为哪条规则、什么意图、该谁处置"，并且事后查得到。

### 为什么现在做

休市日误推会污染触发台账与用户信任（用户 10-05、10-07 连续两次就盯盘推送发问）；
"只有代码没有名称""只有下破没有意图"让用户无法判断该不该动作（本次用户直接问"让卖让买"）；
外发不可溯源让每次异常都退化成一次全盘取证（本次已实测：整盘扫描 + 77 条外发逐条核对）。

### 成功长什么样

1. 休市日无论哪条路径调起判定，都**零触发、零外发**，且台账里能看到 `skipped` 与原因（不是静默）。
2. 卡片一眼可读：`盯盘触发 - 佰维存储（688525）` + 意图 + 级别 + 触发事实 + 下一步。
3. 任何一张盯盘卡都能回答"谁发的"；换一个非引擎来源发卡，审计上能识别为"非引擎"。
4. 判据全部可跑，不靠人盯、不靠真实日期。

## 用户与角色

| 角色 | 关心什么 | 本需求给他的东西 |
|---|---|---|
| 投资人（人） | 这张卡要不要动手 | 名称 + 意图 + 级别 + 下一步，不再只给一句可反读的"下破" |
| 投资脑（agent） | 触发是否可被信任、该不该处置 | 休市日不再有噪声触发；L2 才唤醒；卡面自带上下文 |
| 运维/排障者 | 复发时能否一眼定位发送方 | 外发审计一条查询 + 卡面来源标识 |
| 后续开发者 | 新调用方别再绕过闸门 | 闸门在被调函数层 + 休市日回归锁（冻结时钟） |

## 功能点（G2 条款）

- **FR-1: `WatchEngine.tick()` 的日级闸门收敛到 `TradingDayGuard`（休市日零事件）**
  `tick()` 内部必须以 `TradingDayGuard.check(now.date())` 为唯一日级判据（与 `run_forever()` 同口径），
  非交易日直接返回 `[]` 且**不产生任何触发记录与外发**；判定为降级（`degraded=True`）时按现有 fail-safe 语义处理
  并留结构化痕迹（`source` / `reason` / `degraded`）；禁止调用方各自写 `weekday()` 或第二条日历查询链。

- **FR-2: 触发通知必须带股票名称，禁止把代码当名称**
  名称解析前置到 `TriggerPayload` 构建阶段：优先取行情 `name`，缺则按裸代码查 `quant.stocks`
  （沿用既有 `StockORMRepository.get_name` 取数链，不新造第二条），再缺时下发空值；
  渲染层对空名称显式输出「名称未知」而**不得**回落成代码；标题统一为
  `盯盘触发 - {名称}（{代码}）`，名称为空时为 `盯盘触发 - {代码}（名称未知）`。

- **FR-3: 盯盘外发可溯源（审计 + 来源标识）**
  每一次盯盘触发外发必须落一条外发审计记录（至少含：外发时间、标的、规则号、触发级别、标题、正文摘要/指纹、
  接收渠道、发送方标识（进程/实例）、送达结果），并支持一条查询回答"谁在几点、为哪条规则、发了什么"；
  卡片必须自带来源标识（形如 `—— v2-watch / <instance>`），使"引擎直发"与"其他路径调用同一通知链"
  在事后可区分；审计写入失败不得阻断通知，但必须响亮留痕。

- **FR-4: 卡片正文契约——触发事实 + 规则意图 + 触发级别 + 下一步**
  盯盘卡正文必须四段齐备：① 触发事实（如 `现价 192.35 ≤ 阈值 218.24（下破）`）；
  ② 规则意图（由 `rule.intent` 映射，`entry`=买入跟踪 / `exit_stop`=止损盯盘 / `trend_observe`=趋势观察 …）；
  ③ 触发级别（`L0` / `L1` / `L2`，含"是否需要 agent 处置"的明确措辞）；
  ④ 下一步（取 `next_action_hint`，缺省给"人工确认"而不是留空）。
  同一句"下破"在 `entry` 与 `exit_stop` 下必须产出**可区分**的正文；级别缺失时按旧渲染兼容但显式标注"未分级"。
  **渲染级别与闭环开关解耦（E9 的直接产物）**：上述四段必须由引擎生产端**无条件下发的渲染级别**驱动，
  不得因 `WATCH_TODO_ENABLED=false`（`todo_service is None`）而退回旧渲染；
  但**闭环专属文案**（待办处置入口 / 处置回执位 / 不可静默声明）只在闭环开启时渲染——
  即"意图与级别恒有，闭环承诺按开关"，不许给用户一个指向不存在待办看板的入口。

## 现状取证（2026-10-07 实测）

| 编号 | 结论 | 证据（可复现） |
|---|---|---|
| E1 | `688525` 在库里**有名称** = 佰维存储，卡面只给代码是展示缺陷 | `psql -c "select symbol,name from quant.stocks where symbol='688525'"` → `688525 \| 佰维存储` |
| E2 | 卡面「现价 192.35」**不是实时价**，正是 2026-09-30 收盘价 | `psql -c "select trade_date,close from quant.daily_klines where symbol='688525' order by trade_date desc limit 3"` → `2026-09-30 \| 192.35` |
| E3 | 2026-10-07 **非交易日**，且 v2 自己判对了 | `quant.trading_calendar` 中 `2026-10-01~10-07` 无行（下一交易日 `2026-10-08`）；`logs/api.log` 有 `orchestrator_trading_day_skip … source=trading-calendar-holiday` |
| E4 | `tick()` 的日级闸门缺失：只判"周末 + 时段"，节假日漏过 | [engine.py:322](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/engine.py#L322) `if now.weekday() >= 5 or not self.is_trading_time(...)`；日级闸门只在 [engine.py:263](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/engine.py#L263) 的 `run_forever()` |
| E5 | 卡面单句由 `price_break` 生成，语义可反读 | [conditions.py:144](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/conditions.py#L144)；意图映射见 [feishu_formatters.py:41](/Users/mac/Documents/ai/pi-investment/quantsys-v2/infrastructure/notification/formatters/feishu_formatters.py#L41)；级别→唤醒见 [notifier.py:163](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/notifier.py#L163) |
| E6 | **本机 v2 引擎在保留窗口内没有发过盯盘卡** | 保留日志 `2026-10-01 21:48 → 2026-10-07 10:07`；`NotificationService` 记录的 77 条外发**类型全为 `system_alert`**，`watch` 类型 0 条（跨全部 58 个日志文件）；`quant.watch_rules` 无 688525；`quant.watch_triggers` 无 688525 |
| E7 | "盯盘卡"在飞书上**结构上不可归因**：v2 与 agent-ts 共用同一机器人，且卡不带署名 | 两份 `.env` 的 `FEISHU_WEBHOOK` **sha1 相同**（同一机器人/群）；[feishu-notification.service.ts:156](/Users/mac/Documents/ai/pi-investment/agent-ts/src/services/feishu-notification.service.ts#L156) 自认"ts 消息无来源标识，用户无法区分执行载体"；agent 侧工具**必带署名**（`content + "—— " + agentSign`），v2 侧不署名 |
| E8 | 阈值 `218.24` 在本机**任何文件里都不存在** | 整盘扫描（排除 `node_modules/venv/.git/Caches/*.app/dist`，限 8MB 文本）：仅命中本窗口会话记录与 `docs/requirements/REQ-261007101318-c392/`；SVG/pnpm store 命中为坐标数字误报 |
| E9 | **卡形根因：好模板已存在，只是被闭环开关门掉了** —— 闭环未开启时，通知**必然**退回"一句事实"的旧渲染 | [engine.py:550](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/engine.py#L550) `_notify_level()`：`if self.todo_service is None: return None` → [engine.py:430](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/watch_engine/engine.py#L430) 不带 `level` → [feishu_formatters.py:57](/Users/mac/Documents/ai/pi-investment/quantsys-v2/infrastructure/notification/formatters/feishu_formatters.py#L57) 走旧渲染。本机 `.env` 无 `WATCH_TODO_ENABLED` ⇒ 闭环关闭 ⇒ **所有盯盘卡都是旧渲染**（无意图/无级别/无署名）——与用户"盯盘卡一致如此"的观察吻合 |
| E10 | **外发零持久化**：任何调用方的外发都不留审计（FR-3 的落点与理由） | `NotificationService.__init__(repository=None)`（[notification_service.py:43](/Users/mac/Documents/ai/pi-investment/quantsys-v2/domain/notification/services/notification_service.py#L43)）：`NotificationRepository` 全仓**只有这一处类型注解**，无适配器、无表（`quant` schema 下无 notification/outbox 表） |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1**：`tick()` 的**时段**自检确实存在（2026-09-11 补的），`run_forever()` 的日级门也是好的——
  所以本需求**不是**"完全没门"，而是**日级门没进 `tick()`**（与 `REQ-261006190953-fc43` 同族：门不齐、不在被调函数层）。
- **R2**：`TradingDayGuard` 本身正确——实测 `2026-10-07` 判 `is_trading_day=False`、`source='trading-calendar-holiday'`、
  `degraded=false`。不能把"休市日误推"读成"日历不准"。
- **R3**：两个 agent 侧通知工具都**强制署名**，说明"无署名"这条判据有效——**不能**据此把责任推给 agent 侧；
  但它同时说明 v2 侧的卡天然不可归因，这正是 FR-3 的存在理由。
- **R4（对 E6 的强度限定）**：v2 的保留日志只回溯到 `2026-10-01 21:48`（更早已轮转），
  而 `watch_triggers` 里 `2026-09-11` 的已通知记录（`notified=t`）在任何保留日志里都找不到对应行——
  **说明"日志里没有"不等于"没发过"**。故 E6 的结论严格限定为"**保留窗口内**本机没发过"，
  不能推广到 09-30 及更早；这也是 FR-3 必须落"审计"而非依赖日志的原因。

## 接口与数据契约

| 接口/对象 | 现状 | 本需求后 | 兼容性 |
|---|---|---|---|
| 飞书盯盘卡标题 | `盯盘触发 - {symbol}`（名称缺失时即代码） | `盯盘触发 - {名称}（{代码}）`；名称未知时显式标注 | 文案变更，无接口破坏；消费方（人）可读性提升 |
| 飞书盯盘卡正文 | 非分级路径 = 单句触发事实 | 触发事实 + 意图 + 级别 + 下一步 四段 | 分级路径（`watch_level_templates`）已有级别渲染 → 复用其口径，不做第二套模板 |
| `WatchEngine.tick()` 语义 | 周末 + 时段；**不看节假日** | 周末 + 节假日 + 时段（唯一日级判据 `TradingDayGuard`） | 行为收紧（休市日不再产出事件）；交易时段内行为不变 |
| `TriggerPayload.name` | `name or symbol`（混同） | 名称（可为空，空即"名称未知"），**永不等于 symbol** | 字段语义收紧；下游模板据此渲染 |
| 盯盘外发审计（新增） | **不存在**（`quant.notification_*` 无此表；agent-os `notification_logs` 只记到 system_alert 且渠道失败） | 新增审计记录：外发时间 / 标的 / rule_id / 级别 / 标题 / 正文摘要 / 渠道 / 发送方标识 / 送达结果 | 新增表，向后兼容；表名与字段最终形态在 **design** 阶段定 |

**迁移与回滚**：新增审计表走 `infrastructure/persistence/migrations/`（**两个库都跑**，带 `lock_timeout`，
沿用本仓既有要求）；回滚 = 停写审计（通知链路不依赖审计即可工作，写入失败只留痕不阻断）。

## 判定标准（可跑）

```bash
# 1) 休市日零事件（冻结时钟，不依赖真实日期）——本需求核心判据
pytest tests/services/test_watch_engine_trading_day_gate.py -q

# 2) 名称兜底：name 缺失时按 symbol 查 quant.stocks，卡面含名称
pytest tests/services/test_watch_notifier_name.py -q

# 3) 文案契约：意图 + 级别 + 下一步齐备，entry/exit_stop 正文可区分
pytest tests/notification/test_watch_templates.py -q -k "intent or level"

# 4) 外发可溯源：一次触发后审计可查（表名以 design 为准）
python tools/watch_audit_probe.py --symbol 600519.SH --dry-run   # 退出码 0 且打印将写入的审计字段

# 5) 不破现状
pytest tests/services/test_watch_engine.py tests/services/test_watch_conditions.py \
       tests/notification tests/application/test_watch_disposition_engine.py -q

# 6) 真实观察（时间型）：2026-10-08 复市首日卡片正常且带名称/意图/级别/来源
psql -h 127.0.0.1 -U mac -d quant_investment -c "
select triggered_at, symbol, left(detail::text, 120)
from quant.watch_triggers where triggered_at::date = '2026-10-08' order by triggered_at desc limit 5;"
```

> 判据 6 是**时间型条件**（需等复市首日），`2026-10-08` 即下一个交易日；
> 在此之前 1~5 条即可判定代码侧完成，第 6 条作为上线后回执。
> 本轮取证用到的九条可复现检查（E1~E8）见上表，均为只读命令。

## 档位依据与升级信号

**重档**，三条独立依据：

1. **动真实外发链路 + 新增落库**：FR-3 要在"每次外发"这条热路径上加审计写库，
   并要让"引擎直发"与"其他调用方"可区分——写失败还不能阻断通知（需明确降级语义）。
2. **改内容契约**：标题格式与正文四段是**给人看的契约**，改它意味着既有分级模板
   （`watch_level_templates`）与旧渲染路径（`feishu_formatters`）要同口径收敛，避免出现两套文案。
3. **改判定行为**：`tick()` 的日级口径收紧会影响所有旁路调用方（脚本 / 任务 / 其他窗口），
   属"行为变更"，必须带回归锁（冻结时钟）与跳过留痕。

**升级信号（预先登记，供后续引用）**：

- 若实施中发现休市日误推**已经驱动过真实委托**（而不只是通知），本需求应升级为含"误触发决策回放与影响评估"的独立需求——本需求不预先纳入。
- 若 FR-3 的审计要覆盖**跨仓（agent-ts / agent-dh）外发**才能回答归因问题，则应拆出"三仓通知来源统一"的独立需求（涉及机器人合并与权限，属运维口径变更）。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 本窗口用户消息（2026-10-07 10:0x）：『盯盘触发 - 688525／现价 192.35 ≤ 阈值 218.24（下破）』＋『1、688525 不是股票名称，2、…什么意思 让卖让买，还是你要给agent处理或者其他处理场景 3、今天没有开市』 | 本现象立项；定性为**盯盘通知的三处契约缺失**（名称 / 语义 / 休市闸门） | FR-1、FR-2、FR-4 | E1~E5；`reqboard_status` 显示本窗口绑定 `REQ-261007101318-c392` |
| D-2 | 立项弹框作答（本窗口，2026-10-07 10:13）：名称「盯盘触发：休市日闸门缺失 + 通知缺股票名称」/ 类型 feature / 难度 expert / 文档位置 `docs/requirements/<REQ>/` | 本工作立项为 **feature**、难度 `expert`，文档落 `docs/requirements/REQ-261007101318-c392/` | FR-1、FR-2、FR-3、FR-4 | 本文件存在且经 `reqboard_submit(kind=requirement)` 登记 |
| D-3 | 本窗口弹框作答（出处）：「飞书卡片/群消息」 | 发送通道 = 飞书（webhook 机器人），排查沿该通道进行 | FR-3 | E7：两份 `.env` 的 webhook sha1 相同 → 同机器人；v2 侧外发类型计数见 E6 |
| D-4 | 本窗口弹框作答（发送者，自定义原文）：「v2项目盯盘驱动发送」 | 用户认定发送者为 v2 盯盘机器人；**取证结论：该认定无法证明是 v2 引擎所发**（同机器人亦供 agent 侧使用） | FR-3 | E6 + E7；R3 |
| D-5 | 本窗口弹框作答（需求边界）：「先钉死发送方（推荐）」 | 先做发送方定位，再定修复面 | FR-3（定位所暴露的缺口） | E6/E7/E8 三条独立取证；R4 限定结论强度 |
| D-6 | 本窗口弹框作答（署名判据，自定义原文）：「盯盘发送的一致没有署名」 | 排除 agent 侧两个必带署名的工具；"盯盘卡无署名"成为**不可归因**的直接原因 | FR-3 | [feishu-notification.service.ts:158](/Users/mac/Documents/ai/pi-investment/agent-ts/src/services/feishu-notification.service.ts#L158)；`FeishuNotifyTool.ts:99` / `NotificationSendTool.ts:122` |
| D-7 | 本窗口用户消息（2026-10-07 10:2x）：「执行可能是另外一个机器执行的，你来修复现在发现的问题，先看看代码」 | **确认范围：FR-3 外发可溯源纳入本需求**；并补充关键背景"执行可能在另一台机器"——正因如此，卡面来源标识 + 外发审计是区分**本机 / 异地 / 手工**的唯一手段（E6/E7/E8/R4 已证：本机范围内不可归因） | FR-3 | 用户原话即凭据；本产物经 `reqboard_ask_confirm(target=artifact, kind=requirement)` 落章 |
| D-8 | 本 agent 读码所得（E9 / E10），供设计阶段遵守 | ① **FR-4 不得靠"开启闭环"来实现**——必须做"渲染级别与闭环开关解耦"，否则等于用运维开关换取卡面可读性；② **FR-3 的落点选渠道/服务层**（覆盖全部调用方），不选 notifier 层（只覆盖引擎——而本次缺的正是"非引擎调用"那一类） | FR-3、FR-4 | E9：`_notify_level` 在 `todo_service is None` 时返回 None（engine.py:550）；E10：`NotificationService(repository=None)`、无适配器无表（notification_service.py:43） |
| D-9 | 本窗口用户消息（2026-10-07 13:0x）：「① 这个卡片同意」 | **卡面契约验收通过**（FR-2 名称在前与缺失标注 / FR-4 意图+处置级别+闭环承诺门控 / FR-3 来源尾注）：用户对 2026-10-07 实发的那张验证卡判为"同意"，文案不再调整 | FR-2、FR-3、FR-4 | 用户原话即凭据；实发卡 `notification_id=notif_ef495a078581464a` 与 `design/interfaces.md` §4「卡面内容契约」一致 |
| D-10 | 本窗口用户消息（2026-10-07 13:0x）：「③ L1 是agent设置的，也应该设置何时调用agent的规则」 | **本项不入本需求范围**：「何时叫 agent」的判据（现有 `EscalationChecker` 三条路径 + `level_resolver` 的 `trigger_level='L2'`）属**新能力**——判据收敛、显式化、可见化，已另立 **`REQ-261007133807-eda6`** 并派给新窗口 `session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49` 当 owner | FR-4（本需求内只做"如实呈现级别与意图"，不做"级别何时产生的判定规则"） | 排除判据：本需求「不做什么」未含该能力，属范围外新增；承接方 = `REQ-261007133807-eda6`（`reqboard_capture(on_window_bound=handoff)` 回执 `bound_policy=handoff`） |
| D-11 | 本窗口用户消息（2026-10-07 13:3x）：「② 不需要」 | **`risk_stop` 渠道未注册 不入本需求范围**，也**不另立需求**：该现象本身成立（L1 卡每次先试 agent 通道 → Agent OS 回 `channel 'risk_stop' not found or disabled` → 才降级飞书，白跑一次往返），但用户裁定不修 | 无（范围外；不影响 FR-1~FR-4 任何一条） | 排除判据：用户原话「② 不需要」；本需求只做通知链的四处契约（闸门/名称/审计/文案），渠道注册属另一层 |
| D-12 | 本窗口用户消息（2026-10-07 14:0x）：「B（你要求以演练替代）」 | **以演练替代 2026-10-08 真实回执**（人工裁定，豁免 t6 的时间型条件）：t6 以 `notes/t6-receipt-rehearsal.md` 的演练证据关账。**如实声明：证据强度弱于真实交易日回执**——演练只证明「链路可跑 + 回执 SQL 形状正确 + 零污染可回滚」，**不能**证明 2026-10-08 当日的真实触发与送达。归档复核时必须看见此限定 | 无（时间型条件由人工裁定豁免；不改 FR-1~FR-4 任何实现口径） | 用户原话「B（你要求以演练替代）」；演练记录含：mock 交易日 tick 产出 1 事件、卡面四段契约齐、两条回执 SQL 命中、`ROLLBACK` 后残留 0/0 |

> **D-x 落账说明（如实记账，两条）**
>
> 1. **D-9 / D-10 发生于 design 阶段**，而 `reqboard_submit(kind=requirement)` **只在 brainstorming 阶段可用**
>    （其后报 `REQBOARD_BAD_STATUS`），故无法经 `change_note` 纳入原确认戳。此处按前例
>    （`REQ-261006190953-fc43` 的 D-6）**按内容落账**，归档时应并入正式 D-x 一并复核。
> 2. **D-10 的承接凭证**：新需求 `REQ-261007133807-eda6`《「何时叫 agent」判据收敛与可见化（升级路径单一入口）》
>    经 `reqboard_capture(on_window_bound=handoff)` 创建，owner = 新窗口 `session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49`；
>    本窗口只负责**排除并指向**，不在本需求内实现「何时叫 agent」的规则。

## 下一步

下一步：design —— 用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 交棒；未获批准不得进入设计/实施。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-268fbd、t-c926cd、t-2e590d |
| FR-2 | ✅ 已接收 | t-d5d9b6、t-2e590d |
| FR-3 | ✅ 已接收 | t-633d3f、t-c926cd、t-2e590d |
| FR-4 | ✅ 已接收 | t-c76181、t-2e590d |

> 无未接收条款（4 条全部有落点）。

<!-- reqboard:marks:end -->
