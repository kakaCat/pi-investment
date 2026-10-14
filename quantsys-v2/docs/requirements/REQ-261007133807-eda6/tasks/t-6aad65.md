# t-6aad65 迁移：watch_triggers 加两列（两个库都跑）·联调

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
迁移：watch_triggers 加两列（两个库都跑）·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-07T10:47:53.971Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

联调段完成：两列对测试库真实往返成功（写回读一致、清理零残留）。

### 完成项

- 对 quant_test 真实 insert 一条 auto_observed 触发（带 BUDGET_EXHAUSTED 码）并读回：码/理由/disposition 三者一致
- 清理后残留 0 行（用后即删，不污染测试库）
- 验证「没叫也有码」：auto_observed + 预算门同样带 escalation_code
- 声明：本卡联调面 = 列写入与读回；脚本已两库执行（quant_investment 89 行历史 NULL）

### 下一步

复核段：ORM 列 vs information_schema 对拍。

---
