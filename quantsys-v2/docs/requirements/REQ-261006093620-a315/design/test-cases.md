# 测试策略（REQ-261006093620-a315）

## 1. 测试分层与文件归属（serves: FR-8）

| 层级 | 文件 | 覆盖什么 | 跑法 |
|---|---|---|---|
| 单元（判据） | `tests/test_scheduler_trading_day_gate.py`（新建） | 策略 × 日期条件的**真值表**；fail-open 四条降级路径 | `./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q` |
| 单元（口径锁） | 同上 | `future` 反例锁、未知策略 fail-open | 同上 |
| 集成（执行期） | `tests/infrastructure/test_scheduler_skip_ledger.py`（新建） | 休市日落 `skipped`、`manual=True` 照跑、交易日路径不跳 | `./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q` |
| 集成（人工旁路） | `tests/infrastructure/test_apscheduler_service.py`（改） | `trigger_task_now` 投递 `manual=True` 一次性 job；不动 cron 排期 | `./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q` |
| 集成（巡检口径） | `tests/test_should_have_run.py`（**既有，24 个用例；增量补**） | `skipped` 不算漏跑、也不算真执行；`missed` 仍告警 | `./venv/bin/python -m pytest tests/test_should_have_run.py -q` |
| 回归（③ 不回归） | `tests/test_daily_jobs_trading_day_gate.py`（**改打桩点**） | ③ 的语义逐字不变（含打桩点迁移后仍真生效） | `./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q` |
| 回归（既有调度） | `tests/test_scheduler_duplicate_prevention.py`、`tests/test_scheduler_misfire_semantics.py`、`tests/test_scheduler_inner_failure.py`、`tests/test_scheduler_run_result_json.py` | 撞点/宽限/内层失败/JSON 安全语义不被破坏 | 一并跑 |
| E2E（真实台账） | 无代码：两条 SQL 观察 | `2026-10-07` 休市 → 8 条 `skipped`、无通知；`2026-10-08` 复市 → 恢复 `success` | 见 §4 |

**先查清承载文件再动手**：写 `should_have_run` 的用例前先
`grep -rl "should_have_run" tests/` 确认既有测试文件，**增量补用例**而不是新起一个平行文件
（本仓有"两份真相"的教训）。

## 2. 判据真值表（单元测试的主表）（serves: FR-1, FR-2, FR-4, FR-5）

用**表驱动**把策略 × 日期条件 × 降级 的笛卡尔积写全，桩打在
`application.services.trading_day_gate.TradingDayGuard`（**不是** `daily_jobs.gate`，见 §3）：

| # | policy | 判定注解（stub 注入） | 期望 skip | 覆盖的裁定 |
|---|---|---|---|---|
| 1 | `always` | 任意（含 `holiday`） | **False** | 缺省=行为不变 |
| 2 | `trading-days` | `is_trading_day=False, source='trading-calendar-holiday', degraded=False` | **True** | FR-4 挂门任务 |
| 3 | `trading-days` | `is_trading_day=False, source='weekend', degraded=False` | **True** | 语义一致性（对 `1-5` 任务不可达） |
| 4 | `trading-days` | `is_trading_day=True, source='trading-calendar'` | **False** | UC-2 / UC-4 |
| 5 | `trading-days` | `is_trading_day=False, source='weekday_fallback', degraded=True` | **False** | FR-2 fail-open |
| 6 | `trading-days` | `is_trading_day=False, source='unavailable', degraded=True` | **False** | FR-2 fail-open |
| 7 | `trading-days` | 判定器**抛异常** | **False**（+`source='gate-error'`） | 门自身异常不许停摆 |
| 8 | `trading-days` | `is_trading_day=False, source='future'` | **True** | 语义澄清（门永不喂未来日期；此行为仅作记录） |
| 9 | `holidays` | `source='trading-calendar-holiday', degraded=False` | **True** | FR-5 / UC-6 |
| 10 | `holidays` | `source='weekend', degraded=False` | **False** | **FR-5 的核心断言**（D-6） |
| 11 | `holidays` | `source='trading-calendar'` | **False** | 交易日照跑 |
| 12 | `holidays` | `source='trading-calendar-holiday', degraded=True` | **False** | 降级时连节假日也不跳（fail-open 优先） |
| 13 | `None` / `'holiday'`（未知） | 任意 | **False** + `policy_unknown=True` | UC-7 |

**#10 与 #12 是本表的存在理由**：其余各行都能靠"非交易日就跳"蒙对，
只有这两行把"只跳法定节假日"和"降级优先于跳过"钉死。

## 3. 打桩点迁移的验证（serves: FR-3, FR-8）

**风险**：`daily_jobs/gate.py` 变薄转发后，`tests/test_daily_jobs_trading_day_gate.py:80/131/139`
的 `monkeypatch.setattr(gate_mod, 'TradingDayGuard', ...)` 会**静默失效**（桩还在、真日历照跑）
——这正是 CLAUDE.md 的「打桩点规则」所指的故障形态。

**动作（与代码改动同批）**：
1. 三处 patch 目标改为 `application.services.trading_day_gate`（新模块）；
2. 保留 `gate_mod` 的导入以验证**薄转发仍然可用**（③ 的调用面不破）；
3. **证伪测试**：加一条断言——patch 新模块后，`daily_jobs.gate.skip_non_trading_day()` 的结论
   **确实被桩影响**。若这条红，说明转发链路上有一处名字解析没走新模块（桩失效），
   这正是要防的静默失效。

## 4. 验收口径（可跑命令 + 期望输出）（serves: FR-3, FR-4, FR-8）

```bash
# ① 新增判据单测
./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q          # 全过（13 行真值表）

# ② 执行期集成
./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q # 全过

# ③ ③ 不回归（含打桩点迁移）
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q          # 全过

# ④ 既有调度回归
./venv/bin/python -m pytest tests/test_scheduler_duplicate_prevention.py \
    tests/test_scheduler_misfire_semantics.py tests/test_scheduler_inner_failure.py -q

# ⑤ 复市首日判据（当天即可跑，不必等 10-08）
./venv/bin/python -c "
from datetime import date
from application.services.trading_day_resolver import resolve_trading_day as r
print(r(date(2026,10,7)).date == date(2026,10,7), r(date(2026,10,8)).date == date(2026,10,8))"
# 期望：False True

# ⑥ future 反例锁（防止有人拿它当"复市首日"判据）
./venv/bin/python -c "
from application.services.trading_day_guard import TradingDayGuard as G
v = G.check('2026-10-08'); print(v.is_trading_day, v.source)"
# 期望：False future
```

**真实台账观察（E2E，改完的次日休市日即可取数）**：

```sql
-- 休市日（2026-10-07）：8 条挂门 = skipped，3 条不挂 = success
select t.id, t.name, t.trading_day_policy, r.status, r.result->>'reason' as reason
  from quant.scheduler_runs r join quant.scheduler_tasks t on t.id = r.task_id
 where r.started_at::date = '2026-10-07' order by t.id;

-- 复市首日（2026-10-08）：挂门任务恢复 success
select t.id, t.name, r.status, r.duration_ms
  from quant.scheduler_runs r join quant.scheduler_tasks t on t.id = r.task_id
 where r.started_at::date = '2026-10-08' and t.trading_day_policy <> 'always' order by t.id;
```

## 5. 负向测试（必须一并写，否则"过"没有意义）（serves: FR-3）

| # | 断言 | 为什么必须 |
|---|---|---|
| N1 | 休市日跳过时 `_execute_command` **未被调用** | 防"落了 skipped 但其实照跑了" |
| N2 | 休市日跳过时**未调用** `_report_failure_to_sink` / **未**上报 Agent OS | FR-3 的"不打扰" |
| N3 | 跳过行的 `last_error IS NULL` | 跳过不是失败 |
| N4 | 交易日路径 `complete_run_skipped` **从未被调用** | 防门误伤交易日 |
| N5 | `missed`（真漏跑）**仍然**进 `should_have_run` 的 missed 列表 | 只豁免正常跳过，不放宽真漏跑 |
| N6 | `manual=True` 时**不调** `should_skip`（或调用结果被忽略） | FR-6：人工必须能跑 |
| N7 | 迁移脚本在**空表**上跑 verify 段不抛 | 测试库 `scheduler_tasks` 是空的（历史踩过 `row[0]` TypeError） |

## 6. 不写测试的地方（刻意）(serves: FR-4)

- **不为"哪个任务该挂哪个策略"写行为测试**：它是**配置数据**，由迁移回填 + 一条
  "回填后 8 行策略值逐一等于期望"的数据断言即可（写成行为测试会变成同义反复）。
- **不测 cron 表达式**：本设计不改排班；cron 语义由 `test_scheduler_duplicate_prevention.py`
  等既有用例守着。
