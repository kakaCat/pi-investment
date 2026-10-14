---
id: v13-chain-reliability-audit
title: V13 链路可信性设计的独立审计结论（L2）
summary: a7cd 那套「声明=记录=实际」的设计，哪些真落地、哪些只是文档；照它继续干之前必须先补的三件事。
type: architecture
status: living
updated: 2026-10-06
owners: [project]
tags: [v13, audit, reliability, scheduler, observability]
---

# V13 链路可信性设计的独立审计结论（L2）

> 来源：REQ-261006010812-cd19（只读审计）｜被审对象：REQ-261004154902-a7cd 的 6 份设计文档 + 其落点实现。
> 过程与逐条证据（L3）：[`../requirements/REQ-261006010812-cd19/audit-report.md`](../requirements/REQ-261006010812-cd19/audit-report.md)
> 与同目录 `evidence/a1~a4`。审计时刻：2026-10-06 09:2x–09:5x（CST）。

## 1. 结论一句话

**整体判定：已实现但语义偏离。** 26 个设计落点中 12 条一致、8 条语义偏离、5 条未实现、1 条无法判定 ——
主干（结果契约、日历真源、宽限语义、配置单源、通知兜底）确实落地；但**三类问题仍在**：
记账口径没贯通到生产路径、回滚与判据的载体不在版本控制内、设计没管住的三条链路仍是坏的。

## 2. 三条必须先处理（P0）

### 2.1 「跳过」在调度路径上仍被记成 success

- **事实**：`quant.scheduler_runs` id=3375（2026-10-05 **休市日** 14:37）`status='success'`，
  而其 `result.details.details.check.status='skipped'`、`reason='not_trading_day'`。
- **为什么**：三态映射只做在 `application/services/strategy_service.py:375-377`（策略服务路径）；
  生产调度走的是 `application/jobs/trading_jobs.py:52 → application/jobs/job_protocol.py:43-50`，
  那段只把 `failed/error/fail` 判失败，**其余一律 `JobResult.ok`**。
- **后果**：休市日/未到周期/模型没加载这些"没干活"的情形，在台账上仍是一片绿 —— 正是 a7cd 要消灭的假绿。
- **复核**：
  ```bash
  venv/bin/python -c "import psycopg2;c=psycopg2.connect(host='localhost',port=5432,dbname='quant_investment');cur=c.cursor();cur.execute(\"select status, result->'details'->'details'->'check'->>'status' from quant.scheduler_runs where id=3375\");print(cur.fetchone())"
  # 期望 ('success', 'skipped')
  ```

### 2.2 设计声明的回滚路径不成立

- **事实**：`design.md:289` 写「回滚 = `git revert` 对应提交」，但 a7cd 的实现**从未提交**：
  20 个受改文件为 `M`、5 个新模块为 `??`；**整个需求目录**（6 份设计文档 + 67 张任务卡）也是 `??`。
  实际留档载体是 `notes/code-changes-2026-10-04.patch`（只含已跟踪文件的改动）+
  `notes/code-snapshot-2026-10-04.tar.gz`（含新模块）。
- **复核**：
  ```bash
  git status --porcelain -- docs/requirements/REQ-261004154902-a7cd   # ??（整目录未跟踪）
  git ls-files --error-unmatch application/observability/run_outcome.py  # pathspec 不匹配
  git check-ignore -v tools/check_should_have_run.py                 # .gitignore:85:check_*.py
  ```

### 2.3 判据载体缺失

- `tools/check_trading_day_judgment.py`（`design.md:308` 的 FR-3 验收命令）**不存在**；
  `tools/check_should_have_run.py` / `check_strategy_config_effective.py` / `check_v13_chain_health.py`
  被 `.gitignore:85`（规则 `check_*.py`）排除 → 判据只活在本机工作区；
  设计的灰度开关 `V13_CHAIN_STRICT` 在代码里 **0 命中**（未接线）。

## 3. 其余需要知道的（P1/P2）

- **盘点器没接交易日历**：`tools/check_should_have_run.py` 按 cron 工作日语义推演「应跑」，
  休市日的排班缺失会被报成「漏跑」（实测 exit 2，漏跑 = `daily-strategy-validation`，
  而 2026-10-05 是休市）。与「休市不开火」的口径未对齐。
- **超卖判据被替换但文档没同步**：设计写「超卖清单必须 0 行」，实际用「已登记脏数据排除」
  把对账器做成 exit 0；raw SQL 仍 4 行（300045/300469/300561/300765）。
- **设计未覆盖的三条链路**（a7cd 现状取证里列了 E15/E16，但设计文档 0 命中）：
  ① `risk_check_job` 调不存在的方法 + 账户写死 `default` + 未排班；
  ② `verification_job` 同病 + `predicted_return = 0.12  # TODO`；
  ③ 盘中无 V13 止损（`intraday_monitor.py:77` 写死 `rotation_main`，`rule_guard` 拒绝策略账户）。
- **`missed` 落库零实证**：`_on_job_missed` 已写 `record_missed_run`，但全库 `scheduler_runs`
  只有 success/failed/cancelled，**无 missed 行**；启用 11 条任务中仅 1 条宽限为 NULL。
- **声明失真在 v13 之外仍在**：`v14.yaml factors_count: 75` vs 真实 78；
  `config_simulation.yaml` 注释仍称「v13 链路生效 8」，而 `v13.yaml top_n: 5`。

## 4. 审计方法论（可复用）

- **五个取证面**：设计文档面 / 代码面（`文件:行`）/ 库表面（只读 SQL + 时刻）/ 运行面（实跑退出码）/ 版本面（git）。
  面 A 出条目，其余出证据，**不允许单靠设计文档下「已实现」判定**。
- **四档判定**：已实现且一致 / 已实现但语义偏离 / 未实现 / 无法判定（禁用「基本一致」这类连续语气）。
- **证据强度 L1-L4**：可复跑命令 > 静态定位 > 库/日志快照 > 代码推演；**弱证据不得支撑强结论**。
- **只读边界**：生产库/进程只读；允许跑 pytest（落 `quant_test`，用成对计数证明生产库未变）。
