# t-ee93ba 跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算·测试

> 需求：REQ-261006190953-fc43 业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点

## 在做什么
跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T12:40:31.671Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

测试段：卡 E 验收 15 passed，相邻 37 passed，未见新增失败

### 完成项

- 卡 E 验收原命令：15 passed（Test Files 1 passed）
- 相邻风险文件 37 passed：tool-silent-failure-guard 22 + account-default 15
- 预存失败已用 stash 对照取证，与本卡无关（plugin-schema.smoke.test.ts）
- 阶段模板的 npx tsc 全仓本就大量红（预存），本卡未新增类型错误

### 下一步

卡 E 收尾，7 张卡全部完工，进入验收材料提交。

---
