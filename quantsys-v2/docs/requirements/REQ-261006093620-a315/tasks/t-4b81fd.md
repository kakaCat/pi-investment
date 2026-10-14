# t-4b81fd 仓储层：complete_run_skipped + 抽 _finish_run·联调

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
仓储层：complete_run_skipped + 抽 _finish_run·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-06T01:58:18.880Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

联调段完成：18 处既有调用方零改造，75 条用例全过，真库往返已验。

### 完成项

- 调用方清点：仓内 complete_run( 共 18 处调用，签名与返回值未变，零调用方改造
- 回归全绿：基线 67 条 + 新增 8 条 = 75 passed（含结果 JSON 安全与内层失败用例）
- 真库往返已验：skipped 能写进 scheduler_runs，completed_at 落盘、last_error 为 NULL
- 托管伪任务（cron=managed_by_agent_os）的 next_run_at 不被重算，既有语义保持
- 无破坏性改动：complete_run 仍只映射 success / failed 两态

### 下一步

复核段：核对收尾逻辑唯一性与两态异常策略差异。

---
