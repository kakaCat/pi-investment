# t-98ed3c 巡检口径同步：should_have_run 与 watchdog·复核

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
巡检口径同步：should_have_run 与 watchdog·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T02:04:24.029Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

复核段完成：发现并登记计划的一处范围错误（watchdog 第 390 行属 Agent OS、不改），只改该改的第 289 行并留警示；判据互斥与拼接安全均核实。

### 完成项

- 偏离登记（计划写错一处）：计划称 watchdog 有两处 status=success 需改，实查第 390 行查的是 Agent OS 的 public.task_runs（另一套调度、无 skipped 语义），不属本需求范围
- 只改第 289 行（查 quant.scheduler_runs），并就地写入「不要一并改第 390 行」的警示注释
- 两套集合互斥性核实：skipped 进 HANDLED 不进 REAL；missed 两套都不进
- IN 拼接安全核实：取值来自模块常量并有 [a-z_] 白名单，非法字面量抛 ValueError
- 拒绝静默：门跳过的 reason 明写「已被交易日门按日历跳过」，不冒充真执行
- 对照 design/data-model.md §5 消费者矩阵逐条核对：should_have_run 与 watchdog 两行均已按矩阵落地，结论无偏离（除上述范围修正）

### 改动文件

- `scripts/scheduler_watchdog.py`

### 下一步

测试段：重跑本卡验收与相关回归。

---
## 汇报 2（2026-10-06T02:04:52.049Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

复核段完成（更正版）：watchdog 只改属本次范围的那一处，Agent OS 段保持原样；并登记需求作用域清单漏列根 scripts/ 的文档缺口。

### 完成项

- 更正上一条汇报的 files_changed：scheduler_watchdog.py 位于 monorepo 根 scripts/，**不在 v2 工作区内**，无法用工作区相对路径登记（上一条因此被凭证门拒绝）
- 该文件改动核验：compileall 通过；注入 croniter 桩后可 exec；v2 段新判据 status IN (success, skipped) 在位
- Agent OS 段未被误改：全文件仅剩 1 处 success-only 判据（即 public.task_runs 那处）
- 如实登记一处需求文档缺口：requirement.md 的作用域文件清单漏列了根 scripts/，而 FR-3/R3 明确点名该文件——属文档清单不全，不是范围蔓延
- 该模块自带测试在本机**从来跑不了**（venv 缺 croniter，10 个 error 全是 ModuleNotFoundError），非本次引入

### 下一步

测试段：重跑本卡验收与相关回归。

---
