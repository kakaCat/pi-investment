# 数据模型设计（REQ-261006093620-a315）

## 1. 新增列：`quant.scheduler_tasks.trading_day_policy`（serves: FR-1, FR-4, FR-5）

```sql
ALTER TABLE quant.scheduler_tasks
  ADD COLUMN IF NOT EXISTS trading_day_policy varchar(16) NOT NULL DEFAULT 'always';

ALTER TABLE quant.scheduler_tasks
  DROP CONSTRAINT IF EXISTS scheduler_tasks_trading_day_policy_check;
ALTER TABLE quant.scheduler_tasks
  ADD CONSTRAINT scheduler_tasks_trading_day_policy_check
  CHECK (trading_day_policy IN ('always', 'trading-days', 'holidays'));
```

| 字段 | 类型 | 必填 | 缺省 | 取值 | 语义 |
|---|---|---|---|---|---|
| `trading_day_policy` | `varchar(16)` | 是（NOT NULL） | `'always'` | `always` | **行为与现在完全一致**：不判门、照跑 |
| | | | | `trading-days` | 非交易日（休市日 / 周末 / 未来）**一律跳过** |
| | | | | `holidays` | **只跳法定节假日**（`source='trading-calendar-holiday'`），周末照跑 |

**为什么 NOT NULL + DEFAULT**：三值里必须有一个"什么都不做"的缺省，否则既有行在迁移后
语义未定义；`DEFAULT 'always'` 让"没写策略的行"逐字等于今天的行。

**为什么要 CHECK 约束**：本仓"静默失效"教训密集（`params` 里拼错键、打桩点漂移、停用 DB 行但
jobstore 仍触发）。策略值是**执行开关**，拼错必须**响亮失败**，而不是悄悄退化成 `always` 或
悄悄跳过。CHECK 只挡写库侧；**运行时读到未知值仍按 fail-open 照跑并记 warning**（见 interfaces）。

**为什么不用 `params jsonb`**：① `params` 是**handler 的入参**，混入调度策略会让 handler 收到
无关键（`_execute_command(command, params)` 会把策略一起传下去，语义污染）；
② jsonb 内无 schema、无约束，拼错静默失效；③ 巡检/看板按策略筛任务时不友好。

## 2. 策略回填（8 条挂门 / 3 条不挂）（serves: FR-4, FR-5）

迁移内按 `id` 精确回填（**不用 name 匹配**：name 是 UNIQUE 但历史上有改名记录）：

| task_id | name | 目标策略 | 依据（为什么是这个策略） |
|---|---|---|---|
| 250 | pre-market-scan | `trading-days` | 真实选股打分，吃当日行情 |
| 247 | daily-signal-generate | `trading-days` | 池内扫描出信号，吃当日行情 |
| 242 | 每日信号执行 | `trading-days` | 推当日 pending 信号（`date.today()`） |
| 259 | daily-signal-push-fallback | `trading-days` | 同上（同一 handler） |
| 249 | v13-simulation-trading | `trading-days` | 模拟交易检查，休市无成交 |
| 261 | chan-scan-daily | `trading-days` | 收盘后买卖点扫描，休市日重扫冻结快照 |
| 237 | 每周报告生成 | `trading-days` | 周报吃本周行情（周五 18:00） |
| 232 | 每日数据质量检查 | **`holidays`** | 排班**含周末**（`0 0 * * *`）→ 按 D-6 分档，周末照跑 |
| 252 | daily-strategy-validation | `always` | 基于落库回测证据 `lookback_days=30`，不吃当日行情 |
| 253 | weekly-strategy-discovery | `always` | `lookback_days=365`，排在周六 |
| 262 | chan-knowledge-distill-weekly | `always` | `lookback_days=90`，排在周日 |

`always` 三行**不必写 UPDATE**（DEFAULT 已覆盖）；迁移只显式回填上述 8 行，且**逐行存在性校验**
（`UPDATE ... WHERE id=%s` 的 rowcount 为 0 时打印警告——任务可能已被删，不算失败）。

## 3. ORM 映射（serves: FR-1, FR-7）

`infrastructure/persistence/orm/models/scheduler.py` 的 `SchedulerTaskConfig` 加：

```python
trading_day_policy = Column(
    String(16), nullable=False, server_default='always',
    comment="交易日门策略: always=不判门 / trading-days=非交易日跳过 / holidays=只跳法定节假日",
)
```

**为什么必须同批改 ORM**：`tests/test_orm_db_drift.py` 比对"模型声明"与"测试库实际列"，
只加库表不加模型（或反之）会直接红——这正是 2026-10-02 那次"模型比库表多 3 列 → ② 一条任务
都加载不了"的同族故障。

## 4. 迁移方式与回滚（serves: FR-1, FR-7）

- **文件**：`infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py`
- **约定**（沿用 `20261002_scheduler_tasks_missing_columns.py`）：
  缺省 dry-run 只打印 DDL、`--apply` 才写；DDL 全部 `IF NOT EXISTS`；**verify 段必须防空表**
  （空表 `.first()` 返回 `None`，历史上有一次直接 `row[0]` 在测试库必现 TypeError）。
- **必须两个库都跑**（生产 `quant_investment` + 测试 `quant_test`），否则漂移门禁红：
  ```bash
  python infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py \
    --apply --dsn postgresql://mac@127.0.0.1:5432/quant_test
  # 生产同理（显式 DSN，别指望 PGDATABASE 覆盖）
  ```
- **DDL 请加 `lock_timeout`**（CLAUDE.md 明载：测试库 DDL 会被 `idle in transaction` 连接锁住，
  漂移门禁曾因此让整套测试停在 78% 跑不完）。
- **回滚**：不改列、不删列 → 回滚 = 把 8 行改回 `'always'`：

  ```sql
  UPDATE quant.scheduler_tasks SET trading_day_policy='always'
   WHERE id IN (250,247,242,259,249,261,237,232);
  ```

  执行期判定 ⇒ **改完立即生效，无需 reload、无需重启**。

## 5. 台账契约：`quant.scheduler_runs.status` 新增 `'skipped'`（serves: FR-3）

`status` 列是 `text NOT NULL DEFAULT 'running'`、**无 CHECK 约束** →
`'skipped'` 无需任何 DDL 即可写入。

### 三态语义（本设计定死）（serves: FR-3）

| status | 谁写 | 语义 | `started_at` | `completed_at` |
|---|---|---|---|---|
| `running` | `create_run` | 正在跑 | 真实开始 | NULL |
| `success` / `failed` | `complete_run` | 真跑了，成/败 | 真实开始 | 真实结束 |
| `missed` | `record_missed_run`（既有） | **该跑没跑**（超 misfire 宽限被调度器跳过） | **被跳过的那个排班时刻** | 有值 |
| **`skipped`** | **`complete_run_skipped`（新增）** | **门主动判定"今天不该自动跑"** | 判定时刻 | 有值（=判定时刻） |

`skipped` 与 `missed` 的**极性相反**，这是本设计最容易写错的地方：

- `missed` = 异常（本不该发生）→ **应告警**；
- `skipped` = 正常（按日历本就不该跑）→ **不应告警**、也**不算"跑过"**。

### 消费者矩阵（逐个对账，不靠 `!=` 的副作用）（serves: FR-3, FR-7）

| 消费方 | 现有判据 | 对 `skipped` 的应有行为 | 本设计动作 |
|---|---|---|---|
| `tools/health_probe.py` → `application/services/should_have_run.py:274/359` 「最近一次**真执行**（`status != 'missed'`）」 | 会把 `skipped` 当"跑过" → **恰好不误报**，但语义错（叫"真执行"） | **不算漏跑**（正确），但**不算真执行**（呈现用） | 判据显式化为集合：`NOT_MISSED` / `REAL_RUN` 两套，`skipped` 入前者、不入后者 |
| `scripts/scheduler_watchdog.py:289/390` `status='success'` | 会把 `skipped` 当"没跑" → **误报漏跑** | **不算漏跑** | 改为 `status IN ('success','skipped')`（该脚本未见 launchd 排班，属低成本一致性） |
| `tests/...` 无关 | — | — | — |
| `recover_orphan_runs`（`status == 'running'`） | 只看 running | 不碰 | 无需改（已核实） |
| `_is_zombie_run`（只对 `list_runs(statuses=['running'])` 的结果判） | 只看 running | 不碰 | 无需改（已核实） |
| `complete_run` 内 `config.last_status = status` | 写 `last_status` | 写 `'skipped'` + `last_error=NULL` | `complete_run_skipped` 复用同逻辑 |
| 看板/接口 `list_runs` / `get_scheduler_task_runs` | 透传 status | 多一个取值，展示层增量 | 无需改（接口形状不变） |

**只改一处就覆盖生产告警**：活的告警路径只有 `health_probe → should_have_run.audit_should_have_run`
（`tools/check_should_have_run.py` 与它共用同一实现）。

### 记账方法契约（serves: FR-3）

`adapters/outbound/repositories/scheduler_repository.py`：

```python
def complete_run_skipped(self, run_id: int, result: Optional[Dict[str, Any]] = None,
                         completed_at: Optional[datetime] = None) -> bool:
    """把一条 run 闭环为 status='skipped'（门判定"今天不该自动跑"）。
    复用 _finish_run：completed_at / duration_ms / result(_json_safe) / config.last_status 同口径。
    next_run_at 照 complete_run 的既有逻辑重算（不动 APScheduler 排期事实）。
    失败返回 False，绝不抛（记账失败不许影响调度）。"""
```

**为什么不给 `complete_run` 加第三态**：它的签名是 `success: bool` →
`status = "success" if success else "failed"`，现有 6 处调用方靠这个二值语义；
加 `status=` 形参会把"成/败"与"跳/没跳"两件事混进一个参数。
做法改为**抽私有 `_finish_run(run_id, status, result, error)`**，`complete_run` 与
`complete_run_skipped` 都调它 —— 避免"两份收尾逻辑"漂移。
