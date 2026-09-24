---
requirement_refs: BUG-1, BUG-2
---

# 拆分计划 · REQ-260922182505-0924 删除 triage 遗留兼容路径

> 目标（业务语言）：把已经退役的旧立项流程（triage）残留在看板里的前后台代码彻底删掉，
> 同时清掉 3 个误提交进源码树的 .bak 备份文件；老台账里的 2 条历史记录原样保留、照常可读。
> 做法：先取基线（复现现状+记录现有测试失败集）→ 再按设计文档的改动面执行删除 → 最后独立跑全量回归与部署验证。

## 改动盘点（对照 design/design.md 处置表）

**删除文件（4）**：`src/http/routers/triage.ts`、`src/application/internal/support.ts.bak2/.bak3/.bak4`

**删除代码（14 文件）**：`routes.ts`（4 挂载+import）、`window.ts`（hasPendingSuggestion/pendingSuggestionFor）、`support.ts`（findPending）、`CaptureRequirement.ts`（前置检查③）、`QueryState.ts`（pending 用法）、`StatusTool.ts`（pending 展示）、`Predicates.ts`（isPendingTriage/isResolvedTriage）、`board-mount.ts`（triage 视图状态机）、`views/board.ts`（buildTriage+tab）、`api.ts`（4 接口）、`types.ts`（TriageList/TriageRecord）、`styles/base.ts`（triage CSS）、`view.ts`（1 处）、`ports.ts`（如有类型引用）

**冻结不动**：`protocol.ts` 的 TriageRecord、`JsonLedgerRepository.ts` 读写管道、`RollupSpec/rollup.ts` 的 triage 读取、migration v4 fixture 测试

**仅注释保留**：`CaptureHook.ts`、`index.ts`、`SessionMessageFilter.ts`（历史说明）

**测试同步（随删随改）**：api-client / capture / capture-hook / reqboard 等引用 triage 的测试用例按编译与测试报错逐个同步；acceptance-criteria 存量红灯不动（边界外）

## 任务表

| key | title | phase | side | depends_on |
|-----|-------|-------|------|------------|
| t1 | 复现死代码现状并建立回归基线 | analysis | backend | — |
| t2 | 删除 triage 兼容路径与 .bak 文件 | implement | fullstack | t1 |
| t3 | 全量回归与部署后独立验证 | test | fullstack | t2 |

（bug 类型档三卡制：复现 → 修复 → 独立回归证据；回归卡不并入修复卡）
