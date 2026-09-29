/**
 * card-types.ts 联调测试（REQ-260927182328-6e7d integrate 阶段）
 *
 * 验证内容：
 * 1. 四轴枚举完整性
 * 2. 颜色映射表覆盖率
 * 3. 工具函数返回值正确性
 * 4. 类型导出可用性
 */

import { describe, it, expect } from 'vitest'
import type { StageKind } from '../task/SubtaskTemplate.js'
import type { TaskRole, TaskStatus } from '../task/TaskStatus.js'
import {
  PHASE_COLOR_FAMILIES,
  type PhaseColorFamily,
  STAGE_TO_PHASE_COLOR,
  PHASE_COLOR_MAP,
  SIDES,
  type Side,
  SIDE_LABELS,
  SIDE_COLOR_MAP,
  ROLE_LABELS,
  STATUS_COLOR_MAP,
  STATUS_LABELS,
  getPhaseColor,
  getSideColor,
  getStatusColor,
} from '../card-types.js'

describe('card-types 联调测试', () => {
  describe('Phase（阶段）类型系统', () => {
    it('应定义 7 种颜色族', () => {
      expect(PHASE_COLOR_FAMILIES).toHaveLength(7)
      expect(PHASE_COLOR_FAMILIES).toEqual([
        'dev-family',
        'review-family',
        'test-family',
        'debug-family',
        'research-family',
        'data-family',
        'ops-family',
      ])
    })

    it('STAGE_TO_PHASE_COLOR 应覆盖全部 16 种 StageKind', () => {
      const expectedStages: StageKind[] = [
        'dev', 'integrate', 'review', 'test', 'repro', 'fix', 'regress',
        'probe', 'collect', 'analyze', 'prepare', 'run', 'verify',
        'change', 'dryrun', 'apply',
      ]
      
      const mappedStages = Object.keys(STAGE_TO_PHASE_COLOR) as StageKind[]
      expect(mappedStages).toHaveLength(16)
      
      expectedStages.forEach(stage => {
        expect(STAGE_TO_PHASE_COLOR).toHaveProperty(stage)
        expect(PHASE_COLOR_FAMILIES).toContain(STAGE_TO_PHASE_COLOR[stage])
      })
    })

    it('PHASE_COLOR_MAP 应包含全部 7 种颜色族的映射', () => {
      PHASE_COLOR_FAMILIES.forEach(family => {
        expect(PHASE_COLOR_MAP).toHaveProperty(family)
        expect(PHASE_COLOR_MAP[family]).toMatch(/^#[0-9a-f]{6}$/i)
      })
    })

    it('getPhaseColor 应返回正确的颜色值', () => {
      const testCases: Array<[StageKind, string]> = [
        ['dev', '#3b82f6'],
        ['integrate', '#3b82f6'],
        ['review', '#8b5cf6'],
        ['test', '#10b981'],
        ['repro', '#f59e0b'],
      ]

      testCases.forEach(([stage, expectedColor]) => {
        expect(getPhaseColor(stage)).toBe(expectedColor)
      })
    })
  })

  describe('Side（端别）类型系统', () => {
    it('应定义 4 种端别', () => {
      expect(SIDES).toHaveLength(4)
      expect(SIDES).toEqual(['frontend', 'backend', 'fullstack', 'doc'])
    })

    it('SIDE_LABELS 应包含全部 4 种端别的中文标签', () => {
      SIDES.forEach(side => {
        expect(SIDE_LABELS).toHaveProperty(side)
        expect(SIDE_LABELS[side]).toBeTruthy()
      })
    })

    it('SIDE_COLOR_MAP 应包含全部 4 种端别的颜色映射', () => {
      SIDES.forEach(side => {
        expect(SIDE_COLOR_MAP).toHaveProperty(side)
        expect(SIDE_COLOR_MAP[side]).toMatch(/^#[0-9a-f]{6}$/i)
      })
    })

    it('getSideColor 应返回正确的颜色值', () => {
      const testCases: Array<[Side, string]> = [
        ['frontend', '#3b82f6'],
        ['backend', '#10b981'],
        ['fullstack', '#8b5cf6'],
        ['doc', '#6b7280'],
      ]

      testCases.forEach(([side, expectedColor]) => {
        expect(getSideColor(side)).toBe(expectedColor)
      })
    })
  })

  describe('Role（角色）类型系统', () => {
    it('ROLE_LABELS 应包含全部 3 种角色的中文标签', () => {
      const expectedRoles: TaskRole[] = ['parent', 'subtask', 'legacy']
      
      expectedRoles.forEach(role => {
        expect(ROLE_LABELS).toHaveProperty(role)
        expect(ROLE_LABELS[role]).toBeTruthy()
      })
    })
  })

  describe('Status（状态）类型系统', () => {
    it('STATUS_COLOR_MAP 应包含全部 7 种状态的颜色映射', () => {
      const expectedStatuses: TaskStatus[] = [
        'todo', 'in_progress', 'integrating', 'testing', 
        'in_review', 'done', 'canceled',
      ]
      
      expectedStatuses.forEach(status => {
        expect(STATUS_COLOR_MAP).toHaveProperty(status)
        expect(STATUS_COLOR_MAP[status]).toMatch(/^#[0-9a-f]{6}$/i)
      })
    })

    it('STATUS_LABELS 应包含全部 7 种状态的中文标签', () => {
      const expectedStatuses: TaskStatus[] = [
        'todo', 'in_progress', 'integrating', 'testing', 
        'in_review', 'done', 'canceled',
      ]
      
      expectedStatuses.forEach(status => {
        expect(STATUS_LABELS).toHaveProperty(status)
        expect(STATUS_LABELS[status]).toBeTruthy()
      })
    })

    it('getStatusColor 应返回正确的底色', () => {
      const testCases: Array<[TaskStatus, string]> = [
        ['todo', '#e5e7eb'],
        ['in_progress', '#3b82f6'],
        ['integrating', '#f59e0b'],
        ['testing', '#eab308'],
        ['in_review', '#8b5cf6'],
        ['done', '#10b981'],
        ['canceled', '#6b7280'],
      ]

      testCases.forEach(([status, expectedColor]) => {
        expect(getStatusColor(status)).toBe(expectedColor)
      })
    })
  })

  describe('类型导出', () => {
    it('应能够使用导出的类型', () => {
      // 类型检查（编译时验证）
      const family: PhaseColorFamily = 'dev-family'
      const side: Side = 'frontend'
      
      expect(family).toBe('dev-family')
      expect(side).toBe('frontend')
    })
  })

  describe('边界情况', () => {
    it('所有颜色值应为有效的 hex 格式', () => {
      const allColors = [
        ...Object.values(PHASE_COLOR_MAP),
        ...Object.values(SIDE_COLOR_MAP),
        ...Object.values(STATUS_COLOR_MAP),
      ]
      
      allColors.forEach(color => {
        expect(color).toMatch(/^#[0-9a-f]{6}$/i)
      })
    })

    it('中文标签不应为空字符串', () => {
      const allLabels = [
        ...Object.values(SIDE_LABELS),
        ...Object.values(ROLE_LABELS),
        ...Object.values(STATUS_LABELS),
      ]
      
      allLabels.forEach(label => {
        expect(label).toBeTruthy()
        expect(label.length).toBeGreaterThan(0)
      })
    })
  })
})
