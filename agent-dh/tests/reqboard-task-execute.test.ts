/**
 * reqboard_task_execute 工具测试
 */

import { describe, it, expect, vi } from 'vitest'
import { generateStages } from '../packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/generate-stages.js'
import { generateWorkflowScript } from '../packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/generate-workflow-script.js'
import type { TaskInfo } from '../packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/types.js'

describe('reqboard_task_execute', () => {
  const mockTask: TaskInfo = {
    id: 't-test-001',
    title: '实现测试功能',
    description: '这是一个测试任务',
    acceptance: 'npx vitest run tests/example.test.ts 通过',
    implementation: '实现 foo() 函数',
    context: '测试上下文',
    side: 'backend',
    requirementId: 'REQ-test'
  }

  describe('generateStages', () => {
    it('应该为后端任务生成 6 个阶段', () => {
      const stages = generateStages(mockTask)
      
      expect(stages).toHaveLength(6)
      expect(stages[0].name).toBe('需求分析')
      expect(stages[1].name).toBe('方案设计')
      expect(stages[2].name).toBe('代码实现')
      expect(stages[3].name).toBe('单元测试')
      expect(stages[4].name).toBe('集成测试')
      expect(stages[5].name).toBe('文档汇报')
    })

    it('应该填充任务信息到模板', () => {
      const stages = generateStages(mockTask)
      
      // 检查模板变量是否被替换
      expect(stages[0].promptTemplate).toContain(mockTask.title)
      expect(stages[0].promptTemplate).toContain(mockTask.acceptance)
    })

    it('应该支持从指定阶段恢复', () => {
      const stages = generateStages(mockTask, 3)
      
      expect(stages).toHaveLength(4) // 阶段 3-6
      expect(stages[0].stage).toBe(3)
      expect(stages[0].name).toBe('代码实现')
    })

    it('应该为文档任务生成 4 个阶段', () => {
      const docTask: TaskInfo = { ...mockTask, side: 'doc' }
      const stages = generateStages(docTask)
      
      expect(stages).toHaveLength(4)
      expect(stages[0].name).toBe('需求分析')
      expect(stages[3].name).toBe('审校')
    })
  })

  describe('generateWorkflowScript', () => {
    it('应该生成有效的 JavaScript 脚本', () => {
      const script = generateWorkflowScript(mockTask)
      
      // 检查脚本包含关键元素
      expect(script).toContain('const results = []')
      expect(script).toContain('await ctx.subagent')
      expect(script).toContain('return { success: true')
      expect(script).toContain('阶段1')
      expect(script).toContain('阶段6')
    })

    it('生成的脚本应该调用 6 次 subagent', () => {
      const script = generateWorkflowScript(mockTask)
      
      const subagentCalls = (script.match(/await ctx\.subagent/g) || []).length
      expect(subagentCalls).toBe(6)
    })

    it('应该支持从指定阶段恢复', () => {
      const script = generateWorkflowScript(mockTask, 4)
      
      const subagentCalls = (script.match(/await ctx\.subagent/g) || []).length
      expect(subagentCalls).toBe(3) // 阶段 4-6
    })

    it('生成的脚本应该包含任务信息', () => {
      const script = generateWorkflowScript(mockTask)
      
      expect(script).toContain(mockTask.id)
      expect(script).toContain(mockTask.title)
    })
  })
})
