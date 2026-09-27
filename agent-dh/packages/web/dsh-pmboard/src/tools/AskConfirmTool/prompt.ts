/**
 * reqboard_ask_confirm 提示词（REQ-47939a t8）——弹框确认（原 reqboard_ask_confirm）与
 * 会话落章（原 reqboard_confirm_artifact）合并为一条路：**弹框落章只剩一条路**（设计 §4.3）。
 *
 * REQ-260927123256-196b FR-5 / I-5：等待语义反转——弹框路径**缺省阻塞**（人不作答，agent 就
 * 停在这一步），显式 inline_grace_ms 才是「主动放弃阻塞」的逃生舱。文案是**可证伪契约**
 * （tests/ask-confirm-prompt.test.ts 断言含「缺省阻塞」）。
 *
 * 单字面量（不拼接）：消息卫生棘轮要求 tools 层拼接数只降不升。
 *
 * serves: FR-5（REQ-260927123256-196b t4）——断言见 tests/ask-confirm-prompt.test.ts。
 *
 * @module dsh-pmboard/tools/AskConfirmTool/prompt
 */
export const ASK_CONFIRM_PROMPT =
  `关键确认（原子化：确认 → 落章 → 推进一次完成）。两条路径，自动选择：① 弹框路径（不传 evidence）：把问题弹给用户，**缺省阻塞**——人不作答，agent 就停在这一步（与原生 ask_user_question 的等待语义一致），等到作答 / 取消 / 中止才返回；肯定项 → 自动落章并推进到下一阶段；选"需修改/暂停" → 不推进并留痕。显式传正数 inline_grace_ms = 主动放弃阻塞：超宽限即返回 pending=true + ticket、loop 继续跑，须自行承受到期后 loop 继续的后果，并凭 ticket 调 reqboard_confirm_receipt 取回执。阻塞期间本窗口写路径（reqboard_submit / reqboard_decompose / reqboard_move / reqboard_task_move）被 REQBOARD_CONFIRM_PENDING 拦住；subagent/无 UI 通道时返回 fallback=board（请用户走看板确认按钮）；适用：阶段产物确认（target=artifact, kind=requirement/plan/decomposition/verification/archive）、批准拆分计划（target=plan）。② 文字证据路径（传 evidence）：把用户在 ask_user_question 中的明确答复原文落成与看板一键确认同等效力的人工确认（审计凭据，evidence 必填）——evidence 必须命中该窗口近期真实用户消息原文，编造/曲解会被代码级拒绝（REQBOARD_EVIDENCE_FAKE）。`
