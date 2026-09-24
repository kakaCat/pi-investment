---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 架构设计（REQ-260923222557-d3b0）

## TL;DR <!-- serves: FR-1, FR-4 -->

Worktree 规范**复用现有阶段提示词注入链**（resolveStagePrompt → CaptureHook → onStagePrompt），不新造机制：implementing 走节点路由档，task_done / archived 走事件注入；弹框超时改 `src/domain/limits.ts` 一处具名常量。面板 UX 修正（FR-8/9/10）全部落在 client 渲染层，见 interfaces.md。

## 设计总览 <!-- serves: FR-1, FR-4, FR-5 -->

```
状态转移/任务推进事件
   │
   ├─ 阶段键命中（implementing）──► resolveStagePrompt ──► fragments/implementing/*.md
   │                                                        │
   ├─ 事件型（task done / accepting→archived）──► 事件注入常量（复用 onStagePrompt 通道）
   │                                                        │
   ▼                                                        ▼
CaptureHook（adapters） ──► deps.onStagePrompt(windowKey, text) ──► 绑定会话系统提示词
```

| 组件 | 职责（一句话） | 改动文件 |
|---|---|---|
| 提示词文本 | worktree 规范三份（implementing / task_done / archived），含命令示例与变量 | `src/domain/prompt/fragments/`（新增） |
| 注入触发 | 状态/任务转移后把文本投给绑定窗口（现有通道，仅新增事件型两处触发） | `src/adapters/CaptureHook.ts` |
| 超时常量 | interactive/sheet 两档弹框超时 600s/900s → 3600s，单点定义 | `src/domain/limits.ts` |
| 面板渲染 | 头部胶囊/文档行/状态词三处修正（FR-8/9/10） | `src/client/stage-panel.ts`、`node-panel.ts`、`node-panel-process.ts` |

## 注入点与触发时机 <!-- serves: FR-1, FR-2, FR-3 -->

- **implementing（FR-1）**：decomposing→implementing 转移注入。走节点路由提示词档（与 brainstorming/design 同机制：fragments 按 stage+difficulty+category 匹配，resolveStagePrompt 唯一取词入口，INV-1）。
- **task_done（FR-2）**：`reqboard_task_move` → done 时注入。非阶段键，属事件型——在任务推进的成功路径追加一次 onStagePrompt 投递（与 CaptureHook 现有里程碑提醒 :331 同通道）。
- **archived（FR-3）**：accepting→archived 转移时注入。原需求写的「done 状态」已随 REQ-9f4a44 移除，落点为归档转移。

三份文本共用变量：`{id}`=需求号、`{task_id}`、`{task_title}`；内容含 `git worktree add .worktrees/REQ-{id}/ -b feature/REQ-{id}` 等命令示例。**提示不强制**（边界：agent 可判断后执行，不硬编码自动 git 命令）。

## 失败分支与降级 <!-- serves: FR-1, FR-2, FR-3 -->

- 绑定窗口不存在/投递失败：注入跳过，**不阻断**状态转移（与现有 onStagePrompt 失败语义一致，只留痕）。
- fragments 缺失某档：resolveStagePrompt 回退 difficulty='*' 档；三份 worktree 文本写在 category='*' 档，全类型生效。

## 超时调整 <!-- serves: FR-5, FR-6, FR-7 -->

`LIMITS.timeoutInteractiveMs: 600_000 → 3_600_000`、`LIMITS.timeoutSheetMs: 900_000 → 3_600_000`（domain/limits.ts 是全仓唯一数值事实源，消费方 AskConfirmTool/CaptureTool/TaskExecuteTool/AdvanceTool/AcceptSheetTool 全部引用常量、零硬编码——改一处即全链路 1 小时，天然满足 FR-7 配置化）。弹框等待超时后的返回语义不变。

## 兼容与回滚 <!-- serves: FR-5, FR-8 -->

- 旧管线存量需求（design 阶段已有 plan 记录）：头部胶囊保持计划类旧文案（FR-8 兼容分支）。
- 回滚 = 还原 limits.ts 两值 + 删除三份 fragments/事件文本 + 还原三处渲染函数；无数据迁移。
