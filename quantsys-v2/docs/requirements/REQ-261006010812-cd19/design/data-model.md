---
req: REQ-261006010812-cd19
kind: design
doc: design/data-model
title: 被审数据面——只读清单、查询口径、零写入
serves: FR-2, FR-3, FR-4
---

# 数据面设计（REQ-261006010812-cd19）

> 审计**读**数据以证事实，**不写**任何数据；无写入 ⇒ 无迁移、无回滚需求。

## 1. 只读数据面清单（serves: FR-2, FR-3, FR-4）

- **serves: FR-2, FR-3, FR-4**
- 只碰这 6 张表（均在生产库，只读 `SELECT`），每张对应被审设计的一处声明：

| 表 | 读它证哪条设计声明 | 关键列 |
|---|---|---|
| `quant.scheduler_tasks` | FR-4 时刻口径与宽限（`design.md` §4 / `data-model.md` §3） | `id, name, command, cron_expression, misfire_grace_time_seconds, is_enabled` |
| `quant.scheduler_runs` | 日检成败留痕（`design.md` §2、§8） | `task_id, status, started_at, result, error` |
| `quant.simulation_pending_orders` | 挂单不搁浅 / `expired` 取值（`design.md` §7） | `id, account_name, status, fail_reason, created_at, updated_at` |
| `quant.simulation_trades` | 账本净额与超卖（`design.md` §10） | `account_name, symbol, action, shares, price` |
| `quant.simulation_positions` | 双源并存的证据（`data-model.md` §4） | `account_name, symbol, shares` |
| `quant.simulation_account` | 现金重放比对（`data-model.md` §4） | `account_name, cash_available, last_rebalance_date` |

- 备用只读表：`quant.trading_calendar`（仅当需要核对「某日是否有行」时读，见 `design.md` §3）。
- **不读**：任何与 V13 链路无关的表；不做跨库聚合；不导出数据落到新表。

## 2. 查询口径（serves: FR-2, FR-3）

- **serves: FR-2, FR-3**
- 连接：沿用仓根 `.env` 的 `PG*` 变量（生产库 `quant_investment`）；
  **不得**在 pytest 之外触发测试库自动切换逻辑（本审计的 SQL 一律显式连生产库只读）。
- 每条库证据必须记：**库名 + 查询语句 + 执行时刻（分钟级）**——数据会随时间变化，缺时刻即不可复核。
- 聚合口径固定：
  - 净额 = `sum(case when action='BUY' then shares else -shares end)`，按 `account_name, symbol` 分组；
  - 超卖清单 = 上述净额 `< 0` 的行；
  - 「该跑没跑」不自行另写 SQL 口径，直接复用被审设计的 `tools/check_should_have_run.py` 输出（避免第二个口径）。
- 库不可达（连接失败/权限不足）时：**结构化报出**（错误原文 + 尝试的库名），
  相关判定一律落 `无法判定` 并在证据列写缺口，**不得**用代码推演冒充库事实。

## 3. 零写入声明与"回滚"（serves: FR-2, FR-5）

- **serves: FR-2, FR-5**
- 本设计**无 DDL、无 DML**：不建表、不改列、不写行、不迁移。
- 因此「迁移与回滚」在数据面上是**空操作**；唯一的"回滚"诉求是审计过程的只读性回归：
  审计结束后 `git status --porcelain` 对被审代码文件的输出与开审前一致（`test-cases.md` §4）。
- pytest 例外说明：跑测试会写**测试库** `quant_test`（根 `conftest.py` 有库名守卫，非 `_test` 结尾即拒绝）。
  这属 D-3 允许的实跑动作，且**不触碰生产库**；报告须声明所跑测试的连接目标。

## 4. 数据面的三个"事实陷阱"（serves: FR-2, FR-4）

- **serves: FR-2, FR-4**
- ① **时间点漂移**：`scheduler_runs` 会随每次调度新增行 → 同一查询在不同时刻结论可能不同，
  故库证据必须带时刻，且结论写成"截至 <时刻>"；
- ② **双源并存**：`simulation_positions` 与 `simulation_trades` 是两个口径（被审设计 §4 已认定
  `trades` 为唯一真源）→ 审计核对时必须写明以哪个为准，冲突本身就是要报的发现；
- ③ **归档后仍在动**：被审需求已归档，但生产仍在按现有代码跑 → "设计说 X、库里是 Y"既可能是没实现，
  也可能是归档后有别的需求改了它。判定前必须查该文件的最近提交（面 E）与提交信息，
  不能把"后来者改动"误判成"设计没落地"。
