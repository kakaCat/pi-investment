---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10]
---

# 设计总说明（封面）<!-- serves: FR-1, FR-8 -->

> v2（2026-09-23 重写）：原 v1 单文件设计按类型模板拆为 5 份，并并入本窗口实测发现的三处节点面板 UX 缺陷（FR-8/9/10，详见 requirement.md 功能点）。本文档仅作索引与变更说明，正式设计以分视角文档为准。

## 文档地图 <!-- serves: FR-1, FR-4, FR-5, FR-8, FR-9, FR-10 -->

- [architecture.md](architecture.md)——worktree 提示词注入链 + 超时常量 + 触发时机（FR-1..FR-7）
- [interfaces.md](interfaces.md)——模板变量契约与三处渲染函数语义契约（FR-4、FR-8/9/10）
- [data-model.md](data-model.md)——数值契约（LIMITS 两档弹框超时 →3600s），无 schema 变更
- [test-cases.md](test-cases.md)——单测锚点 + TC-1..TC-8 + 线上验收
- [use-cases.md](use-cases.md)——UC-1..UC-6 场景

## 相对 v1 的修正 <!-- serves: FR-1, FR-3, FR-5 -->

1. 落点改真实机制：v1 臆测的 `src/node/route-prompt-injector.ts`、`requirement/state-machine.ts` 不存在——v2 落到 resolveStagePrompt + CaptureHook.onStagePrompt（唯一取词入口 INV-1）。
2. FR-3 落点 done → archived（REQ-9f4a44 已移除 done 节点）。
3. 超时改 `domain/limits.ts` 具名常量（v1 计划新建 config/defaults.ts，与 limits 唯一事实源原则冲突）。
