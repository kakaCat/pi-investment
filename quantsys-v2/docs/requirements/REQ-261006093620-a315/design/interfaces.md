# 接口设计（REQ-261006093620-a315）

## 1. `application/services/trading_day_gate.py`（新建，判据唯一真源）（serves: FR-1, FR-2, FR-5）

从 `adapters/inbound/fastapi_app/daily_jobs/gate.py` **原样搬入**三个既有函数（签名逐字不变，
③ 的调用方零改动），并新增策略感知入口：

```python
# ── 既有三个（原样搬迁，③ 直接用） ──────────────────────────────
SOURCE_GATE_ERROR = 'gate-error'

def verdict_info(now: Optional[datetime] = None) -> Dict[str, Any]:
    """五键注解: day / is_trading_day / source / degraded / reason。**永不抛**。"""

def skip_non_trading_day(now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]:
    """等价 should_skip('trading-days', now)。返回 (是否跳过, 判定注解)。**永不抛**。"""

def is_non_trading_day(now: Optional[datetime] = None) -> bool:
    """局部跳过用（③ 的因子段）。**永不抛**。"""

# ── 新增：策略感知 ───────────────────────────────────────────────
POLICY_ALWAYS = 'always'
POLICY_TRADING_DAYS = 'trading-days'
POLICY_HOLIDAYS = 'holidays'
KNOWN_POLICIES = frozenset({POLICY_ALWAYS, POLICY_TRADING_DAYS, POLICY_HOLIDAYS})

def should_skip(policy: Optional[str], now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]:
    """按策略判定"本次自动执行是否跳过"。返回 (是否跳过, 判定注解)。**永不抛**。

    策略语义（见 data-model §1）：
      always         → (False, info)                       # 不判门
      trading-days   → skip ⇔ (not is_trading_day) and (not degraded)
      holidays       → skip ⇔ source == 'trading-calendar-holiday' and (not degraded)
      未知/None      → (False, info + 'policy_unknown': True)  # fail-open + warning
    """
```

**为什么未知策略 fail-open 而不是 fail-closed**：策略列的 CHECK 已经在写库侧挡住非法值；
运行时仍读到未知值只剩"人工直改库 / 回滚到旧代码"两种可能。此时**照跑**的后果是
"多跑一次"，**跳过**的后果是"任务静默停摆"——与 FR-2 的取舍同向（绝不拿可用性换省一次重算）。
未知值必须**记 warning 并写进 result**，不许静默。

## 2. 判据口径：两个函数不可互换（serves: FR-2, FR-4）

| 调用 | `2026-10-06`（休市） | `2026-10-08`（复市首日） | 用途 |
|---|---|---|---|
| `TradingDayGuard.check(d)`（门内部用） | `False` / `trading-calendar-holiday` | **`False` / `future`** | 判"今天该不该跑"（**只传当天/过去**） |
| `resolve_trading_day(d).date == d` | `False` | **`True`** | 验收"复市首日不得跳过"（日历表覆盖到 2026-12-31） |

**门的 `now` 缺省 = `datetime.now()`（今天）**，永远不会把"未来日期"喂给 guard，
故 `future` 分支对门**不可达**。`future` 只在——有人拿 `check('2026-10-08')` 当验收判据时——
才会冒出来把人误导成"复市首日被跳过了"。

**因此 FR-8 的反例锁是接口层契约**：测试必须固定
`TradingDayGuard.check('2026-10-08').source == 'future'`，防止后续有人把验收写成
`check(复市首日).is_trading_day` 而反复改坏门。

## 3. `infrastructure/scheduler/job_executor.py`（serves: FR-2, FR-3, FR-6）

```python
def execute_scheduled_job(task_id: int, manual: bool = False):
    """APScheduler 调用入口。manual=True = 人工触发（跳过门）。"""

def _execute_scheduled_job_impl(task_id: int, manual: bool = False):
    """执行体。流程（新增项标 ★）：

      1. repo.get_task(task_id)                    # 读任务（含 trading_day_policy）
      2. is_enabled 检查                            # 既有
      ★3. 门判定（仅 manual=False 时）：
             policy = task.get('trading_day_policy') or POLICY_ALWAYS
             skip, info = should_skip(policy, now)
             skip → create_run → complete_run_skipped(run_id, result={...}) → return
      4. 并发检查（既有，只对 running 判）
      5. create_run → _execute_command → complete_run   # 既有，逐字不变
    """
```

**落点为何在并发检查之前**：跳过不占用执行槽、也不该被"已有 running"拒绝；
放在并发检查之前，休市日的跳过记录**恒为一条**，语义干净。

**跳过时写的 result 形状**（固定五键，与 ③ 同形，便于统一巡检）：

```python
{
  'skipped': True,
  'reason': info['reason'],                 # 人读原因
  'trading_day_source': info['source'],      # trading-calendar-holiday / weekend / calendar / gate-error / ...
  'degraded': info['degraded'],
  'policy': policy,
}
```

**不打扰**：跳过路径**不调用** `_report_failure_to_sink`、不发 Agent OS 事件、不写 `last_error`
（`last_error=None`）。只在 executor 打一行 `logger.info`。

## 4. `apscheduler_service.trigger_task_now`（serves: FR-6）

```python
def trigger_task_now(self, task_id: int):
    """人工触发一次执行（不判交易日门）。

    2026-10-06 起（本需求）：不再 modify_job(next_run_time=now)——
    那条路与自动到点共用同一 job，执行期无法区分"人按的"与"到点的"。
    改为投递一次性 job，显式带 manual=True：
    """
    job = self.scheduler.get_job(f"task_{task_id}")   # 不存在 → ValueError（既有语义保留）
    self.scheduler.add_job(
        func=execute_scheduled_job,
        trigger=DateTrigger(run_date=datetime.now()),
        args=[task_id],
        kwargs={'manual': True},
        id=f'manual_{task_id}_{int(time.time())}',      # 每次唯一 → 一次性 job 之间不互相覆盖
        name=f'[manual] {job.name}',
        replace_existing=False,
        misfire_grace_time=None,                        # 人工触发不该因宽限被丢
    )
```

| 契约 | 值 |
|---|---|
| 对外行为 | "立即跑一次"，成功返回后人工可查 `scheduler_runs` 那条真执行记录 |
| 异常 | `task_id` 在 APScheduler 无注册 job → `ValueError`（**保留既有语义**，路由层靠它降级到 legacy 路径） |
| job id 约定 | 自动：`task_{id}`；人工：`manual_{id}_{epoch}` |
| 副作用 | **不再**改动 `task_{id}` 的 `next_run_time`（比现状更安全） |
| 收尾 | DateTrigger 耗尽 → APScheduler 自动摘除该一次性 job（jobstore 不留垃圾） |

`adapters/inbound/fastapi_app/routes/scheduler_async.py` **不改**：`:441` 调 `trigger_task_now`，
`:447` 的 legacy fallback `_scheduler.run_task` 不经 executor、天然不受门影响。

## 5. 仓储层（serves: FR-3）

`adapters/outbound/repositories/scheduler_repository.py`：

```python
def _finish_run(self, run_id: int, status: str, result=None, error=None,
                completed_at=None) -> bool:
    """私有：三种终态共用的收尾（status / completed_at / duration_ms /
    result(_json_safe) / config.last_status / next_run_at 重算）。失败不抛。"""

def complete_run(self, run_id, success=True, result=None, error=None, completed_at=None) -> bool:
    """既有签名逐字不变；内部改为调 _finish_run(status=('success' if success else 'failed'))。"""

def complete_run_skipped(self, run_id: int, result=None, completed_at=None) -> bool:
    """新增：闭环为 status='skipped'（语义见 data-model §5）。"""
```

**既有 6 处 `complete_run` 调用方零改动**（签名与返回值不变）。

## 6. `application/services/should_have_run.py`（serves: FR-3）

```python
# 判据显式化（不改判定结论，只把"靠 != 的副作用"变成"写出来的两套集合"）
NOT_MISSED_STATUSES = ('success', 'failed', 'skipped')   # 用于"是否算处理过"
REAL_RUN_STATUSES   = ('success', 'failed')              # 用于"最近一次真执行"呈现
```

- `:274`「最近一次**真执行**（`status != 'missed'`）的 `started_at ≥ 应跑时刻` → ok」：
  语义拆成"**该槽位是否已被处理**"（含 `skipped`）→ 休市日槽位**不判 missed**（正确、且显式）；
- `:359`「最近一次真执行的 `started_at`」：仍用 `REAL_RUN_STATUSES`，
  避免把 `skipped` 当成执行时刻展示；
- **不掺交易日历**：本模块的纪律（`:38`）明确"只判该跑没跑"，日历判定仍归门——本次不动这条。

## 7. 对外 HTTP 契约（serves: FR-6）

| 端点 | 变化 |
|---|---|
| `POST /api/scheduler/tasks/{task_id}/trigger` | **无**（休市日仍可用；响应文案不变） |
| `POST /api/scheduler/reload` | **无** |
| `POST /api/scheduler/compensate` | **无**（走 `_scheduler.run_task`，不经门） |
| `GET /api/scheduler/runs` / `tasks/{id}/runs` | **形状不变**；`status` 多一个取值 `skipped` |
| `GET /api/scheduler/tasks` | **形状不变**；任务对象多一个字段 `trading_day_policy` |

**无破坏性契约变更**、不新增第三方依赖。

## 8. 错误语义（serves: FR-2, FR-3）

| 场景 | 行为 | 留痕 |
|---|---|---|
| 门判定异常（`TradingDayGuard` 抛） | **照跑** | result 带 `source='gate-error'` / `degraded=true`；门记 warning |
| 日历链降级（`weekday_fallback` / `unavailable`） | **照跑** | result 带真实 `source` / `degraded=true` |
| 策略值未知 | **照跑** | result 带 `policy_unknown: true`；记 warning |
| 写 `skipped` 记账失败 | **不影响调度**（`complete_run_skipped` 返回 False，不抛） | 日志 error；该次 run 可能停在 running → 由既有孤儿回收闭环 |
| 任务行不存在 / `is_enabled=false` | 既有行为不变（return） | 既有日志 |

**门与记账都遵守同一条原则：不许成为可用性故障源。**
