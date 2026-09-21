/**
 * AcceptSheetTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineAcceptSheetTool description 原样搬入。
 * @module dsh-pmboard/tools/AcceptSheetTool/prompt
 */
export const ACCEPT_SHEET_PROMPT = '验收单逐项弹框验收（原子：弹框 → 记录裁决 → 未过项自动返工）。'
      + '每次弹一批待验项（batch_size 默认 5，≤10），选项 通过/改进/其他；'
      + '选"改进/其他"请写意见（自定义输入）。仍有待验项时再次调用本工具从断点继续。'
      + 'subagent/无 UI 通道时返回 fallback=board（请用户走看板勾选）。'
