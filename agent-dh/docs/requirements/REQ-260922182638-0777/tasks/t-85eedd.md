# t-85eedd 新增 artifact-labels 唯一事实源模块与防漂移单测

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增 artifact-labels 唯一事实源模块与防漂移单测

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：fullstack

## 得到什么结果
cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/artifact-labels.test.ts 全绿（TC-001~005）；pnpm typecheck 通过

## 实施方案（implementation）
1. 新建 src/shared/artifact-labels.ts（与 protocol.ts 同层，纯函数零依赖）：导出三张 Readonly 表（内容与 design/interfaces.md I-3 终稿逐字一致）+ 三函数，兜底契约按 I-2（未知 kind→「产物（原值）」；未知文件名→「<kind中文>（<文件名>）」；任何输入不 throw）。2. 新建 tests/artifact-labels.test.ts：TC-001 全表逐条断言；TC-002 未知 kind/空串不 throw；TC-003 DOC_FILE_LABELS 全表命中+未知文件名兜底；TC-004 taskCardLabel 两分支；TC-005 防漂移护栏——import effectiveDesignDocs 对六种 category 规范文件名断言 ∈ DOC_FILE_LABELS 键集。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T13:24:14.922Z，窗口 session-89aa3b25-9e19-48c0-a032-cf932135f88b）

唯一事实源模块已落地：追溯链/文档区/工具回执要用的中文名映射从此只有一处定义（src/shared/artifact-labels.ts：KIND_LABELS/KIND_ICONS/DOC_FILE_LABELS 三表 + artifactKindLabel/docFileLabel/taskCardLabel 三函数，纯函数零依赖，未知值中文兜底不 throw）；配套 17 条防漂移单测全绿——以后新增产物种类或规范设计文档文件名没配中文名，测试直接变红拦截。实测发现 ArtifactKind 枚举实为 9 值（含 notes/task_output，设计文档按 7+4 写），已补配「其他」「任务产物」并纳入护栏。

### 完成项

- 新建 src/shared/artifact-labels.ts（三表三函数，按 interfaces.md I-1~I-3；补配枚举内 notes/task_output）
- 新建 tests/artifact-labels.test.ts（TC-001~005 共 17 条断言，含 effectiveDesignDocs 防漂移护栏）
- pnpm vitest run packages/web/dsh-pmboard/tests/artifact-labels.test.ts → 17/17 通过
- pnpm typecheck → 通过（exit 0）

### 改动文件

- `packages/web/dsh-pmboard/src/shared/artifact-labels.ts`
- `packages/web/dsh-pmboard/tests/artifact-labels.test.ts`

### 下一步

t2/t3/t4/t5 四张下游卡引本模块收敛六处本地映射表

---
