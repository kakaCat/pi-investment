/**
 * reqboard_submit 提示词（REQ-47939a t8）——四个提交工具（requirement / plan / verification /
 * archive）的 description 合并为一条，靠 kind 参数区分（工具面 13→9，设计 §4.3）。
 *
 * @module dsh-pmboard/tools/SubmitTool/prompt
 */
export const SUBMIT_PROMPT =
  '提交阶段产物（kind 区分四类，提交后请人确认/审核）：'
  + 'kind=requirement（brainstorming 阶段）：需求文档已落盘 → 登记 requirement 产物，'
  + '人工确认门（brainstorming→design）要求该产物已登记且经人确认；path 不传默认 '
  + 'docs/requirements/<REQ>/requirement.md，summary 为一句话摘要，change_note 为已确认后重写时的变更原因（必填）。'
  + 'kind=plan（decomposing 拆分阶段；2026-09-21 起设计阶段只写设计文档）：提交拆分计划'
  + '（path=decomposition.md 计划文档、summary=目标+做法、tasks=任务表），'
  + '待人批准后 reqboard_decompose 才能拆分；已批准过再重交必须传 change_note（旧批准作废）。'
  + 'kind=verification（implementing/accepting 阶段）：提交验收材料（summary=交付结论、'
  + 'evidence=可复核证据清单：命令+输出摘要/报告路径/截图路径），需求进入验收态等人工审核。'
  + 'kind=archive（archived/done）：准备归档材料（dir=需求目录、docs=目录内文档清单、'
  + 'merged_into=合并进的项目文档、index_entry=一句话结论、manual_updates/manual_note=说明书更新点），'
  + '必填文档与合法去向按需求类型限定（见 agent-dh/docs/architecture/requirement-archive.md），缺项被代码级拒绝。'
