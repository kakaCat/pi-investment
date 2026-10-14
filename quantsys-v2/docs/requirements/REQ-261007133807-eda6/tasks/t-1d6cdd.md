# t-1d6cdd 收敛出唯一裁决出口 decide_escalation（15 条顺序表）·联调

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
收敛出唯一裁决出口 decide_escalation（15 条顺序表）·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-07T10:50:22.214Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

联调段完成：既有用例零改动全绿（44 passed），无循环导入。

### 完成项

- 既有回归 44 passed（checker 9 / metric_contract / disposition / disposition_engine）
- 兼容锁成立：四个既有测试文件零改动（git status 无这些文件的改动）
- 新模块与既有模块无循环导入（escalation_verdict 只向下依赖 disposition/models）
- 如实声明：子卡模板的 npx vitest 不适用本仓；真实判据为 pytest

### 下一步

复核段：码覆盖与设计顺序表对拍。

---
