---
req_id: REQ-308b9a
doc: design/test-cases
serves: FR-7, FR-8, FR-9
status: design
---

# REQ-308b9a 设计 · 测试用例

## 1. 单元测试（域内纯规则）  `serves: FR-9`

| ID | 用例 | 期望 |
|---|---|---|
| T-U1 | `applyVerdicts` 收到 `not_verifiable` 无 opinion | 抛 `invalid_input`（AC-9.2） |
| T-U2 | `applyVerdicts` 收到 `failed` 无 opinion | 抛 `invalid_input` |
| T-U3 | `isFullyDecided`：`passed + not_verifiable`、无 pending | `true`（AC-9.3） |
| T-U4 | `isFullyDecided`：含 pending | `false`（AC-9.5） |
| T-U5 | `renderVerificationDoc` 输出含四段标题 | 验收列表/测试报告/文档完整性检查/验收结果（AC-7.2~7.3） |
| T-U6 | 结果表列头 | 恰好 编号/验收项/状态/验收人/验收时间（AC-7.8） |
| T-U7 | `checkDocCompleteness`：缺 1 类 | `passed=false` 且 `missing` 精确列出（AC-7.4） |

## 2. 集成测试（用例层）  `serves: FR-7, FR-8`

| ID | 用例 | 期望 |
|---|---|---|
| T-I1 | 提交含 `failed` 的裁决 | 需求自动 `implementing` + 每个 failed 生成一张返工卡（AC-8.1/8.2） |
| T-I2 | 回退原子性（故障注入：物化返工卡时抛错） | 整笔回滚，需求状态与任务均不变（AC-8.3） |
| T-I3 | 回退留痕 | `statusHistory` 新增一条（actor/reason）+ 评论存在（AC-8.4） |
| T-I4 | `not_verifiable` 裁决 | **不**触发回退（AC-8.5） |
| T-I5 | 全部已裁决（`passed + not_verifiable`） | 允许进入「验收通过」（AC-9.3） |
| T-I6 | 存在 pending | 通过被拒（AC-9.5） |
| T-I7 | 提交验收材料时缺 9 类文档之一 | 提交被拒 + 提示补哪一份（AC-7.5） |
| T-I8 | 提交验收材料且文档齐 | 生成完整 `verification.md`（AC-7.1） |
| T-I9 | 裁决后 | `verification.md` 结果表被回填（AC-7.7） |

## 3. E2E / 回归  `serves: FR-7, FR-8, FR-9`

| ID | 场景 | 期望 |
|---|---|---|
| T-E1 | 完整流水线：提交材料 → 逐项裁决（含失败）→ 自动回退 → 返工 done → 再提交 → 全过 → 归档 | 全链无死锁；`verification.md` 版本递增（v1→v2） |
| T-E2 | 旧验收单（三值状态）读取与续验 | 不报错，可继续裁决（NFR-1） |
| T-E3 | 弹框题干长度 | 题干 ≤ `popupQuestionMax`，选项不被挤出可视区 |
| T-E4 | 看板「退回返工」入口 | 与自动回退走同一 use-case（无双实现漂移） |

## 4. 门禁  `serves: FR-7, FR-8, FR-9`

- `pnpm --filter dsh-pmboard test`（vitest 全量）必须全绿；
- `node scripts/verify-client-build.mjs` exit=0（客户端产物未污染）；
- 类型门禁 `tsc` 0 错误。
