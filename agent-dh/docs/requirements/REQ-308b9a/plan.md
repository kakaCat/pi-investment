---
req_id: REQ-308b9a
doc: plan
status: design
---

# REQ-308b9a 拆分计划

## 目标

把阶段 6 验收的三条缺口补齐：**FR-7** verification.md 结构化生成、**FR-8** 验收失败自动回退实施、
**FR-9** 不可验收项记录 + 全部已裁决即可通过。

## 前置（硬约束）

REQ-a8d582（已 archived）的代码改动**当前仍在工作区未提交**，且本计划 t2 **推翻其 FR-2**。
**必须先把 REQ-a8d582 的改动合入基线，再在基线上实施**；不得在他人未提交改动上直接编辑。

## 接口与数据契约

见 `design/interfaces.md` §2/§3（域内纯函数签名、两个新错误码）与 `design/data-model.md` §1（四值状态联合）。
契约在实现前冻结。

## 任务表

| key | 标题 | phase | side | 依赖 | 验收（可证伪） |
|---|---|---|---|---|---|
| t1 | 扩展验收项状态与通过判据（domain） | implement | backend | - | `pnpm --filter dsh-pmboard test`：tests/domain/acceptance-sheet.test.ts T-U1~T-U4 全绿 |
| t2 | FR-8 自动回退实施（application） | implement | backend | t1 | tests/verdicts-and-rework.test.ts T-I1~T-I4 全绿；T-I2 故障注入整笔回滚 |
| t3 | verification.md 生成 + 9 类文档检查 | implement | backend | t1 | T-U5~T-U7 / T-I7 / T-I8 全绿；verification.md 含四段 |
| t4 | 裁决后回填验收结果表 | implement | backend | t2,t3 | T-I9 断言 verification.md 结果表含五列 |
| t5 | 弹框补操作步骤 + 题干截短 | implement | fullstack | t3 | T-E3：题干 ≤220 且选项可见、弹框含操作步骤 |
| t6 | 「退回返工」收敛为等价入口 | implement | backend | t2 | T-E4：两入口同一 use-case |
| t7 | 测试与门禁 | test | fullstack | t4,t5,t6 | vitest 全绿 + verify-client-build.mjs exit=0 + tsc 0 错 |
| t8 | 文档同步（PRD 与指南） | doc | doc | t2,t3 | grep 三处标注齐、无悬空引用 |

## 接口 → 实现 → 接线顺序

t1（契约/域）→ t2/t3（实现，可并行）→ t4/t6（接线）→ t5（前端接线）→ t7（门禁）→ t8（文档）。

## 验收

- 功能：`design/test-cases.md` T-U/T-I/T-E 全绿；
- 回归：旧验收单可读可续验（T-E2）；
- 门禁：vitest 全绿、`verify-client-build.mjs` exit=0、`tsc` 0 错误。

## 回滚

代码 `git revert` + 重启（`launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`）。
台账若已写入 `not_verifiable`，读路径不校验枚举 → 天然容忍；无需数据回填。
