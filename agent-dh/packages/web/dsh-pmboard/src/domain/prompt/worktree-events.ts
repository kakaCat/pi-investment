/**
 * 事件型 worktree 提示词（REQ-260923222557-d3b0 FR-2/FR-3）。
 *
 * 为什么不是节点路由分片：task_done / archived 不是 stage，走不到 resolveStagePrompt 的
 * 回退链；它们是**任务推进/状态转移事件**，故以常量 + 纯变量替换函数承载，由
 * CaptureHook 在事件发生时经既有 onStagePrompt 通道投递（与里程碑提醒同通道）。
 *
 * 变量契约：{id} = 台账需求 id（**含 REQ- 前缀**，如 REQ-260923222557-d3b0），模板不再自带
 * REQ- 前缀（避免 REQ-REQ- 双前缀）；{task_id}/{task_title} 为任务上下文。
 *
 * 设计：纯函数、零 I/O、零 Date.now（可单测）；文本中的 {id}/{task_id}/{task_title}
 * 注入前替换，缺失变量置空串（不留花括号残骸）。
 *
 * @module dsh-pmboard/domain/prompt/worktree-events
 */

/** 事件型提示词的两类触发。 */
export type WorktreeEvent = 'task_done' | 'archived'

export interface WorktreeEventContext {
  /** 台账需求 id（含 REQ- 前缀），替换 {id} */
  requirementId: string
  /** 任务 id（如 t-abc123），替换 {task_id}；task_done 用 */
  taskId?: string
  /** 任务标题，替换 {task_title}；task_done 用 */
  taskTitle?: string
}

/** 文本模板（源即事实；替换见 renderWorktreePrompt）。 */
export const WORKTREE_EVENT_TEMPLATES: Readonly<Record<WorktreeEvent, string>> = {
  task_done: [
    '## Worktree 提交检查点（子任务完成）',
    '',
    '子任务「{task_title}」({task_id}) 已完成——请在 worktree 内提交一次，形成检查点：',
    '',
    '- `git add <相关文件>`（只加本任务改动的文件，勿夹带他人改动）',
    '- `git commit -m "feat({id}): 完成子任务 {task_id} — {task_title}"`',
    '',
    '为什么：每个子任务一个检查点，出错可回滚到正确版本，代码演进在审查中可见。',
    '分支约定 `feature/{id}`，目录 `.worktrees/{id}/`；不强制执行，按实际情况判断。',
  ].join('\n'),
  archived: [
    '## Worktree 合并与清理（需求已归档）',
    '',
    '需求 {id} 验收通过并归档——请把 worktree 的改动合并回主线并清理：',
    '',
    '- 切回主工作区：`git merge --no-ff feature/{id}`',
    '- 删除工作树：`git worktree remove .worktrees/{id}/`',
    '- 删除分支：`git branch -d feature/{id}`',
    '',
    '验证：主分支包含本次改动、`.worktrees/{id}/` 已不存在、分支已删除。不强制执行，按实际情况判断。',
  ].join('\n'),
}

/** 变量替换：{id}/{task_id}/{task_title}；缺失变量置空串。 */
export function renderWorktreePrompt(event: WorktreeEvent, ctx: WorktreeEventContext): string {
  return WORKTREE_EVENT_TEMPLATES[event]
    .replace(/\{id\}/g, ctx.requirementId)
    .replace(/\{task_id\}/g, ctx.taskId ?? '')
    .replace(/\{task_title\}/g, ctx.taskTitle ?? '')
}
