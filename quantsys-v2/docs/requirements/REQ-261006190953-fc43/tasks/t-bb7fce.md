# t-bb7fce 跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算·联调

> 需求：REQ-261006190953-fc43 业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点

## 在做什么
跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡接口/契约对应的测试文件>` → 全绿（请求样例与期望响应一致）

---
## 汇报 1（2026-10-06T12:39:51.259Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

联调段：线上现状与预存失败都已查实；卡 E 的透出分支需 v2 重启才端到端成立（已登记为 R-5，属部署决定）

### 完成项

- 线上 v2 现场核对：/api/simulation/performance 仍只有 5 个旧键，无 window / nav_coverage（进程未重启）
- 因此线上当前走卡 E 的未校验分支：行为正确（如实声明、不误报缺口），但透出分支要等重启才生效
- agent-dh 预存失败归属核对：plugin-schema.smoke.test.ts 1 failed（stash 对照证明与卡 E 无关）
- 预存类型错误 TS1117 亦经 git show HEAD 确认为基线自带，本卡未新增
- 跨仓改动路径登记形式问题已解决并记账（DEV-15：../agent-dh/...）

### 改动文件

- `docs/requirements/REQ-261006190953-fc43/notes/implementation-deviations.md`

### 下一步

复核段：逐条点名验收 ①~⑤，并明确 ① 当前为桩测（线上待重启）。

---
