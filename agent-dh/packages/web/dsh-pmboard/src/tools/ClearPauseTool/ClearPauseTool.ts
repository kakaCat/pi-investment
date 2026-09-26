/**
 * ClearPauseTool 工具壳（REQ-260925212722-96e7）
 *
 * 清除 Dive 模式的 armed 状态，允许手动操作。
 *
 * @module dsh-pmboard/tools/ClearPauseTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import type { UseCaseDeps } from '../../application/ports.js'
import { clearPause } from '../../application/use-cases/ClearPause.js'
import { CLEAR_PAUSE_PROMPT } from './prompt.js'

export function defineClearPauseTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_clear_pause',
    description: CLEAR_PAUSE_PROMPT,
    parameters: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          requirement_id: {
            type: 'string',
            description: '需求 id（REQ-xxxxxx）；不传则默认本窗口绑定的需求'
          }
        }
      }
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          requirement_id: { type: 'string', description: '需求 id' },
          previous_activation: { type: 'string', description: '之前的 activation 状态' },
          message: { type: 'string', description: '结果消息' }
        }
      }
    },
    async execute(input, context: ToolRunContext) {
      const windowKey = context.session?.id ?? 'unknown'
      return await clearPause(deps, windowKey, input)
    }
  })
}
