/**
 * TaskTreeTool 提示词（REQ-260927144541-0481 FR-3）——reqboard_task_tree 的工具描述。
 * @module dsh-pmboard/tools/TaskTreeTool/prompt
 */
export const TASK_TREE_PROMPT = [
  '用于：查看父子卡结构（只读）——一条命令看清某条链上有哪几张子卡、各自的子卡阶段（stageKind）、',
  '卡片状态、依赖、是否跑过（lastRunOk）与最近汇报摘要。',
  '入参给 parent_id（父卡 id）或 requirement_id（缺省取本窗口绑定需求）；不传 parent_id 时',
  '列出该需求下全部父卡及其子卡链。无子卡时返回空数组并给 note（尚未展开）。',
  '只读、无副作用、只读本窗口绑定需求。单卡执行细节用 reqboard_task_status；起链用 reqboard_task_run。',
].join('')
