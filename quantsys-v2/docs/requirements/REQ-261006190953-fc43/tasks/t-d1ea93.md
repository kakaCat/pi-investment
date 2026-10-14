# t-d1ea93 跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算·研发

> 需求：REQ-261006190953-fc43 业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点

## 在做什么
跨仓消费侧：agent-dh 改读 v2 缺口口径，不再 weekday 自算·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T12:38:49.818Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

研发段：agent-dh 不再自己算缺口，改成只消费 v2 的交易日口径；缺字段时如实声明未校验而不回退自算

### 完成项

- probeNavCoverage 改为消费 v2 的 nav_coverage，删除 getUTCDay 工作日自算
- 抽出可测纯函数 buildNavCoverage，线上探测只负责取 body（同一条代码路径）
- 缺字段 / 非 2xx / 请求失败三种情形一律 verified=false + 未做交易日校验，不回退自算、不产生补跑建议
- prompt.ts 的窗口与缺口文案由工作日改为交易日，并补 nav_coverage 与 verified=false 两条 notes
- attribution-alignment.test.ts 由 6 例扩到 15 例，覆盖验收 ①~⑤
- agent-dh 侧旁证回归 52 passed（三条风险相邻文件）；验收命令 15 passed
- getUTCDay 在两个文件中计数均为 0

### 改动文件

- `agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts`
- `agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/prompt.ts`
- `agent-dh/apps/web/tests/attribution-alignment.test.ts`

### 下一步

联调段：核对线上现状（v2 未重启 → 走未校验分支）与预存失败归属。

---
## 汇报 2（2026-10-06T12:39:04.134Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

研发段（路径登记更正）：agent-dh 不再自己算缺口，改成只消费 v2 的交易日口径

### 完成项

- probeNavCoverage 改为消费 v2 的 nav_coverage，删除 getUTCDay 工作日自算
- 抽出可测纯函数 buildNavCoverage；线上探测只负责取 body（同一条代码路径）
- 缺字段 / 非 2xx / 请求失败一律 verified=false + 未做交易日校验，不回退自算、不建议补跑
- prompt.ts 窗口与缺口文案由工作日改为交易日，并补 nav_coverage 与 verified=false 两条 notes
- attribution-alignment.test.ts 由 6 例扩到 15 例，覆盖验收 ①~⑤
- 验收命令 15 passed；旁证回归 52 passed；getUTCDay 计数 0
- 路径说明：本卡改动全部在兄弟仓 agent-dh，故改动文件以 ../agent-dh/... 形式登记（工作区相对路径解析可达）

### 改动文件

- `../agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts`
- `../agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/prompt.ts`
- `../agent-dh/apps/web/tests/attribution-alignment.test.ts`

### 下一步

联调段：核对线上现状（v2 未重启 → 当前走"未校验"分支）与预存失败归属。

---
