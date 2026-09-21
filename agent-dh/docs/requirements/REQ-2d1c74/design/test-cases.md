---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 测试策略（REQ-2d1c74）

## 1. 用例矩阵（serves: FR-1, FR-2, FR-3, FR-5）

| 用例 | 层级 | 预期 | 实际文件 |
|---|---|---|---|
| feature 缺 use-cases.md → 缺失清单含该份 | unit | missingCategoryDocs 报缺 | tests/design-doc-policy.test.ts |
| sides=frontend → frontend.md 必交、backend.md 不要求 | unit | 条件必交生效 | tests/design-doc-policy.test.ts |
| design_exempt 生效 / 空理由不生效 | unit | 豁免增减缺失清单 | tests/design-doc-policy.test.ts |
| 文档集缺份 → design→decomposing 四路径全拒 | unit | design_doc_incomplete + 清单 | tests/design-completeness-gate.test.ts |
| 部分 design 产物未确认 → 拒；全确认 → 放行 | unit | gaps 列出未确认路径 | tests/design-completeness-gate.test.ts |
| depends_on 表头命中 / 代码块示例不命中 / 中文散文不命中 | unit | 特征清单精确 | tests/decomposition-detect.test.ts |
| 三确认通道落章前均被拦截 | unit | design_contains_decomposition | tests/decomposition-detect.test.ts |
| 确认 kind=design 成组落章全部产物 | unit | 全部 confirmedAt | tests/confirm-group.test.ts |
| 不存在路径 / 伪路径登记被拒，消息含 normalized | unit | 两枚错误码分流 | tests/artifact-openable.test.ts |
| isLegacy 需求全部新闸门放行 | unit | 兼容不回退 | tests/design-completeness-gate.test.ts |

测试文件头部 20 行内写 serves 注释（本仓既有约定，供孤儿用例探测）。

## 2. 规范层验证（serves: FR-4）

- `node scripts/inline-prompt-fragments.mjs` 重跑后 `node scripts/check-prompt-fragments.mjs` 通过（字节级同步）；
- `grep -n "kind=plan\|target=plan" src/domain/prompt/fragments/design/heavy/overrides.md` 无命中；
- docs/guides/reqboard-workflow.md 流程表与 GateCatalog.ts 逐行人工核对（闸门边 G2=确认设计文档、
  G3=批准拆分计划均在 decomposing 阶段），diff 留证。

## 3. 回归与总闸（serves: FR-6）

- `npx vitest run`（dsh-pmboard 包）全绿，含 base-delta / gate-catalog 既有性质测试；
- plan_submit 既有门禁（编号串联 / serves / 文档集）的既有测试不许改预期；
- 冒烟：构造测试需求走通"交齐 → 成组确认 → 放行"全路径（对应需求 §6 验收口径 3）。
