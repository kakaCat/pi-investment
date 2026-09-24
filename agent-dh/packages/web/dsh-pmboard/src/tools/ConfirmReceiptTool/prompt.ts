/**
 * reqboard_confirm_receipt 提示词（REQ-260924213231-b1c4 T-6 / I-4）——非阻塞弹框的取件口。
 *
 * 单字面量（不拼接）：消息卫生棘轮要求 tools 层拼接数只降不升，新消息一律不再用 \`+\` 拼。
 *
 * @module dsh-pmboard/tools/ConfirmReceiptTool/prompt
 */
export const CONFIRM_RECEIPT_PROMPT =
  `挂起确认回执（非阻塞弹框的取件口）：reqboard_ask_confirm 返回 pending=true 时，问题已投递、人作答后由后台自动落章/推进。凭返回的 ticket 调本工具取回执——confirmed 以台账为准（产物 confirmedAt / 计划 approvedAt 已写 → true），advanced 与 from/to 还原推进前后阶段；尚未作答时如实返回 confirmed=false。ticket 未知/不属于本窗口/已过期 → REQBOARD_UNKNOWN_TICKET：不要重试猜 ticket，改调 reqboard_status 读 design_docs[].confirmed（以台账为准）。`
