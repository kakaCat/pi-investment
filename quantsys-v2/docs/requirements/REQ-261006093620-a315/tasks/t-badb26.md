# t-badb26 人工触发改投一次性 manual=True job·复核

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
人工触发改投一次性 manual=True job·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T02:01:27.543Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

复核段完成：modify_job 调用点归零、一次性 job 唯一性成立，对照设计无偏离。

### 完成项

- 无遗留：infrastructure/ 与 adapters/ 下 modify_job 调用点归零
- 一次性 job 以 epoch 为后缀（manual_{task_id}_{epoch}），连续人工触发不会互相覆盖
- 重复触发的语义符合设计：每次都是独立一次性 job，replace_existing=False
- 对照 design/interfaces.md §4 逐条核对：机制、id 约定、异常语义、副作用（不再扰动排期）逐条一致
- 结论：无偏离

### 下一步

测试段：重跑本卡验收与合并回归。

---
## 汇报 2（2026-10-06T02:01:39.760Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

更正：\u300cmodify_job 调用点归零\u300d的结论成立，但上一条汇报的 grep 口径把 docstring 提及算成了命中；精确口径 .modify_job( 为 0。

### 完成项

- 更正上一条汇报的检查口径：我用 grep modify_job 得到的 2 处命中，全部是我新写的 docstring 里对旧实现的说明（第 459/461 行），不是调用点
- 精确口径复核：grep 实际调用形式 .modify_job( 在 infrastructure/ 与 adapters/ 下命中数为 0
- 结论不变（调用点已归零），但上一条汇报把粗口径计数当成结论陈述，属检查方法不严，记此更正
- 教训：判据要用能区分「提及」与「调用」的模式（带点与左括号），否则会把注释算成代码

### 下一步

测试段：重跑本卡验收与合并回归。

---
