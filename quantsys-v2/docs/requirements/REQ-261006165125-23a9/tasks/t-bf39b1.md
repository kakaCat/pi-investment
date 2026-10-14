# t-bf39b1 新建通知判据模块 notify_policy（无事判据 + env 解析）·研发

> 需求：REQ-261006165125-23a9 每日任务空结果不发飞书（no_event/skipped 静默）

## 在做什么
新建通知判据模块 notify_policy（无事判据 + env 解析）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T09:03:24.270Z，窗口 session-981b7858-34a5-4ea0-88c9-a7e2efb95886）

研发段：新建 notify_policy.py（108 行）判据模块，纯函数、零 IO、无跨层依赖。

### 完成项

- 新增 is_no_op 白名单判据（严格 no_output is True，其余一律外发）
- 新增 should_send_completion：manual／回滚态／无事／有产出四分支
- 新增 notify_noop_enabled 与 running_notice_seconds（坏值容错，0 表示关闭提示）
- 四条验收命令与层边界 grep 全过
- 阶段模板给的 vitest 命令不适用本仓 Python 栈，已用 python -c 等价自证

### 改动文件

- `adapters/inbound/fastapi_app/daily_jobs/notify_policy.py`

### 下一步

复核段：按 design/interfaces.md §1 逐条比对签名与语义

---
