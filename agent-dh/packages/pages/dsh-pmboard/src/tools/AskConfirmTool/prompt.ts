/**
 * reqboard_ask_confirm 提示词（REQ-47939a t8）——弹框确认（原 reqboard_ask_confirm）与
 * 会话落章（原 reqboard_confirm_artifact）合并为一条路：**弹框落章只剩一条路**（设计 §4.3）。
 *
 * @module dsh-pmboard/tools/AskConfirmTool/prompt
 */
export const ASK_CONFIRM_PROMPT =
  '关键确认（原子化：确认 → 落章 → 推进一次完成）。两条路径，自动选择：'
  + '① 弹框路径（不传 evidence）：把问题弹给用户，肯定项 → 自动落章并推进到下一阶段；'
  + '选"需修改/暂停" → 不推进并留痕；subagent/无 UI 通道时返回 fallback=board（请用户走看板确认按钮）；'
  + '适用：阶段产物确认（target=artifact, kind=requirement/plan/decomposition/verification/archive）、'
  + '批准拆分计划（target=plan）。'
  + '② 文字证据路径（传 evidence）：把用户在 ask_user_question 中的明确答复原文落成与看板一键确认'
  + '同等效力的人工确认（审计凭据，evidence 必填）——evidence 必须命中该窗口近期真实用户消息原文，'
  + '编造/曲解会被代码级拒绝（REQBOARD_EVIDENCE_FAKE）。'
