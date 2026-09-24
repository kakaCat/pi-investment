/**
 * reqboard_note_interruption 工具壳（REQ-260924213231-b1c4 T-9 · serves: FR-6 / I-8）——断点补写。
 *
 * 三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）+ execute 委托 application 用例。
 * 响应字段与 interfaces.md I-8 字段明细一一对应（success/requirement_id/interruption/note）。
 *
 * @module dsh-pmboard/tools/NoteInterruptionTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { noteInterruption } from '../../application/use-cases/NoteInterruption.js'
import { renderSmart } from '../shared.js'
import { noteInterruptionSummary } from '../render-summaries.js'
import { NOTE_INTERRUPTION_PROMPT } from './prompt.js'

export function defineNoteInterruptionTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_note_interruption',
    description: NOTE_INTERRUPTION_PROMPT,
    parameters: {
      reason: {
        type: 'string',
        description: '中断原因原文（如 upstream stream idle 3m）；必填',
        required: true,
      },
      requirement_id: {
        type: 'string',
        description: '需求 id（REQ-xxxxxx）；缺省 = 本窗口绑定的进行中需求',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string', description: '被补写断点的需求 id' },
          interruption: {
            type: 'object',
            additionalProperties: false,
            properties: {
              at: { type: 'number', description: '中断/检查点时间戳（ms）' },
              reason: { type: 'string', description: '中断原因原文；交棒检查点写 checkpoint' },
              stage: { type: 'string', description: '断点时的流水线阶段' },
              pendingAction: { type: 'string', description: '未完成动作（下一步工具命令）' },
              tool: { type: 'string', description: '最后成功调用的工具名（可缺省）' },
            },
          },
          note: { type: 'string', description: '回执结论一句话（人话）' },
        },
      },
      render: renderSmart(noteInterruptionSummary),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    execute: async (args: unknown, exec: ToolRunContext) => noteInterruption(deps, args, exec),
  } as any)
}
