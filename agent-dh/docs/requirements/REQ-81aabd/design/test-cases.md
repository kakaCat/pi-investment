---
req_id: REQ-81aabd
title: 设计 · 测试用例：分类/归因/回填/展示/命名收口与键迁移
serves: FR-3, FR-4, FR-5, FR-6, FR-7
---

# 设计 · 测试用例（REQ-81aabd）

## 1. 用例总表（serves: FR-3, FR-4, FR-5, FR-6, FR-7）

| ID | 用例 | 层级 | 实际文件 | 预期 |
|----|------|------|----------|------|
| TC-1 | `design/*.md` → `kind='design'`，非 .md 仍是 `notes` | 单测 | packages/pages/dsh-pmboard/tests/domain/artifact.test.ts | `kindForRelPath('design/architecture.md')==='design'`；`.html` → `notes` |
| TC-2 | `design` 是展示种类，不进任何必备/确认门 | 单测 | packages/pages/dsh-pmboard/tests/domain/artifact.test.ts | `ALL_ARTIFACT_KINDS` 含 `design`；`STAGE_ARTIFACT_REQUIREMENTS`/`ARTIFACT_CONFIRM_GATES` 均不含 |
| TC-3 | 补登：目录里的 `design/architecture.md` 被同步进台账 | 单测 | packages/pages/dsh-pmboard/tests/sync-artifacts.test.ts | 补登 1 件；`kind==='design'`；`stage==='design'` |
| TC-4 | 回填：旧 `notes`（autoDiscovered）→ `design`，二次调用幂等 | 单测 | packages/pages/dsh-pmboard/tests/sync-artifacts.test.ts | 首次改写台账；二次返回值 0 且不再改写 |
| TC-5 | 人工登记条目不被回填覆盖 | 单测 | packages/pages/dsh-pmboard/tests/sync-artifacts.test.ts | `kind` 保持 `notes` |
| TC-6 | 设计节点逐份状态（feature 四份，一份已交） | 单测 | packages/pages/dsh-pmboard/tests/stage-detail.test.ts | `designDocs` 名称顺序 = 模板声明顺序；恰一份 `submitted=true` |
| TC-7 | bug 类型要求 0 份设计文档 | 单测 | packages/pages/dsh-pmboard/tests/stage-detail.test.ts | `designDocs` 为 `[]` |
| TC-8 | 面板渲染 ✅ 已交 / ⬜ 未交 + 稳定 DOM 属性 | 单测 | packages/pages/dsh-pmboard/tests/stage-panel.test.ts | 含 `data-design-doc="architecture.md" data-submitted="yes"` 与 `…"data-model.md" data-submitted="no"` |
| TC-9 | 旧名零残留 + 客户端产物含新符号 | 集成 | packages/pages/dsh-pmboard/scripts/verify-client-build.mjs | 构建门禁 OK；`技术设计/实施计划/头脑风暴/planning` 在 `lib/client.js` 命中 0 |
| TC-10 | 全量回归 | 集成 | packages/pages/dsh-pmboard/tests | `npx vitest run` 全绿（97 文件 / 1250 用例） |
| TC-11 | E2E：本需求自身的看板设计节点显示四份已交状态 | E2E | 项目看板 · 设计节点 | 四行 ✅/⬜，与 `docs/requirements/REQ-81aabd/design/` 实际文件一致 |
| TC-12 | 键改名：旧键 `planning` 非法、新键 `design` 合法 | 单测 | packages/pages/dsh-pmboard/tests/domain/*status*.test.ts | `REQ_STATUSES` 不含 `planning` / 含 `design`；`brainstorming → design` 属人门 |
| TC-13 | 台账 v6→v7 迁移：键归一 + 白名单外零差异 + 幂等 | 集成 | packages/pages/dsh-pmboard/tests/migration.test.ts | `npx vitest run tests/migration.test.ts` 全绿；迁移链含 `{from:6,to:7}` |
| TC-14 | 存量台账实迁复核 | 集成 | 线上台账 `.dsh-data/dsh-reqboard.json` | `--apply` 后 `--verify` 输出 0 问题项；`schemaVersion=7`；正文 `planning` 措辞保留 |

## 2. 测试策略（serves: FR-6）

- **单测优先**：分类（TC-1/2）、同步（TC-3/4/5）、装配（TC-6/7）、渲染（TC-8）全部落在纯函数与
  内存台账上，不依赖看板 UI；
- **集成**：构建门禁（TC-9）是"改了客户端却忘了重建"的唯一拦截点——本次改的是 `stage-panel.ts`，
  不同步重建则线上仍是旧渲染，属于必须实测的路径；
- **E2E**：TC-11 用本需求自己当样本（它恰好有 4 份设计文档），比构造 fixture 更真实；
- **不做**：不为回填逻辑造 100 条历史模型的性能测试（规模已知：需求数百条，单次同步 O(n)）。

## 3. 反例与边界（serves: FR-5）

| 输入 | 预期 |
|------|------|
| `design/` 为空目录 | 补登 0 件；无报错 |
| `design/token-ui.html` | 归 `notes`（不是文档） |
| 台账已登记同路径、种类正确 | 不重复登记（幂等），不产生审计噪声 |
| 手工把 `notes` 条目改成 `design` 后同步 | 不改（无 `autoDiscovered` 标记 = 人的声明优先） |
| 未登记 `category` 的需求 | 无 `designDocs` 字段，面板回退旧渲染 |
