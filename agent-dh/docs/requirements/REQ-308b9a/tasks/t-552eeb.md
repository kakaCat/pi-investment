# t-552eeb verification.md 结构化生成 + 9 类文档完整性检查

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
verification.md 结构化生成 + 9 类文档完整性检查

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test，T-U5/T-U6/T-U7/T-I7/T-I8 全绿；生成的 docs/requirements/<REQ>/verification.md 包含验收列表/测试报告/文档完整性检查/验收结果四段。

## 实施方案（implementation）
新增 src/domain/workflow/VerificationDoc.ts（renderVerificationDoc 纯渲染四段）与 DocCompleteness.ts（checkDocCompleteness）；SubmitVerification.ts 生成文件并在缺项时抛 REQBOARD_DOC_INCOMPLETE。

## 上游产出摘要（dependsSummary）
- 扩展验收项状态与通过判据（domain）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T02:24:38.381Z，窗口 session-7cfa4169-c6dd-4608-b5c4-fb5af4f69a54）

FR-7 落地：提交验收时执行 9 类文档完整性检查（缺则拒绝），并生成四段式 verification.md（验收列表含派生操作步骤/预期结果、测试报告、文档完整性检查、验收结果表）。

### 完成项

- domain/workflow/DocCompleteness.ts：9 类文档纯判定（与本仓 feature 产物对齐，不另造清单）
- domain/workflow/VerificationDoc.ts：verification.md 纯渲染（四段 + 结果表五列；消息走 fmt，domain 零拼接）
- SubmitVerification.ts：接线检查（缺项 → REQBOARD_DOC_INCOMPLETE）+ 结构化生成（覆盖旧骨架）
- 存量豁免口径：artifacts 空或盘上无 requirement.md → 不追溯（避免误伤测试/存量数据；用 requirement.md 而非"目录非空"，因为首次提交会写 verification.md 破坏该信号）
- 新增 T-U5/T-U5b/T-U6/T-U7（域）+ T-I7/T-I8（集成）；补 doc-gate-e2e 的 9 类文档夹具

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/workflow/DocCompleteness.ts`
- `packages/pages/dsh-pmboard/src/domain/workflow/VerificationDoc.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/SubmitVerification.ts`
- `packages/pages/dsh-pmboard/tests/domain/verification-doc.test.ts`
- `packages/pages/dsh-pmboard/tests/doc-gate-e2e.test.ts`
- `packages/pages/dsh-pmboard/lib/client.js`
- `packages/pages/dsh-pmboard/lib/client.cjs`

### 下一步

t4：裁决后回填验收结果表

---
