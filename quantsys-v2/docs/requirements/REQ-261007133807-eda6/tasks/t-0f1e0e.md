# t-0f1e0e 卡面「升级原因」行（旧渲染 + 分级渲染两条路径）·测试

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
卡面「升级原因」行（旧渲染 + 分级渲染两条路径）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-07T11:13:49.818Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t9 测试段完成：6 passed，两条渲染路径与三种形态全覆盖。

### 完成项

- tests/notification/test_watch_escalation_reason_line.py → 6 passed
- 覆盖：两条路径同形 / 只有码 / 都没有不渲染 / 未收录码显示码 / 行序 / 变量透传
- notify-guard intercepted=0 egress=0

### 下一步

父卡 t-ba3f1f 收尾。

---
