# t-077bfc 扩展 on_fill 批次退役与事件留痕·测试

> 需求：REQ-261022022657-857f 交易闭环补口：反思唤醒 + 减仓批次收敛 + 消息→离场

## 在做什么
扩展 on_fill 批次退役与事件留痕·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-21T18:35:59.227Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

测试段通过：批次 11 例全绿，plan 全量 139 例无红。

### 完成项

- pytest tests/plan/test_plan_batch_convergence.py -q → 11 passed
- pytest tests/plan -q → 139 passed

---
