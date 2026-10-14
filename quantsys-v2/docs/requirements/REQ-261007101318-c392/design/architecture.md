# 架构设计（REQ-261007101318-c392）（serves: FR-1, FR-2, FR-3, FR-4）

**目标一句话**：盯盘通知从"看起来像事实的一行字"变成**可自证的通知**——该不该发（日级闸门进 `tick`）、叫得对（名称兜底）、读得懂（意图 + 处置级别）、查得到（外发审计 + 来源标识）。

> ⚠️ **本文档是"已实现回填"**：用户 2026-10-07 指示「你直接改，然后发送我来判断是否对」，
> 代码先于本文档落地并已验证（228 条定向用例 + 621 条 key 扫描全过）。
> 本文档如实记录**实现后的形状**，不假装尚未开工；差异点逐条标注「实现位置」以便复核。

```
        一张盯盘卡暴露的四个洞，各自的收口点（一洞一处，不许第二份口径）
  ┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
  │ ① 该不该发（FR-1）         │ ② 叫得对（FR-2）           │ ③ 读得懂（FR-4）           │
  ├───────────────────────────┼───────────────────────────┼───────────────────────────┤
  │ WatchEngine.tick()        │ WatchNotifier             │ WatchEngine._notify_level │
  │  └ _resolve_trading_day   │  └ name 不回落 symbol     │  （去掉 todo_service 门）  │
  │    = TradingDayGuard      │     缺失 → 「名称缺失」    │ watch_level_templates     │
  │    （tick / run_forever   │  └ PgStockNameResolver    │  └ 意图 + 处置级别 + 尾注   │
  │      共用同一入口）        │    （与回执同一份取数）    │  └ closed_loop 控制闭环承诺 │
  └───────────────────────────┴───────────────────────────┴───────────────────────────┘
                    │                        │                        │
                    └────────────────────────┼────────────────────────┘
                                             v
  ┌───────────────────────────────────────────────────────────────────────────────────┐
  │ ④ 查得到（FR-3）：NotificationService.send / send_with_fallback（所有外发必经）    │
  │    └ NotificationAuditRepository.save() → quant.notification_audit（一通知一行）   │
  │    └ 卡面尾注 —— v2-watch@<host>#<pid>（跨机靠 host、跨进程靠 pid）                 │
  └───────────────────────────────────────────────────────────────────────────────────┘
```

## 落点与依赖方向（serves: FR-1, FR-2, FR-3, FR-4）

**依赖方向（单向，不许反向）**：

```
adapters（channels / repositories）
        ↑ 实现端口
application（watch_engine / notification_facade / sender_identity）
        ↓ 调用
domain（notification 服务与策略、watch 纯函数）
infrastructure（formatters、persistence、migrations）
```

- **闸门（FR-1）** 落在 `application/services/watch_engine/engine.py` 的 `WatchEngine._resolve_trading_day`
  —— 它是 `tick()` 与 `run_forever()` 的**唯一日级入口**；判定真源是
  `application/services/trading_day_guard.TradingDayGuard.check`（含 `quant.trading_calendar`）。
  引擎**不**自己写第二份 `weekday()`/日历查询。
- **名称（FR-2）** 的取数落在端口实现 `adapters/outbound/repositories/stock_name_resolver.PgStockNameResolver`
  （`domain/watch/ports.StockNameResolver` 的实现），由 `WatchNotifier._lookup_stock_name` 调用；
  与 SLA 巡检/回执渲染**同一份**——此前引擎用 `StockORMRepository.get_name`，是同一问题的第二条口径。
- **审计（FR-3）** 落在 `adapters/outbound/repositories/notification_audit_repository.py`，
  由 `NotificationService`（domain）经 **端口式可选仓储**调用（`repository=None` 即不落库，行为兼容）；
  装配在 `application/notification/notification_factory.py`。
  身份口径落在 `application/notification/sender_identity.py`（纯函数，无外部依赖）。
- **文案（FR-4）** 落在 `infrastructure/notification/formatters/`（纯函数模板），
  输入只认结构化字段（既有纪律：模板不解析已拼好的文案）。

## 为什么闸门必须落在 `tick()`（serves: FR-1）

`tick()` 的时段自检注释自己写明：「任何旁路调用（补跑脚本 / 新服务 / 其他窗口）都会在盘后照样判定并推送」。
2026-09-11 那次只补了「周末 + 交易时段」，**漏了法定节假日**；而日级闸门前只挂在 `run_forever`。
结论：**闸门只有落在被调函数层，才对旁路调用方有效**（与 `REQ-261006190953-fc43` 的判据同源）。
实现后 `tick()` 的第一步即：

```
in_session      = self.is_trading_time(now.time())           # 时段
is_trading, src = self._resolve_trading_day(now.date())      # 日级（含节假日）
if not (is_trading and in_session):
    self._log_market_closed(...)   # 跳过必须可见（按日去重，不刷屏）
    return []
```

**为什么"跳过"也要留痕**：此前跳过是静默 `return []`，事后无法区分"今天没开市"与"引擎没跑"——
休市日误推之所以要靠用户发现，正是因为这条路径不留任何痕迹。

**可注入**：`is_trading_day_fn` / `trading_day_verdict_fn` 两个注入点（生产不注入）。
理由：`TradingDayGuard` 内部用 `datetime.now()` 判"未来日期"，测试冻结时钟若注入未来日期会被判 `future`
而**静默跳过**——注入点让"冻结日期测试"与"真实日历判定"各归其位。

## 为什么级别与闭环必须解耦（serves: FR-4）

旧实现 `_notify_level()` 首行 `if self.todo_service is None: return None`（闭环未开 ⇒ 不给级别 ⇒ 退回旧渲染）。
它把两件事绑死了：

| 概念 | 含义 | 应当由谁决定 |
|---|---|---|
| **级别 P0..P3** | 这条触发够不够格打扰人 + 卡片长什么样（颜色/聚合/是否 @） | **恒解析**（与闭环无关） |
| **闭环** | 要不要建待办、要不要承诺"处置入口 / 回执位" | `closed_loop`（= `todo_service` 是否注入） |

实测后果：本机 `WATCH_TODO_ENABLED` 未开 ⇒ **所有**盯盘卡只剩一句「现价 X ≤ 阈值 Y（下破）」，
用户无法判断该买该卖（2026-10-07 用户原话：「让卖让买，还是你要给agent处理」）。
解耦后：级别恒下发；闭环专属文案由渲染层按 `closed_loop` 决定——**不给用户指向不存在的待办看板的入口**。

## 为什么审计挂在渠道服务层（serves: FR-3）

用户在飞书收到的那张 688525 卡，在 `watch_rules` / `watch_triggers` / 保留日志里**全查不到**：
它不是引擎那条路径发的。若把审计挂在 `WatchNotifier`（引擎专属），**恰好漏掉需要审计的那一类**。
`NotificationService.send / send_with_fallback` 是**所有外发必经**，故审计挂在这里：

- 覆盖：引擎、脚本、异地实例、手工调用；
- 不覆盖（如实声明）：绕过 `NotificationService` 直接 POST 飞书 webhook 的调用
  （此类只能靠**卡面来源尾注**事后识别，或从飞书侧查发送者）。

## 失败与降级纪律（serves: FR-3, FR-1, FR-2）

| 失败点 | 行为 | 理由 |
|---|---|---|
| 交易日判定异常 | 保守判**非交易日** + error 留痕 | 判定失败 ≠ 开市；宁可漏推不可误推 |
| 名称查询异常/未命中 | 名称留空 → 渲染「名称缺失」 | 不臆造名称（R-013），也不冒充成"名称就是代码" |
| 审计写入失败 | `save()` 返回 False + error 留痕，**不上抛** | 审计是增益；不许"发不出去"变成"没发出去还不知道" |
| 审计仓储装配失败 | `repository=None`，通知照发 | 同上（可用性优先于可观测性，但必须响亮留痕） |
| 级别判定异常 | 退回旧渲染（不带级别） | 既有降级语义不变 |

## 与既有机制的关系（不改动，避免重复）（serves: FR-1, FR-2, FR-3）

- **`watch_triggers`（既有台账）不动**：它是"引擎触发 → 处置状态机"的业务台账；
  审计是"渠道外发"的事实记录，两者层级不同、消费方不同，不合并（合并会把非引擎外发塞进业务状态机）。
- **分级模板 `watch_level_templates` 不做第二套**：旧渲染路径与分级路径共用 `INTENT_META`，
  本次只把"处置级别行/来源尾注"补进两条路径，保持单一真相。
- **交易日历数据不刷新**：闸门依赖 `quant.trading_calendar` 正确，日历维护是另一件事。

## 文件结构（新建 / 修改 / 删除）（serves: FR-1, FR-2, FR-3, FR-4）

拆分阶段据此做**变更盘点**；每行一句话职责（与实现一致，可逐个 `git diff` 核对）。

**新建（6）**

| 文件 | 职责一句话 |
|---|---|
| `application/notification/sender_identity.py` | 发送方标识 `v2-watch@<host>#<pid>`（纯函数，取主机名失败退化为 `unknown-host`，绝不抛错） |
| `adapters/outbound/repositories/notification_audit_repository.py` | 外发审计仓储：一通知一行 upsert，**失败自吞**并留痕 |
| `infrastructure/persistence/migrations/20261007_notification_audit_table.py` | 建 `quant.notification_audit`（幂等 + `lock_timeout=30s`，两库都跑） |
| `tests/services/test_watch_engine_trading_day_gate.py` | FR-1 回归锁：休市日零事件 / 交易日照常 / 盘后仍拦 / 默认闸门认识节假日 |
| `tests/notification/test_req_c392_notification_contract.py` | FR-2/3/4 卡面契约锁：名称 / 意图 / 处置级别 / 闭环承诺门控 / 来源尾注 |
| `tests/notification/test_notification_audit_repository.py` | FR-3 审计锁：写入 / 幂等 upsert / 失败不打挂 / 服务层 stamping |

**修改（8 生产 + 3 测试）**

| 文件 | 改了什么 |
|---|---|
| `application/services/watch_engine/engine.py` | `tick()` 补**日级**闸门（`_resolve_trading_day` 单一入口，tick/run_forever 共用）+ 跳过留痕；`_notify_level` 去掉 `todo_service` 门（级别恒解析） |
| `application/services/watch_engine/notifier.py` | `name` 不再回落 symbol；`closed_loop` 透传；名称取数并入领域端口 `PgStockNameResolver` |
| `application/services/watch_engine/dto.py` | `TriggerPayload` 新增 `closed_loop`（默认 True）并随 variables 下发 |
| `application/notification/notification_facade.py` | 新增 `closed_loop` / `sender_id`；`sender_id` 无条件进 variables 与 metadata |
| `application/notification/notification_factory.py` | 装配 `NotificationAuditRepository`（失败降级 `None`，通知照发） |
| `infrastructure/notification/formatters/watch_level_templates.py` | 新增「处置级别」行；闭环承诺（处置入口/回执位/待办#）改由 `closed_loop` 门控；新增来源尾注 |
| `infrastructure/notification/formatters/feishu_formatters.py` | 名称缺失显式标注；新增「处置级别」行与来源尾注（旧路径同口径） |
| `domain/notification/services/notification_service.py` | 三处 `save` 点写入 `delivery_channel` / `delivered` / `fallback_cause`（审计要靠它回答"最后从哪个渠道出去"） |
| `tests/application/test_watch_disposition_engine.py` | 测试替身接受并记录 `level` / `closed_loop`（引擎新增 kwarg） |
| `tests/application/test_watch_t12_todo_creation.py` | `test_no_todo_service_*` 翻新为新契约（级别恒有 + `closed_loop=False`） |
| `tests/application/test_watch_t12_wiring.py` | `test_notify_level_*` 翻新为新契约（不再返回 None） |

**删除**：无（本次不加也不删表；`watch_triggers` 等既有对象一律不动）
