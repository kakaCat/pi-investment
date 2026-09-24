/**
 * reqboard_note_interruption 提示词（REQ-260924213231-b1c4 T-9 / I-8）——断点显式兜底。
 *
 * 单字面量（不拼接）：消息卫生棘轮要求 tools 层拼接数只降不升，新消息一律不用 \`+\` 拼。
 *
 * @module dsh-pmboard/tools/NoteInterruptionTool/prompt
 */
export const NOTE_INTERRUPTION_PROMPT =
  `补写断点（续跑有据的显式兜底）：交棒工具成功时 pmboard 已自动写下断点（当前阶段 + 下一步命令）；本工具用于事件入口不可得（旧 DSH 版本 / turn/end 形态变化）或 agent 自己发现上一回合被中断时，把中断原因原文补进需求台账。reason 必填（如 upstream stream idle 3m ×5）；缺省作用于本窗口绑定的进行中需求，也可用 requirement_id 显式指定。同一需求只保留一个断点（后写覆盖前写），pendingAction 按当前状态重算。写入后新窗口重建节点输入包即可看到「## 断点」节。reason 为空 → REQBOARD_INVALID_INPUT；本窗口无绑定需求 → REQBOARD_NO_BOUND_REQ。`;
