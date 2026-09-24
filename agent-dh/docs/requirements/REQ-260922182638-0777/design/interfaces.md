---
requirement_refs: FR-1, FR-3
---

# 接口设计 · 统一追溯链逻辑：全链路展示中文化

> REQ-260922182638-0777 · 唯一对外出口 = src/shared/artifact-labels.ts（纯函数模块，无 IO、无错误码——任何输入不 throw）。

## I-1 导出签名 `serves: FR-1`

```ts
/** 种类 → 中文名（唯一事实源）：7 种 ArtifactKind + 文档区扩展种类（ui/proposal/retro/notes） */
export const KIND_LABELS: Readonly<Record<string, string>>
/** 文档记录区图标（图标归属不变，仅集中一处） */
export const KIND_ICONS: Readonly<Record<string, string>>
/** 文件名 → 中文名：键 = 需求目录相对尾段（design/architecture.md）或裸文件名（requirement.md） */
export const DOC_FILE_LABELS: Readonly<Record<string, string>>

export function artifactKindLabel(kind: string): string
export function docFileLabel(path: string, kind?: string): string
export function taskCardLabel(path: string, title?: string): string
```
参数/返回全部 string 进 string 出；调用方原来 `?? kind` 的兜底写法全部删除，由函数内部统一兜底。

## I-2 取值与兜底契约 `serves: FR-3`

`artifactKindLabel(kind)`：命中 KIND_LABELS → 中文名；未命中 → `产物（${kind}）`（中文引导 + 原文附注，不裸显英文）。
`docFileLabel(path, kind?)`：path 归一化（去前导 `./`）后对 DOC_FILE_LABELS 做段边界后缀匹配（`path === key || path.endsWith('/' + key)`）→ 中文名；未命中 → basename 非空时 `${kind ? artifactKindLabel(kind) : '文档'}（${basename}）`，basename 为空 → artifactKindLabel(kind)。
`taskCardLabel(path, title?)`：title 非空 → `任务卡 · ${title}`；否则取 basename 去 `.md` 后缀 → `任务卡（${id}）`（id 空则 `任务卡`）。

## I-3 映射表终稿 `serves: FR-1, FR-4`

KIND_LABELS（与 prototype.html 第一层表逐字一致）：requirement→需求文档 / design→设计文档 / plan→拆分计划（旧版） / decomposition→拆分计划 / task_detail→任务卡 / verification→验收材料 / archive→归档材料；扩展：ui→UI 文档 / proposal→设计文档 / retro→复盘 / notes→其他。
DOC_FILE_LABELS（与 prototype.html 第二层表逐字一致，另补齐 category-doc-sets 规范文件名，使防漂移护栏对合法新文件不误报）：requirement.md→需求文档 / decomposition.md→拆分计划 / design/architecture.md→架构文档 / design/data-model.md→数据模型 / design/interfaces.md→接口文档 / design/test-cases.md→测试用例 / design/migration.md→迁移方案 / design/frontend.md→前端设计 / design/backend.md→后端设计 / design/use-cases.md→用例文档。

## I-4 迁移与兼容 `serves: FR-2`

无数据迁移、无开关、无灰度：展示层取值切换，刷新页面即生效。
兼容注意点：artifacts.ts 的 ARTIFACT_KIND_LABELS、verification.ts 的 ARCHIVE_DOC_KIND_LABELS 为导出符号，经全仓 grep 确认无外部 import（仅本文件自用），可直接删除；DOC_KIND_META 保留导出形状（icon+label），仅取值来源改到唯一事实源。
