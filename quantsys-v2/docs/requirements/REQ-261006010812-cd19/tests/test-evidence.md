# 测试与复跑证据 · REQ-261006010812-cd19

> 说明：本需求为**只读审计**，不新增产品代码与产品测试；本文件记录的是**判据实跑**（审计自身的可执行证据）。
> 执行时刻：2026-10-06 09:2x–09:5x（CST）｜ 原始日志：`/tmp/cd19/C{1..7}.log`（本机路径）。

## 1. 被审设计的验收命令逐条实跑

| # | 命令 | 实跑? | 退出码 | 输出摘要 |
|---|---|---|---|---|
| C1 | `venv/bin/python -m pytest tests/live_trading/ tests/test_v13_scheduler.py -q` | 实跑 | 0 | `36 passed in 1.42s`；`notify-guard intercepted=0 egress=0` |
| C2 | `venv/bin/python tools/check_trading_day_judgment.py --dates 2026-10-05,2026-10-06,2026-10-07,2026-10-08` | **不可跑** | - | `[Errno 2] No such file or directory`（该工具不存在） |
| C2' | 替代判据（纯函数冻结 today） | 实跑 | 0 | `2026-10-05/06/07 → False`、`2026-10-08 → True`（4/4 与设计意图相符） |
| C3 | `venv/bin/python tools/check_should_have_run.py` | 实跑 | **2** | `启用任务 11 / 漏跑 1 / 改动豁免 10`；漏跑 = `daily-strategy-validation` |
| C4 | `venv/bin/python tools/check_strategy_config_effective.py` | 实跑 | 0 | `声明 == 生效`（rebalance_days 5 / top_n 5 / 止损 -0.15） |
| C5 | `venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py -q` | 实跑 | 0 | `10 passed in 0.57s` |
| C6 | `venv/bin/python -m pytest tests/services/test_pending_orders.py -q` | 实跑 | 0 | `28 passed, 1 warning in 2.04s` |
| C7 | `venv/bin/python tools/reconcile_sim_account.py --account v13_simulation` | 实跑 | 0 | 结论「✅ 自洽」；已排除 4 只已登记脏数据（raw 口径仍 4 行） |

小计：实跑 6 条（含 1 条替代判据）、不可跑 1 条；pytest 合计 `74 passed`，0 failed。

## 2. 写入面测量（证明只写测试库）

| 表 | 跑前 prod | 跑后 prod | 跑前 test | 跑后 test |
|---|---|---|---|---|
| `scheduler_runs` | 3155 | **3155** | 0 | 0 |
| `scheduler_tasks` | 33 | **33** | 0 | 0 |
| `simulation_trades` | 78 | **78** | 0 | 0 |
| `simulation_pending_orders` | 7 | **7** | 0 | 0 |

方法：计数 → 跑 `pytest tests/regression/test_strategy_config_refactor.py -q`（10 passed）→ 再计数。
结论：生产库逐字不变，测试库保持 0 行；本审计的实跑动作未触碰生产数据。

## 3. 审计报告自身的判定（机器可跑）

```bash
cd docs/requirements/REQ-261006010812-cd19
grep -c '^## ' audit-report.md                     # 7  (>=5)
grep -cE '<设计 interfaces.md §2 的 5 个禁用表述>' audit-report.md   # 0
sed -n '/^## 一致性矩阵/,/^## 验收/p' audit-report.md | grep -cE '^\| (design|test-cases)'   # 26
sed -n '/^## 改进项/,/^## 逐条/p' audit-report.md | grep -cE '^\| .*\| P[0-2]'               # 9
grep -cE '^\| [0-9] \| M-.*通过' audit-report.md     # 5  (抽查 5/5 通过)
```

## 4. 只读性回归

```bash
cd /Users/mac/Documents/ai/pi-investment
git status --porcelain | wc -l                                  # 开审前 128 → 收工后 129
git status --porcelain | grep -v 'REQ-261006010812-cd19' | wc -l # 128（含另一窗口的新需求 + 生产日志）
git status --porcelain -- quantsys-v2/live_trading/simulation_trader.py \
  quantsys-v2/application/observability/run_outcome.py           # 与 a1 记录逐字一致
```

差量归属（逐项查明）：本需求目录 1 项；**另一窗口**于 2026-10-06 09:36:20 新建的
`docs/requirements/REQ-261006093620-a315/`；以及生产 API/探针在跑导致的 `logs/*` 增长。
被审对象（a7cd 的 20 个 ` M` 文件与 5 个 `??` 新模块）状态未变。

结论：审计未给被审代码/文档加任何改动（全仓计数的变化已逐项归属）。

## 5. 未执行的测试（如实声明）

- `kill -9` 生产 API 验探活告警：**未执行**（D-3 禁止生产副作用）→ 报告中判 `无法判定`。
- 制造一次 scheduler missed 事件验落库：**未执行**（同上）→ 报告中判 `无法判定`。
- 真实飞书外发验证：**未执行**（同上）→ 只做静态定位与渠道选择逻辑核对。

## 6. 任务覆盖声明（covers）

> 本需求为只读审计，每张卡的「验收」就是其对应证据的**可复跑性**；下列 covers 行把卡与证据项绑定。

- covers: t-9f0fbe —— 设计自洽性与版本面：`evidence/a1-design-selfconsistency.md`（19 条结论 + 57 路径全量表）
- covers: t-e2e068 —— a1 取数：228 个数据点（57 路径 × 4 项检查）
- covers: t-83047e —— a1 分析：15 条自洽性条目 + 4 条面 E 硬结论
- covers: t-69aedb —— a1 复核：7 项关键结论独立重查全过（D-Doc-1）
- covers: t-3c2fb0 —— 一致性矩阵：`evidence/a2-impl-matrix.md`（26 落点四档判定）
- covers: t-947815 —— a2 取数：25 个符号检索 + 9 条生产库只读查询
- covers: t-2b228e —— a2 分析：12/8/5/1 判定分布 + 4 条被证伪假设
- covers: t-db3def —— a2 复核：M-06/M-12/M-23/M-25 四条重判定独立成立
- covers: t-881157 —— 复跑与库事实：`evidence/a3-calldb-replay.md`（C1~C7 + 9 条库证据）
- covers: t-7b8637 —— a3 取数：7 条命令实跑 + 成对计数测量（§1/§2）
- covers: t-ba6005 —— a3 分析：5/7 与设计期望相符 + 4 条被证伪假设
- covers: t-003c90 —— a3 复核：C3/C4 重跑稳定、计数逐字一致、C2 替代判据通过
- covers: t-9adb94 —— 缺口清单：`evidence/a4-gaps.md`（8 条，高 4/中 3/低 1）
- covers: t-1e2867 —— a4 取数：G-1~G-8 三类证据（代码/库/设计覆盖度反证）
- covers: t-539d6c —— a4 分析：定级与覆盖归属（设计未覆盖 4 条）
- covers: t-9faa06 —— a4 复核：8 项重查成立（含 G-1 口径补精）
- covers: t-e7f33f —— 报告汇总：`audit-report.md` 五节契约
- covers: t-3118e8 —— 报告成文：矩阵 26/复跑 7/缺口 8/改进项 9
- covers: t-9c82c7 —— 报告复核：S1/S2/S3 + 抽查 5/5 + 只读性回归（§3/§4）

## 7. 返工覆盖声明（v2，covers）

- covers: t-b3d14a —— 返工父卡：四份证据文件的「可执行复核」节均落地（a1 §5 / a2 §5 / a3 §8 / a4 附录）
- covers: t-587b54 —— a1 §5：置信度分级命令 + 边界验法 + 3 条被证伪假设的支撑命令
- covers: t-dc82bd —— a2 §5：M-06 等 5 条 SQL 复核 + M-23 双口径强制 + 4 条假设 SQL
- covers: t-adf822 —— a3 §8：C1~C7 复核命令与期望退出码 + 替代判据边界 + 4 条假设命令
- covers: t-bdfea6 —— a4 附录：风险等级与覆盖归属的验法 + 3 条假设命令
