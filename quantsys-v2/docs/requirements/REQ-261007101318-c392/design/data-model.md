# 数据模型设计（REQ-261007101318-c392）（serves: FR-2, FR-3, FR-4）

## 1. 新增表 `quant.notification_audit`（serves: FR-3）

**为什么建表**：用户收到的那张 688525 卡，在 `watch_rules` / `watch_triggers` / 保留日志里
**全都查不到**；而 `NotificationService(repository=None)` ⇒ **外发零持久化**
（`NotificationRepository` 全仓只有一处类型注解，无适配器、无表）。
再叠加 v2 与 agent-ts 的 `FEISHU_WEBHOOK` **完全相同**（同一机器人/群）⇒ 不落审计则事后不可归因。

### 字段与语义（serves: FR-3）

| 字段 | 类型 | 语义 | 取值来源 |
|---|---|---|---|
| `id` | BIGSERIAL | 自增主键 | — |
| `notification_id` | VARCHAR(64) **UNIQUE** | 通知聚合根 id（`notif_xxx`） | `Notification.notification_id` |
| `occurred_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | 首行写入时刻 | 建行时 |
| `notification_type` | VARCHAR(32) NOT NULL | 通知类型（本案 `watch_triggered`） | `NotificationType.value` |
| `priority` | VARCHAR(16) | 优先级（low/normal/high/critical） | `NotificationPriority.value` |
| `title` | VARCHAR(255) | **卡面标题**（FR-3 的核心可读证据） | `Notification.title` |
| `content_digest` | VARCHAR(64) | 正文 sha1（`title\ncontent`）——核对"发的是不是这张卡" | 仓储计算 |
| `content_excerpt` | TEXT | 正文前 500 字（人眼核对，不整存防空膨胀） | `Notification.content[:500]` |
| `status` | VARCHAR(20) NOT NULL | pending/sending/sent/failed/fallback（**末态即最终结果**） | `NotificationStatus.value` |
| `error` | TEXT | 失败原因（渠道失败/异常） | `Notification.error_message` |
| `delivery_channel` | VARCHAR(32) | **最后从哪个渠道出去**（agent/feishu/None） | `metadata.delivery_channel` |
| `delivered` | BOOLEAN | 是否真送达 | `metadata.delivered` |
| `sender_id` | VARCHAR(128) | **发送方标识** `v2-watch@<host>#<pid>` | `metadata.sender_id` |
| `payload_meta` | JSONB | 白名单上下文（symbol/name/rule_id/intent/trigger_level/watch_level/closed_loop/watch_channel/wake_target） | variables+metadata 白名单 |
| `created_at` / `updated_at` | TIMESTAMPTZ NOT NULL | 建行/末次更新时刻 | — |

**索引**：`occurred_at DESC`（按时间倒查）、`title`（按标题找卡）、`sender_id, occurred_at DESC`（按来源追）。

### 关键决定：为什么是 **upsert** 而不是追加（serves: FR-3）

`NotificationService` 在一次外发里会 **多次** `repository.save(notification)`：
`mark_sending()` → save、`mark_sent()/mark_fallback()` → save、（全败）→ save。
若做成追加式，一次通知会写 2~3 行噪声，且"哪行是终态"要靠猜。
故 `notification_id` 唯一 + `ON CONFLICT DO UPDATE`（更新 status/error/delivery_channel/delivered/
sender_id/payload_meta/updated_at）——**一通知一行，末态覆盖**，查询语义最简。

### 关键决定：为什么**不**建 ORM 模型（serves: FR-3）

`tests/test_orm_db_drift.py` 逐模型比对"模型声明 vs 测试库"，新增 ORM 模型就必须同步两库结构，
否则漂移门红。本表只被一个适配器**只写不读**（读走 SQL/看板），没有 ORM 查询需求；
不建模型 = 不动 ORM 注册表、不引漂移风险。**若将来要 ORM 读它，必须同时补模型 + 迁移 + 两库镜像**。

### 迁移与回滚（serves: FR-3）

- 迁移脚本：`infrastructure/persistence/migrations/20261007_notification_audit_table.py`
  （`CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`，幂等；带 `SET lock_timeout = '30s'`，
  防 DDL 撞 `idle in transaction` 无限等锁——本仓既有要求）。
- **两个库都已执行**：`quant_investment`（生产）与 `quant_test`（测试镜像）。
  实测回执：两库均 `[verify] 建表完成，当前审计行数: 0`。
- **回滚**：`DROP TABLE quant.notification_audit;` —— 通知链路不依赖它（`repository=None` 即旧行为），
  删除只丢审计，不影响任何业务路径。

## 2. 不动的既有表与理由（serves: FR-3）

| 既有对象 | 决定 | 理由 |
|---|---|---|
| `quant.watch_triggers` | **不动、不合并** | 它是"引擎触发 → 处置状态机"的**业务台账**（含 disposition/dup_of/todo_id）；审计是**渠道外发**事实。合并会把"非引擎外发"塞进业务状态机，制造假触发 |
| `quant.watch_rule_changes` / `watch_receipts` 等闭环表 | 不动 | 闭环开关（`WATCH_TODO_ENABLED`）未开，本需求不引入闭环承诺（`closed_loop=False` 时不渲染） |
| `quant.trading_calendar` | 不动（只读） | 闸门依赖它正确；刷新日历是独立事项（本需求不越界） |
| `quant.stocks` | 不动（只读） | 名称取数沿用端口实现 `PgStockNameResolver`（本次把引擎的第二条口径并入它） |
| `simulation_equity_snapshot` 等 | 无关 | — |

## 3. 数据契约变更（serves: FR-2, FR-4）

| 对象 | 变更 | 兼容性 |
|---|---|---|
| `TriggerPayload` | 新增 `closed_loop: bool = True` | 有默认值 → 旧调用方不改；默认 True 与"旧行为里有级别即意味着闭环开"等价 |
| `Notification.variables` | 新增 `closed_loop`（bool）、`sender_id`（str） | 纯新增键；旧 formatter 读不到即走旧行为 |
| `Notification.metadata` | 新增 `sender_id`（facade 无条件写入）、`delivery_channel` / `delivered` / `fallback_cause`（服务层写） | 纯新增键；审计读它，不改聚合根既有字段 |
| 卡面标题 | `盯盘触发 - {名称}（{代码}）`；名称缺失 → `{代码}（名称缺失）` | 文案变更，无接口破坏 |
| 卡面正文 | 新增「**处置**：L0/L1/L2 …」行与「—— {sender_id}」尾注 | 级别未知则**隐藏该行**（不臆造）；无 sender_id 则不渲染尾注（旧调用方不受影响） |

**不做的事**：不给 `watch_triggers` 加"是否交易日"列、不给审计表加外键约束——
交易日属性是日历的函数（落列会与日历漂移），审计表不参与业务约束。
