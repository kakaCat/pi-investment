# t-fff73f 收敛出唯一裁决出口 decide_escalation（15 条顺序表）·测试

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
收敛出唯一裁决出口 decide_escalation（15 条顺序表）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-07T10:50:50.570Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

测试段完成：本卡验收命令 26 passed，metric 契约抛错专项通过，零真实外发。

### 完成项

- pytest tests/services/test_watch_escalation_verdict.py -q → 26 passed（15 行判据齐备）
- metric 契约专项：1 passed（缺 PCT_CHANGE 时抛错，不静默降级）
- notify-guard intercepted=0 egress=0
- 如实声明：子卡模板的 pnpm test / npx tsc 不适用本仓；真实判据为 pytest 汇总

### 下一步

父卡 t-2f1402 收尾；随后 t3（规则侧显式化）与 t4/t5（兼容壳）。

---
