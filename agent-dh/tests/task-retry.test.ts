/**
 * 任务执行失败重试测试
 * 验证 resume_from 功能
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { generateStages } from '../packages/web/dsh-pmboard/src/tools/TaskExecuteTool/generate-stages.js'
import type { TaskInfo } from '../packages/web/dsh-pmboard/src/tools/TaskExecuteTool/types.js'

describe('任务执行失败重试', () => {
  const mockTask: TaskInfo = {
    id: 't-retry-test',
    title: '测试失败重试',
    description: '模拟任务执行失败后重试',
    acceptance: '测试通过',
    implementation: '实现功能',
    context: '测试上下文',
    side: 'backend',
    requirementId: 'REQ-test'
  }

  describe('resume_from 参数', () => {
    it('应该从指定阶段开始执行', () => {
      // 模拟从第 3 阶段恢复
      const stages = generateStages(mockTask, 3)
      
      expect(stages).toHaveLength(4) // 阶段 3-6
      expect(stages[0].stage).toBe(3)
      expect(stages[0].name).toBe('代码实现')
      expect(stages[1].stage).toBe(4)
      expect(stages[2].stage).toBe(5)
      expect(stages[3].stage).toBe(6)
    })

    it('应该跳过已完成的阶段', () => {
      // 从第 1 阶段开始
      const allStages = generateStages(mockTask)
      
      // 从第 4 阶段恢复
      const resumeStages = generateStages(mockTask, 4)
      
      // 应该跳过前 3 个阶段
      expect(allStages).toHaveLength(6)
      expect(resumeStages).toHaveLength(3) // 阶段 4-6
      expect(resumeStages[0].stage).toBe(4)
    })

    it('应该支持从任意阶段恢复', () => {
      // 测试各个阶段
      for (let stage = 1; stage <= 6; stage++) {
        const stages = generateStages(mockTask, stage)
        expect(stages[0].stage).toBe(stage)
        expect(stages).toHaveLength(6 - stage + 1)
      }
    })
  })

  describe('失败场景模拟', () => {
    it('模拟阶段 1 失败，从阶段 1 重试', () => {
      // 第一次执行（失败）
      const firstRun = generateStages(mockTask)
      expect(firstRun[0].stage).toBe(1)
      
      // 重试（从阶段 1 开始）
      const retry = generateStages(mockTask, 1)
      expect(retry[0].stage).toBe(1)
      expect(retry).toHaveLength(6)
    })

    it('模拟阶段 3 失败，从阶段 3 恢复', () => {
      // 假设前 2 个阶段已完成
      const stages = generateStages(mockTask, 3)
      
      expect(stages[0].stage).toBe(3)
      expect(stages[0].name).toBe('代码实现')
      expect(stages).toHaveLength(4) // 只执行阶段 3-6
    })

    it('模拟最后阶段失败，只重试最后阶段', () => {
      const stages = generateStages(mockTask, 6)
      
      expect(stages).toHaveLength(1)
      expect(stages[0].stage).toBe(6)
      expect(stages[0].name).toBe('文档汇报')
    })
  })

  describe('边界情况', () => {
    it('resume_from 为 1 应该执行全部阶段', () => {
      const stages = generateStages(mockTask, 1)
      expect(stages).toHaveLength(6)
      expect(stages[0].stage).toBe(1)
    })

    it('resume_from 为 6 应该只执行最后阶段', () => {
      const stages = generateStages(mockTask, 6)
      expect(stages).toHaveLength(1)
      expect(stages[0].stage).toBe(6)
    })

    it('不传 resume_from 应该执行全部阶段', () => {
      const stages = generateStages(mockTask)
      expect(stages).toHaveLength(6)
      expect(stages[0].stage).toBe(1)
    })

    it('resume_from 超出范围应该仍能工作', () => {
      // 从阶段 7 恢复（超出范围）
      const stages = generateStages(mockTask, 7)
      expect(stages).toHaveLength(0) // 没有阶段
    })
  })

  describe('不同任务类型的重试', () => {
    it('文档任务应该有 4 个阶段', () => {
      const docTask: TaskInfo = {
        ...mockTask,
        side: 'doc'
      }
      
      const stages = generateStages(docTask)
      expect(stages).toHaveLength(4)
    })

    it('文档任务从阶段 2 恢复', () => {
      const docTask: TaskInfo = {
        ...mockTask,
        side: 'doc'
      }
      
      const stages = generateStages(docTask, 2)
      expect(stages).toHaveLength(3) // 阶段 2-4
      expect(stages[0].stage).toBe(2)
    })
  })

  describe('任务信息保留', () => {
    it('恢复时应该保留原任务信息', () => {
      const stages = generateStages(mockTask, 3)
      
      // 检查任务信息是否仍在模板中
      expect(stages[0].promptTemplate).toContain(mockTask.title)
      expect(stages[0].promptTemplate).toContain(mockTask.acceptance)
      expect(stages[0].promptTemplate).toContain(mockTask.implementation)
    })

    it('所有阶段都应该有完整的任务上下文', () => {
      const stages = generateStages(mockTask, 3)
      
      stages.forEach(stage => {
        expect(stage.promptTemplate).toBeTruthy()
        expect(stage.promptTemplate.length).toBeGreaterThan(0)
      })
    })
  })
})
