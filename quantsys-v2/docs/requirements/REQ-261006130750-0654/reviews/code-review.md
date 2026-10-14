# 独立复核报告（REQ-261006130750-0654）

**复核者**：本窗口 agent（独立于各卡研发自述：逐条重跑探针与命令）
**复核对象**：`adapters/inbound/fastapi_app/orchestrator_bootstrap.py`、
`application/services/intraday_monitor.py`、`tests/api/test_orchestrator_trading_day_gate.py`
**结论**：**通过**（无阻断偏离）；1 处**设计记载不全**、1 处**设计取舍残留**、3 处低影响观察。

## 1. 逐条对照设计

| 设计条目 | 复核方式 | 结果 |
|---|---|---|
| interfaces §2.1 helper 契约 | 读码 + 探针 `_should_run_today(2026-10-06)=False`、`(2026-09-30)=True` | ✅ |
| interfaces §2.3 主循环两分支 | 周六探针：窗口 False ⇒ 门**不被调用**（行为不变） | ✅ |
| interfaces §3.2 `check(now=…)` 兼容 | 既有唯一生产调用方 `monitor_jobs` 未改；真库探针返回 `non-trading-day` | ✅ |
| interfaces §3.3 判定顺序（严格增量） | `check(now=20:00)` → 既有 `not trading time` | ✅ |
| interfaces §5 静态不变量 | `grep should_skip` = 4（≥2）；新增逻辑零 `weekday()` | ✅ |
| design §4 唯一真源 | 两处调用点均调 `trading_day_gate.should_skip`，无第二份日历判定 | ✅ |

## 2. 复核发现

| 编号 | 级别 | 内容 | 处置 |
|---|---|---|---|
| **F1** | 中（设计记载不全） | 设计 R3 称「唯一生产调用方是 `monitor_jobs`」——**不成立**：`application/services/scheduler_tasks_runtime.py:30` 的 `handle_intraday_monitor` 也调 `check()`，且它把 `skipped` 包成外层 `status='success'`（与 a315 治过的"假成功"同型） | **不改**（超出本卡边界）；当前**无启用任务接线**（DB 无 `intraday_monitor` 任务行），登记为后续项 |
| **F2** | 中（设计取舍残留） | `resume_from_breakpoint()` 与内层 `tick()` 仍走 **fail-closed**；日历覆盖断档时（`quant.trading_calendar` 只到 2026-12-31）休市日仍会跑 —— 这是 fail-open 取舍的**唯一残余路径** | **不改**（改内层＝用 fail-open 覆盖钱路 fail-closed）；修它要动日历自动补刷（需求后续线 2） |
| F3 | 低 | 交易日每分钟会先过 A 层门、再由内层自查一次 → 两次判定查询/分钟；被守卫 60s 日期缓存吸收 | 登记 |
| F4 | 低 | B 层（`check()`）跳过日志未去噪（旁路 10 次/天 = 10 条）；A 层已按 `(path, day)` 去噪 | 登记 |
| F5 | 低（流程） | 任务卡 acceptance 模板为 JS 栈（`npx vitest` / `pnpm test` / `npx tsc`），本仓是 Python，执行时改用 pytest 等价口径并逐卡如实报出 | 登记（建议上游修模板） |
| F6 | 低（流程） | 计划文件清单未列 `tests/api/test_orchestrator_bootstrap.py`，但需求 FR-4 已预先授权「补最小桩」；实际补了 2 处「今天是交易日」桩 | 登记 |

## 3. 反向证据（不支持"改得很好"的一面）

- **门只省调用，不新增能力**：它不会让休市日"更正确"，只是**不再假装干活**；真正的正确性来自 ②③ 已有的门与日历本身。
- **残余风险仍在日历侧**：覆盖断档（F2）会让三条件路径同时回退到"周几口径"——本需求只保证**外层照跑 + 响亮**，不保证"永不复发"。
- **`handle_intraday_monitor` 的假成功形态**（F1）在接线那一刻就会重现：这是**未来**的雷，不是已修的洞。

## 4. 复核用原始读数

```
_in_intraday_window(2026-10-06 10:30) = True        （时段层放行——拦它的是日级门）
TradingDayGuard.check('2026-10-06') → False / trading-calendar-holiday / degraded=False
_should_run_today(2026-10-06 12:30) = (False, trading-calendar-holiday)
_should_run_today(2026-09-30 12:30) = (True,  trading-calendar)
_LAST_SKIP_LOG = {'orchestrator_tick': '2026-10-06', 'intraday_monitor': '2026-10-06'}
周六探针：_in_orchestrator_window(2026-10-10 12:30)=False → 门未被调用、日志键为空
生产留痕：13:21:44 orchestrator_tick / 13:30:46 intraday_monitor（均 degraded=false）
写库面：simulation_positions 最新 2026-10-04；rotation_main 2026-07-25；orchestrator_state(10-06)=0 行
```
