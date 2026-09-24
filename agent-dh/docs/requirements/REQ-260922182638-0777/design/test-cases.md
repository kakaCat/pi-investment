---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 测试策略 · 统一追溯链逻辑：全链路展示中文化

> REQ-260922182638-0777 · 防再漂移机制 = 单测断言映射完整性 + 验收期 grep 唯一性核查。

## T-1 单测清单 `serves: FR-3`

| 用例ID | 用例 | 实际文件 | serves |
|--------|------|----------|--------|
| TC-001 | KIND_LABELS 覆盖 7 种 ArtifactKind + 4 种扩展种类，逐条断言中文名 | tests/artifact-labels.test.ts | FR-1 |
| TC-002 | 未知 kind → 「产物（mystery_kind）」；空串 → 不 throw | tests/artifact-labels.test.ts | FR-3 |
| TC-003 | DOC_FILE_LABELS 全表逐条命中（含 design/ 前缀段边界后缀匹配）；未知文件名 → 「设计文档（foo.md）」 | tests/artifact-labels.test.ts | FR-3, FR-4 |
| TC-004 | taskCardLabel：有 title →「任务卡 · 名称」；无 title →「任务卡（t-xxx）」 | tests/artifact-labels.test.ts | FR-5 |
| TC-005 | 防漂移护栏：effectiveDesignDocs('feature'/'bug'/…各类型) 产出的全部规范文件名 ∈ DOC_FILE_LABELS 键集——新增规范文件名未配中文名即红 | tests/artifact-labels.test.ts | FR-3 |
| TC-006 | 追溯链渲染：design 多份显示中文文档名、task_detail 逐张带名称展开、缺失产物红字保留 | tests/stage-panel.test.ts（扩展） | FR-4, FR-5 |

## T-2 验收命令 `serves: FR-2`

1. `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/artifact-labels.test.ts tests/stage-panel.test.ts` —— 全绿；
2. `grep -rn "'需求文档'" agent-dh/packages/web/dsh-pmboard/src` —— 映射定义只剩 src/shared/artifact-labels.ts 一处；
3. `pnpm typecheck && pnpm build` —— 通过（含 verify-client-build 哨兵）；
4. `grep -rn "ARTIFACT_KIND_LABELS\|SUBMIT_KIND\|ARCHIVE_DOC_KIND_LABELS\|DOC_KIND_META" src` —— 除 artifact-labels.ts 与 DOC_KIND_META 兼容导出外无残留本地表。

## T-3 浏览器人工核对 `serves: FR-4, FR-5`

打开 :13080 任一有 design 多份产物 + 任务卡的进行中需求详情页，对照 prototype.html §1–§5 黄底差异逐项核对：追溯链全中文（架构文档/接口文档/任务卡 · 名称）、无「任务卡×N」、无英文枚举；归档清单 requirement 显示「需求文档」。
人为构造未知值（测试数据塞 mystery_kind / foo.md）核对兜底形态「产物（mystery_kind）」「设计文档（foo.md）」。
