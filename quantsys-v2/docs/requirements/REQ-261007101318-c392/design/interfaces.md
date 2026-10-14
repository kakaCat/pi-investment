# 接口设计（REQ-261007101318-c392）（serves: FR-1, FR-2, FR-3, FR-4）

**原则**：只加**可选**参数/字段，不改既有签名语义，不新增第二份取数口径。

## 1. `WatchEngine`（serves: FR-1, FR-4）

### 1.1 构造注入（新增两个可选参数）（serves: FR-1, FR-4）

```python
WatchEngine(..., is_trading_day_fn: Optional[Callable] = None,
                 trading_day_verdict_fn: Optional[Callable] = None)
```

| 参数 | 输入 | 输出 | 语义 | 生产是否使用 |
|---|---|---|---|---|
| `is_trading_day_fn` | `date` | `bool` | 只要布尔；测试用 | 否（生产不注入） |
| `trading_day_verdict_fn` | `date` | 带 `.is_trading_day` / `.source` / `.degraded` 的裁决对象 | 要 source/降级信息；测试用 | 否 |

未注入时默认 `TradingDayGuard.check`（惰性 import，避免 import 期拉起重依赖）。

### 1.2 `_resolve_trading_day(day) -> (bool, str)`（serves: FR-1）

**唯一日级入口**，`tick()` 与 `run_forever()` **共用**。

- 返回 `(is_trading_day, source)`；`source` 形如 `trading-calendar` / `trading-calendar-holiday` /
  `weekend` / `future` / `unavailable/degraded` / `injected` / `compute-error`。
- **错误语义**：注入方抛错 → `(False, 'injected-error')`；默认判定抛错 → `(False, 'compute-error')`。
  **一律保守判非交易日**，绝不因判定异常而放行判定。

### 1.3 `tick() -> List[dict]`（行为契约收紧）（serves: FR-1）

- 前置：`is_trading_time(now.time())` **且** `_resolve_trading_day(now.date())[0]` 同时为真；否则
  调用 `_log_market_closed(...)`（按「日 + 原因」去重留痕）并 `return []`
  —— **不取规则、不评估、不落库、不外发**。
- 返回：命中事件列表（字段与既有口径一致，含 `disposition` / `trigger_level` / `notified` 等）。
- 兼容性：交易时段内行为**逐字不变**；新增行为只在"非交易日"（周末/节假日）生效。

### 1.4 `WatchNotifier.notify(..., closed_loop: bool = True)`（serves: FR-4）

新增可选参数，随 `TriggerPayload.closed_loop` 下发到通知 variables。
`closed_loop=True` 表示"闭环已开，可以承诺处置入口/回执"；`False` 表示"只提醒，不承诺闭环"。
默认 `True` = 兼容旧调用方。

## 2. `WatchNotifier`（serves: FR-2, FR-3）

```python
WatchNotifier.notify(rule, condition, quote, result,
                     escalation_reason=None, disposition=None, disposition_reason=None,
                     dup_of=None, action_amount_yuan=None, level=None, closed_loop=True)
```

- **名称契约（FR-2）**：传给 `NotificationFacade` 的 `name` 为「行情 name → `quant.stocks` 兜底 → **None**」。
  **永不等于 symbol**（旧写法 `payload.name or payload.symbol` 已删）。
- **取数口径**：`_lookup_stock_name(symbol)` 走端口实现 `PgStockNameResolver.resolve_batch([bare])`
  （与 SLA 巡检/回执同一份），异常/未命中 → `None`（不上抛）。
- 返回值：落库后的触发对象；`trigger_repo=None` 时返回 `None`（验证脚本据此不污染台账）。

## 3. `NotificationFacade.send_watch_triggered(...)`（serves: FR-3, FR-4）

新增两个可选参数：

| 参数 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `closed_loop` | `bool` | `True` | 是否承诺处置闭环（渲染色决定） |
| `sender_id` | `str` | `None` → 取 `current_sender_id()` | 发送方标识；**无条件**写入 `Notification.variables['sender_id']` 与 `metadata['sender_id']` |

标题契约：`title = f"盯盘触发 - {symbol}"`（不变；**人眼可读的名称在正文首行**，由渲染层保证）。
**错误语义**：本方法不因 `sender_id` 取值失败而抛错（`socket.gethostname()` 失败退化为 `unknown-host`）。

### 3.1 `application/notification/sender_identity.current_sender_id(kind='v2-watch') -> str`（serves: FR-3）

- 输出：`v2-watch@<hostname>#<pid>`（进程级，**无配置项**）。
- 跨机分辨靠 `hostname` 段（用户 2026-10-07：「执行可能是另外一个机器执行的」）；
  跨进程分辨靠 `pid` 段。
- **已知瑕疵（如实登记）**：`hostname` 段在不同进程可能给出 mDNS 名或 IP
  （实测 launchd 侧 `192.168.1.109`、终端侧 `yunpengs-MacBook-Pro.local`）。
  跨机分辨不受影响；若需"同机按 host 聚合"稳定，需统一为 FQDN（未纳入本次范围）。

## 4. 卡面内容契约（serves: FR-2, FR-4）

**分级路径**（`watch_level_templates`）与**旧路径**（`feishu_formatters`）**同口径**：

| 段 | 内容 | 缺失时 |
|---|---|---|
| 标题 | `🟠 P1 待决策（1 项）· 佰维存储（688525）` / 旧路径 `🛑 止损盯盘 · 佰维存储（688525）` | 名称缺失 → `{代码}（名称缺失）` |
| 意图 | `**🛑 止损盯盘｜佰维存储（688525）**`（`INTENT_META` 7 类） | 未标注 → `❓ 未标注意图` |
| 触发 | `**触发**：现价 192.35 ≤ 阈值 218.24（下破）` | 条件缺失 → `-` |
| 现价 | `**当前**：¥192.35 (+涨跌幅)　盈亏 %` | 价格缺失 → `-`（不臆造） |
| 目的 | `**这条提醒为了**：<intent 驱动的目的句>` | 用 `INTENT_META` 默认句 |
| 预案 | `**预案**：<rule.context>` | 无 context → 隐藏该行 |
| **处置级别** | `**处置**：L2 行动（需 agent 介入处置）` | **级别未知 → 隐藏该行**（不臆造） |
| 下一步 | `**下一步**：<next_action_hint 或 intent 映射>` | 兜底「见触发条件」 |
| 闭环承诺 | 「处置入口／不可静默／回执位／待办#」 | **`closed_loop=False` → 全部不渲染** |
| **来源尾注** | `—— v2-watch@<host>#<pid>` | 无 `sender_id` → 不渲染 |

**处置级别措辞表**（`TRIGGER_LEVEL_META`）：`L0 纯信息（只看，不需要动作）` /
`L1 提醒（人工判断，不唤醒 agent）` / `L2 行动（需 agent 介入处置）`。

## 5. 审计仓储（serves: FR-3）

```python
class NotificationAuditRepository:          # 实现 NotificationRepository 端口语义
    def save(self, notification) -> bool    # True=写入成功；False=失败（已留痕，不上抛）
```

- **调用点**：`NotificationService.send()`（成功 / 全败）与 `send_with_fallback()`
  （主渠道成功 / 降级发送）四处 —— 覆盖**所有**外发路径。
- **服务层写入 metadata 的键**：`delivery_channel`（最后出口渠道）、`delivered`（是否送达）、
  `fallback_cause`（降级原因）。
- **幂等**：按 `notification_id` upsert。
- **错误语义**：任何异常（含 `_params` 构造失败）都被 `save()` 吞掉并 error 留痕 —— 审计失败**绝不**影响通知。

## 6. 查询接口（人/agent 用，serves: FR-3）

```sql
-- 「谁在几点、为哪条规则、发了什么标题」——本次那张卡曾经答不出的问题
select occurred_at, notification_type, title, delivery_channel, delivered, sender_id
  from quant.notification_audit
 order by occurred_at desc limit 20;
```

**判定"是否本机所发"**：看 `sender_id` 的 `host` 段与 `pid` 段
（本机实例 = 本机 host + 该进程 pid；异地实例 = 别的 host；手工 webhook = 无此行）。
