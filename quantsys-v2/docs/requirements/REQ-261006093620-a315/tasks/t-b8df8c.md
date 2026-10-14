# t-b8df8c 仓储层：complete_run_skipped + 抽 _finish_run·复核

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
仓储层：complete_run_skipped + 抽 _finish_run·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T01:58:25.568Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

复核段完成：三态收尾唯一、异常策略差异有测试锁定、对上设计三态契约；并登记一处既有近似重复（不在本次范围）。

### 完成项

- 三态收尾唯一性核实：complete_run 与 complete_run_skipped 都只调 _finish_run，无第二份实现
- 异常策略差异已刻意化并有测试锁：complete_run 上抛、complete_run_skipped 吞掉返回 False
- 登记既有近似重复（不在本次范围）：recover_orphan_runs 自己批量写 duration_ms，事务形状刻意不同，未强行合并
- last_error 语义核实：跳过恒为 None，与 failed 可区分
- 对照 design/data-model.md §5 三态契约逐条核对：结论无偏离

### 下一步

测试段：重跑本卡验收命令与回归基线。

---
