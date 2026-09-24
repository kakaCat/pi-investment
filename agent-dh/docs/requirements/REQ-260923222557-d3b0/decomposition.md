# REQ-260923222557-d3b0 拆分计划

> 对照 design/ 五份设计文档盘点改动（新增/修改/删除），任务表见文末。

## 改动盘点

### 新增
- `src/domain/prompt/worktree-events.ts` —— 事件型提示词常量两份（task_done / archived）+ 变量替换（{id}/{task_id}/{task_title}）
- `src/domain/prompt/fragments/implementing/` —— implementing 档补 worktree 规范段（无该档则新建；generated/fragments.ts 由 scripts/inline-prompt-fragments.mjs 再生成）

### 修改
- `src/domain/limits.ts` —— timeoutInteractiveMs 600_000→3_600_000、timeoutSheetMs 900_000→3_600_000
- `src/adapters/CaptureHook.ts` —— task_move→done 与 accepting→archived 两处事件注入（复用 onStagePrompt 通道，失败不阻断转移）
- `src/client/stage-panel.ts` —— stageHeadSummary design 分支改按设计文档交付/确认取词（旧 plan 存量兼容）
- `src/client/node-panel.ts` —— renderHead 下传行状态（pending→「未开始」）；renderDesignInfo 已交行改 docItem 可点；renderDecomposingInfo 补占位行
- `tests/` —— fragments 基线更新 + TC-1..TC-8 用例
- 构建产物：generated/fragments.ts 再生成 + lib/client.js 重建

### 删除
- 无

## 兼容要点
- 旧管线存量需求（design 有 plan 记录）头部文案不变；非 reqboard 工具超时不动；提示词不强制执行 git 命令（agent 自主判断）。

## 任务表

| key | 标题 | 依赖 |
|---|---|---|
| t1 | 弹框超时调整为 1 小时（domain 常量） | — |
| t2 | worktree 提示词文本三份（implementing 档 + 事件常量） | — |
| t3 | 子任务完成/归档两处事件注入接线 | t2 |
| t4 | 面板头部：进展胶囊与状态词修正 | — |
| t5 | 面板文档行：已交可点、未交占位 | — |
| t6 | 测试补齐与全量回归 | t1, t2, t3, t4, t5 |
| t7 | 兼容核验 + 构建部署与线上验收 | t6 |

## RTM 覆盖表（需求条款 ↔ 任务卡）

> 该表是「哪条需求由哪张卡负责」的规范载体（TaskRecord 不存该绑定，覆盖判定与三方一致性都读这里）。
> 补录原因：2026-09-23 自动拆分曾被 requirement_uncovered 拦下，人工补 decompose 时把绑定传进了
> 工具参数，但本文档最初的任务表只有 key/标题/依赖三列，解析器读不到根编号 → 需求页把 FR-1..FR-10
> 全标成「未被接收」。此处按台账 id 补录，一行一条条款。

| 任务编号 | 任务标题 | 根编号 |
|---|---|---|
| t-787137 | 弹框超时调整为 1 小时（domain 常量） | FR-5 |
| t-787137 | 弹框超时调整为 1 小时（domain 常量） | FR-6 |
| t-787137 | 弹框超时调整为 1 小时（domain 常量） | FR-7 |
| t-b2e945 | worktree 提示词文本三份（implementing 档 + 事件常量） | FR-1 |
| t-b2e945 | worktree 提示词文本三份（implementing 档 + 事件常量） | FR-4 |
| t-06d59d | 子任务完成/归档两处事件注入接线 | FR-2 |
| t-06d59d | 子任务完成/归档两处事件注入接线 | FR-3 |
| t-485233 | 面板头部：进展胶囊与状态词修正 | FR-8 |
| t-485233 | 面板头部：进展胶囊与状态词修正 | FR-10 |
| t-595192 | 面板文档行：已交可点、未交占位 | FR-9 |
| t-b9ff3f | 测试补齐与全量回归 | FR-1 |
| t-b9ff3f | 测试补齐与全量回归 | FR-2 |
| t-b9ff3f | 测试补齐与全量回归 | FR-3 |
| t-b9ff3f | 测试补齐与全量回归 | FR-4 |
| t-b9ff3f | 测试补齐与全量回归 | FR-5 |
| t-b9ff3f | 测试补齐与全量回归 | FR-6 |
| t-b9ff3f | 测试补齐与全量回归 | FR-7 |
| t-b9ff3f | 测试补齐与全量回归 | FR-8 |
| t-b9ff3f | 测试补齐与全量回归 | FR-9 |
| t-b9ff3f | 测试补齐与全量回归 | FR-10 |
| t-4e8339 | 兼容核验 + 构建部署与线上验收 | FR-5 |
| t-4e8339 | 兼容核验 + 构建部署与线上验收 | FR-8 |
| t-4e8339 | 兼容核验 + 构建部署与线上验收 | FR-9 |
| t-4e8339 | 兼容核验 + 构建部署与线上验收 | FR-10 |

