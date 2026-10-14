# 使用场景（REQ-261006093620-a315）

每个 UC 给出：**触发 → 期望行为 → 可观察读数**。读数一律是可查的台账/命令，不是"应该没问题"。

## UC-1 休市日：自动到点整段跳过（serves: FR-1, FR-3, FR-4）

**触发**：`2026-10-07`（国庆休市·周三）09:25，APScheduler 到点为 `pre-market-scan`(250) 调
`execute_scheduled_job(250)`（`manual` 缺省 False）。

**期望**：
1. 读任务 → `trading_day_policy='trading-days'` → `should_skip` 得
   `(True, {is_trading_day: False, source: 'trading-calendar-holiday', degraded: False})`；
2. **不调用** `_execute_command`（`market_scan_preopen` 一行都不跑）；
3. 落一条 `scheduler_runs`：`status='skipped'`、`completed_at` 有值、`result` 五键；
4. **不发**任何通知、`last_error` 为 NULL。

**可观察读数**：
```sql
select t.id, t.name, t.trading_day_policy, r.status, r.result->>'trading_day_source' as src,
       r.result->>'reason' as reason
  from quant.scheduler_runs r join quant.scheduler_tasks t on t.id = r.task_id
 where r.started_at::date = '2026-10-07' order by t.id;
-- 期望：8 条挂门任务 status='skipped'；3 条不挂门任务 status='success'
```

## UC-2 交易日：行为逐字不变（serves: FR-1, FR-4, FR-8）

**触发**：`2026-09-30`（交易日）同一路径。

**期望**：`should_skip` 返回 `(False, {is_trading_day: True, source: 'trading-calendar', degraded: False})`；
执行流程与改动前**逐字相同**（并发检查、`create_run`、`_execute_command`、`complete_run` 全在）；
`status='success'` 或按内层失败判 `failed`——**判定逻辑一行不改**。

**回归锁**：既有 `tests/test_scheduler*.py` / `tests/infrastructure/test_apscheduler_*.py` 全过；
新增测试断言"交易日路径下 `complete_run_skipped` 从未被调用"。

## UC-3 日历链降级：fail-open 照跑、但不静默（serves: FR-2）

**触发**：`quant.trading_calendar` 读不到 + provider 不可达 → 解析链走"周一~周五回退"
（`degraded=True`，工作日结论照用）。

**期望**：**照跑**（`skip=False`），且 run 的 `result` 里带 `degraded=true` 与真实 `source`
（如 `weekday_fallback`），日志一行 warning。**不许**把"日历不可用"当成休市。

**可观察读数**：该 run `status='success'`（真跑了）+ `result->>'degraded' = 'true'`。

## UC-4 复市首日：不得被跳过（serves: FR-2, FR-4, FR-8）

**触发**：`2026-10-08`（国庆后复市首日）09:25。

**期望**：`should_skip('trading-days', 2026-10-08T09:25)` → `False`（日历表覆盖到 2026-12-31，
该日是交易日）→ 照跑、`status='success'`。

**本节存在的理由（防写错口径）**：当天不能拿 `TradingDayGuard.check('2026-10-08')` 当判据——
它在 `10-06` 会返回 `source='future'` / `is_trading_day=False`（**写入型路径刻意保守**），
照着它写验收会把好代码判成 bug。当天可跑的正确判据是：
```bash
./venv/bin/python -c "
from datetime import date
from application.services.trading_day_resolver import resolve_trading_day as r
print(r(date(2026,10,8)).date == date(2026,10,8))"   # 期望 True
```

## UC-5 休市日的人工触发：仍然跑（serves: FR-6）

**触发**：休市日人工 `POST /api/scheduler/tasks/250/trigger`。

**期望**：
1. 路由 → `trigger_task_now(250)` → 投递一次性 job（`kwargs={'manual': True}`）；
2. executor 收到 `manual=True` → **不判门** → 正常执行 → `status='success'`；
3. 人工可查该 run（真执行记录），且**没有** `skipped` 行（人工那次不该被记成"跳过"）；
4. `task_250` 的 cron `next_run_time` **未被扰动**（与旧实现的关键差异）。

**可观察读数**：`scheduler.get_job('task_250').next_run_time` 与触发前一致；
`get_jobs()` 中出现过 `manual_250_*`（执行后自动消失）。

## UC-6 `#232` 的周末分档：周六照跑、法定节假日跳过（serves: FR-5）

**触发**：`2026-10-03`（周六）00:00 与 `2026-10-06`（国庆休市·周二）00:00。

**期望**：
- 周六：`source='weekend'` → 策略 `holidays` **不满足跳过条件** → **照跑**（`success`）；
- 法定节假日：`source='trading-calendar-holiday'` → **跳过**（`skipped`）。

**为什么这条必须单测**：这是 D-6 的裁定落地，也是"一刀切按交易日"会踩的坑
（`#253` 周六 / `#262` 周日排班的任务若被一刀切会**永不执行**）。

## UC-7 策略值未知：fail-open 照跑并留痕（serves: FR-1, FR-2）

**触发**：库中 `trading_day_policy` 被人工改成 `'holiday'`（少个 s，CHECK 之外的历史脏数据）。

**期望**：`should_skip` 返回 `(False, info + policy_unknown=True)` → **照跑**、记 warning、
run 的 `result` 带 `policy_unknown: true`。**不静默、不跳过**。

## UC-8 巡检侧：休市日的 `skipped` 不产生"漏跑"告警（serves: FR-3）

**触发**：休市日之后跑活着的告警路径 `tools/health_probe.py`（内部调
`application/services/should_have_run.audit_should_have_run`，与 `tools/check_should_have_run.py` 同实现）。

**期望**：
1. 挂门任务的休市日槽位**不判 missed**（`skipped` 被显式认作"已按日历处理"）；
2. `missed` 列表里**不出现**这 8 条任务；
3. 呈现层"最近一次真执行"仍只认 `success` / `failed`（不把 `skipped` 当执行时刻）；
4. `scripts/scheduler_watchdog.py` 的 `success` 判据同步为 `success` 或 `skipped`。

**反例（必须一并断言）**：`missed`（该跑没跑）**仍然告警**——本设计只新增"正常跳过"的豁免，
绝不放宽真正的漏跑。

## UC-9 回滚：改回 `always` 即回到今天的行为（serves: FR-1, FR-7）

**触发**：上线后判定"跳过太激进"，需要回退。

**期望**：执行
```sql
UPDATE quant.scheduler_tasks SET trading_day_policy='always'
 WHERE id IN (250,247,242,259,249,261,237,232);
```
→ **立即**（无需 reload、无需重启）所有 8 条任务恢复"到点必跑"；
`skipped` 的历史行保留（可审计）；下次到点写回 `success`。
代码与列**都不用回滚**。
