# t-7a9c7e 变更 task 232 阈值配置并实跑复验出证据·测试

> 需求：REQ-261006163444-8e4f 数据质量告警去伪：D级计数按当日行数重复计数 + 检查域混入退市股

## 在做什么
变更 task 232 阈值配置并实跑复验出证据·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T08:56:25.043Z，窗口 session-efbdbfc6-d84c-4d09-9829-b1c906699db5）

测试段完成：相关 59 条用例全绿，实跑未产生测试外发。

### 完成项

- pytest 四文件 -q → 59 passed（本卡未改代码，回归即证据）
- 实跑为网络真跑，测试期未触发通知外发（notify_guard 会话输出 intercepted=0）
- 如实声明：子卡模板给的是 pnpm test（本仓 Python），实际用 pytest 自证

### 改动文件

- `docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md`

---
