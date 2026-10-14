# t-a60ba4 落码表与裁决结果契约（EscalationCode + Verdict）·测试

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
落码表与裁决结果契约（EscalationCode + Verdict）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-07T10:47:40.043Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

测试段完成：本卡验收命令 4 passed，整文件 9 passed，零真实外发。

### 完成项

- pytest tests/services/test_watch_escalation_verdict.py -q → 9 passed
- pytest ... -k code_table → 4 passed, 5 deselected（本卡验收命令）
- notify-guard intercepted=0 egress=0（零真实外发）
- 如实声明：子卡模板里的 npx vitest/pnpm test 是本插件的前端默认段，与本仓栈不符；本卡真实判据为 pytest

### 下一步

父卡 t-d24cfb 收尾（4 段子卡全部完成）。

---
