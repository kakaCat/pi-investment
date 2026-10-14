# t-ee89ed 落库两列 + 通知变量透传·测试

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
落库两列 + 通知变量透传·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-07T11:13:49.715Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t8 测试段完成：6 passed，三条验收判据齐备。

### 完成项

- tests/services/test_watch_trigger_escalation_columns.py → 6 passed
- 验收三条齐备：deduped 与 auto_observed 行码非 NULL；写库失败不阻断通知且 stdout 留痕；不传码为 NULL
- 测试库零残留（规则 0 / 触发 0）
- notify-guard intercepted=0 egress=0

### 下一步

父卡 t-fc92ab 收尾。

---
