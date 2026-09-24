---
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 架构设计 · 统一追溯链逻辑：全链路展示中文化

> REQ-260922182638-0777 · feature / simple · 窗口 w-89aa3b25 · 2026-09-22

## A-1 目标与改动面 `serves: FR-1`

一句话目标（可证伪）：dsh-pmboard 中「产物种类 kind → 中文名」与「节点文档文件名 → 中文名」两层映射收敛为**唯一事实源模块** `src/shared/artifact-labels.ts`，六处调用点全部改为 import 引用，`grep -rn "'需求文档'" src` 定义只剩一处。
改动面 = 新增 1 个共享模块 + 6 处引用收敛 + 追溯链 2 处标签逻辑改造；不动协议、不动枚举、不动后端。

## A-2 模块放置与理由 `serves: FR-1`

模块放 `src/shared/artifact-labels.ts`（与 protocol.ts 同层），不放 client/：调用点横跨两侧——client 侧（stage-panel / views）与 host 侧（tools/render-summaries），shared 是唯一双方都已 import 的公共层，client bundle 构建（tsdown.client.config）已覆盖 shared 目录，无构建配置变更。
模块纯函数、零 IO、零依赖（仅类型上对齐 ArtifactKind 联合），client/host 双向安全。

## A-3 调用点收敛清单 `serves: FR-1, FR-2`

| # | 文件 | 现状 | 改造 |
|---|------|------|------|
| 1 | src/client/stage-panel.ts:60 | 私有 ARTIFACT_KIND_LABELS（7 项） | 删本地表，import artifactKindLabel / docFileLabel / taskCardLabel |
| 2 | src/client/views/artifacts.ts:18 | 导出 ARTIFACT_KIND_LABELS（同名重复定义） | 删表，chips 两处（L78/L107）改 artifactKindLabel(g.kind) |
| 3 | src/client/views/verification.ts:16 | DOC_KIND_META（12 项，图标+标签） | 标签位改由 KIND_LABELS 供给、图标由 KIND_ICONS 供给，导出形状不变 |
| 4 | src/client/views/verification.ts:189 | ARCHIVE_DOC_KIND_LABELS（requirement 译作「需求说明」） | 删表，L175 改 artifactKindLabel(d.kind)（retro/notes 已入 KIND_LABELS） |
| 5 | src/client/toolviews/shared.ts:138 + rows/submit.ts + rows/ask-confirm.ts | SUBMIT_KIND 仅 4 项，ask-confirm 另有 KIND_CN 补丁 | 删 SUBMIT_KIND/KIND_CN，统一 artifactKindLabel（design/decomposition/task_detail 自动补齐） |
| 6 | src/tools/render-summaries.ts:24 | SUBMIT_KIND_CN（plan 译「拆分计划」） | 删表，import artifactKindLabel（plan 统一为「拆分计划（旧版）」，术语漂移消除） |

## A-4 追溯链渲染改造 `serves: FR-4, FR-5`

traceNodeLabel（stage-panel.ts:88）：单份产物 → artifactKindLabel(kind)；同类多份（MULTI_DOC_KINDS={design}）→ docFileLabel(artifact.path, kind)，裸文件名（architecture.md）不再作主标签，tooltip 仍带 displayDocPath 完整路径（排查线索不丢）。
生效面（答用户问）：renderStageNode 是**看板与会话流程节点共用入口**（board-mount.ts:642 与 conversation-progress.ts:278 同调一个渲染器），故追溯链改造在两处同时生效；工具回执改动（toolviews/render-summaries）本就渲染在会话流里。
任务卡展开（stage-panel.ts:562-569）：删「任务卡×N」折叠分支，task_detail 与 design 一样逐条渲染；每条标签 = taskCardLabel(path, title)，title 由 `taskTitleByCardDoc(payload)` 解析——payload.body 为 DecomposeStageBody/ImplementStageBody 时取其 tasks，建 cardDoc → title 映射，artifact.path 精确匹配命中即用 StageTaskRef.title；匹配不到降级「任务卡（t-xxx）」（id 取 basename 去 .md）。缺失必备产物红字「（缺失）」分支行为不变。

## A-5 不变量与回滚 `serves: FR-2`

不变量：ArtifactKind 枚举、StageArtifact/StageTaskRef 形状、reqboard_submit 契约、ArtifactSync 同步逻辑、图标归属、chips 颜色语义、「种类名 · 文档名」两段式格式——全部不变（对齐 prototype.html 不变项清单）。
回滚：纯展示层取值变更，无数据迁移、无状态文件，单 commit revert 即全量回退。
