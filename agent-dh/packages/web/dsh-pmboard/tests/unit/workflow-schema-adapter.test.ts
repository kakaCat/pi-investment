/**
 * Workflow Schema 适配器测试
 */

import { describe, it, expect, vi } from 'vitest'
import {
  executeWithSchema,
  isValidSubtaskOutput,
  createEmptySubtaskOutput,
  type SubtaskOutputSchema,
  type Workflow
} from '../../src/adapters/WorkflowSchemaAdapter.js'

describe('WorkflowSchemaAdapter', () => {
  describe('executeWithSchema', () => {
    it('正常情况：引擎返回符合 schema 的结果', async () => {
      const mockOutput: SubtaskOutputSchema = {
        filesChanged: ['src/domain/test.ts', 'src/app.ts'],
        summary: 'Implemented test feature'
      }
      
      const mockWorkflow: Workflow = {
        agent: vi.fn().mockResolvedValue(mockOutput)
      }
      
      const schema = { type: 'object' }
      const result = await executeWithSchema(mockWorkflow, 'test prompt', schema)
      
      expect(result).toEqual(mockOutput)
      expect(mockWorkflow.agent).toHaveBeenCalledWith('test prompt', { schema })
    })

    it('引擎拒绝：降级为空值', async () => {
      const mockWorkflow: Workflow = {
        agent: vi.fn().mockRejectedValue(new Error('Schema validation failed'))
      }
      
      const schema = { type: 'object' }
      const result = await executeWithSchema(mockWorkflow, 'test prompt', schema)
      
      // 降级返回空值
      expect(result).toEqual({
        filesChanged: [],
        summary: 'schema validation failed'
      })
    })

    it('引擎返回空值：降级处理', async () => {
      const mockWorkflow: Workflow = {
        agent: vi.fn().mockResolvedValue(null)
      }
      
      const result = await executeWithSchema(mockWorkflow, 'test', {})
      
      // null 会被当作失败，降级为空值
      expect(result.filesChanged).toEqual([])
      expect(result.summary).toBe('schema validation failed')
    })

    it('传递 schema 参数', async () => {
      const mockWorkflow: Workflow = {
        agent: vi.fn().mockResolvedValue({ filesChanged: [], summary: 'ok' })
      }
      
      const customSchema = {
        type: 'object',
        properties: {
          filesChanged: { type: 'array' },
          summary: { type: 'string' }
        }
      }
      
      await executeWithSchema(mockWorkflow, 'prompt', customSchema)
      
      expect(mockWorkflow.agent).toHaveBeenCalledWith('prompt', { schema: customSchema })
    })
  })

  describe('isValidSubtaskOutput', () => {
    it('有效的输出', () => {
      const valid: SubtaskOutputSchema = {
        filesChanged: ['file1.ts', 'file2.ts'],
        summary: 'Done'
      }
      
      expect(isValidSubtaskOutput(valid)).toBe(true)
    })

    it('空数组也是有效的', () => {
      const valid = {
        filesChanged: [],
        summary: 'No changes'
      }
      
      expect(isValidSubtaskOutput(valid)).toBe(true)
    })

    it('无效：null', () => {
      expect(isValidSubtaskOutput(null)).toBe(false)
    })

    it('无效：缺少 filesChanged', () => {
      const invalid = {
        summary: 'Done'
      }
      
      expect(isValidSubtaskOutput(invalid)).toBe(false)
    })

    it('无效：filesChanged 不是数组', () => {
      const invalid = {
        filesChanged: 'not an array',
        summary: 'Done'
      }
      
      expect(isValidSubtaskOutput(invalid)).toBe(false)
    })

    it('无效：filesChanged 包含非字符串', () => {
      const invalid = {
        filesChanged: ['file.ts', 123, null],
        summary: 'Done'
      }
      
      expect(isValidSubtaskOutput(invalid)).toBe(false)
    })

    it('无效：缺少 summary', () => {
      const invalid = {
        filesChanged: []
      }
      
      expect(isValidSubtaskOutput(invalid)).toBe(false)
    })

    it('无效：summary 不是字符串', () => {
      const invalid = {
        filesChanged: [],
        summary: 123
      }
      
      expect(isValidSubtaskOutput(invalid)).toBe(false)
    })
  })

  describe('createEmptySubtaskOutput', () => {
    it('创建空输出：默认原因', () => {
      const empty = createEmptySubtaskOutput()
      
      expect(empty).toEqual({
        filesChanged: [],
        summary: 'no output'
      })
    })

    it('创建空输出：自定义原因', () => {
      const empty = createEmptySubtaskOutput('task skipped')
      
      expect(empty).toEqual({
        filesChanged: [],
        summary: 'task skipped'
      })
    })
  })
})
