/**
 * 卡片四轴类型系统联调测试（REQ-260927182328-6e7d t-4d579e integrate）
 * 
 * 验收标准：接口联调通过——给出请求样例与期望响应，实际返回与预期一致。
 */

import { describe, it, expect } from 'vitest'
import {
  PHASE_COLOR_FAMILIES,
  STAGE_TO_PHASE_COLOR,
  PHASE_COLOR_MAP,
  SIDES,
  SIDE_LABELS,
  SIDE_COLOR_MAP,
  ROLE_LABELS,
  STATUS_COLOR_MAP,
  STATUS_LABELS,
  getPhaseColor,
  getSideColor,
  getStatusColor,
  type PhaseColorFamily,
  type Side,
  type TaskRole,
  type TaskStatus,
} from '../../src/domain/card-types.js'

describe('卡片四轴类型系统 - 联调测试', () => {
  describe('Phase（阶段）维度', () => {
    it('应返回7个颜色族', () => {
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

    it('应正确映射 StageKind → Phase 颜色族', () => {
      // 研发族
      expect(STAGE_TO_PHASE_COLOR.dev).toBe('dev-family')
      expect(STAGE_TO_PHASE_COLOR.integrate).toBe('dev-family')
      
      // 复核族
      expect(STAGE_TO_PHASE_COLOR.review).toBe('review-family')
      
      // 测试族
      expect(STAGE_TO_PHASE_COLOR.test).toBe('test-family')
      expect(STAGE_TO_PHASE_COLOR.regress).toBe('test-family')
      
      // 调试族
      expect(STAGE_TO_PHASE_COLOR.repro).toBe('debug-family')
      expect(STAGE_TO_PHASE_COLOR.fix).toBe('debug-family')
      
      // 调研族
      expect(STAGE_TO_PHASE_COLOR.probe).toBe('research-family')
      expect(STAGE_TO_PHASE_COLOR.collect).toBe('research-family')
      expect(STAGE_TO_PHASE_COLOR.analyze).toBe('research-family')
      
      // 数据族
      expect(STAGE_TO_PHASE_COLOR.prepare).toBe('data-family')
      expect(STAGE_TO_PHASE_COLOR.run).toBe('data-family')
      expect(STAGE_TO_PHASE_COLOR.verify).toBe('data-family')
      
      // 运维族
      expect(STAGE_TO_PHASE_COLOR.change).toBe('ops-family')
      expect(STAGE_TO_PHASE_COLOR.dryrun).toBe('ops-family')
      expect(STAGE_TO_PHASE_COLOR.apply).toBe('ops-family')
    })

    it('应为每个颜色族返回颜色值', () => {
      expect(PHASE_COLOR_MAP['dev-family']).toBe('#3b82f6')
      expect(PHASE_COLOR_MAP['review-family']).toBe('#8b5cf6')
      expect(PHASE_COLOR_MAP['test-family']).toBe('#10b981')
      expect(PHASE_COLOR_MAP['debug-family']).toBe('#f59e0b')
      expect(PHASE_COLOR_MAP['research-family']).toBe('#06b6d4')
      expect(PHASE_COLOR_MAP['data-family']).toBe('#6366f1')
      expect(PHASE_COLOR_MAP['ops-family']).toBe('#ef4444')
    })

    it('getPhaseColor() 应返回正确颜色', () => {
      expect(getPhaseColor('dev')).toBe('#3b82f6')
      expect(getPhaseColor('integrate')).toBe('#3b82f6')
      expect(getPhaseColor('review')).toBe('#8b5cf6')
      expect(getPhaseColor('test')).toBe('#10b981')
    })
  })

  describe('Side（端别）维度', () => {
    it('应返回4种端别', () => {
      expect(SIDES).toHaveLength(4)
      expect(SIDES).toEqual(['frontend', 'backend', 'fullstack', 'doc'])
    })

    it('应为每种端别返回中文标签', () => {
      expect(SIDE_LABELS.frontend).toBe('前端')
      expect(SIDE_LABELS.backend).toBe('后端')
      expect(SIDE_LABELS.fullstack).toBe('全栈')
      expect(SIDE_LABELS.doc).toBe('文档')
    })

    it('应为每种端别返回颜色值', () => {
      expect(SIDE_COLOR_MAP.frontend).toBe('#3b82f6')
      expect(SIDE_COLOR_MAP.backend).toBe('#10b981')
      expect(SIDE_COLOR_MAP.fullstack).toBe('#8b5cf6')
      expect(SIDE_COLOR_MAP.doc).toBe('#6b7280')
    })

    it('getSideColor() 应返回正确颜色', () => {
      expect(getSideColor('frontend')).toBe('#3b82f6')
      expect(getSideColor('backend')).toBe('#10b981')
      expect(getSideColor('fullstack')).toBe('#8b5cf6')
      expect(getSideColor('doc')).toBe('#6b7280')
    })
  })

  describe('Role（角色）维度', () => {
    it('应为每种角色返回中文标签', () => {
      expect(ROLE_LABELS.parent).toBe('父卡')
      expect(ROLE_LABELS.subtask).toBe('子卡')
      expect(ROLE_LABELS.legacy).toBe('存量卡')
    })
  })

  describe('Status（状态）维度', () => {
    it('应为每种状态返回底色', () => {
      expect(STATUS_COLOR_MAP.todo).toBe('#e5e7eb')
      expect(STATUS_COLOR_MAP.in_progress).toBe('#3b82f6')
      expect(STATUS_COLOR_MAP.integrating).toBe('#f59e0b')
      expect(STATUS_COLOR_MAP.testing).toBe('#eab308')
      expect(STATUS_COLOR_MAP.in_review).toBe('#8b5cf6')
      expect(STATUS_COLOR_MAP.done).toBe('#10b981')
      expect(STATUS_COLOR_MAP.canceled).toBe('#6b7280')
    })

    it('应为每种状态返回中文标签', () => {
      expect(STATUS_LABELS.todo).toBe('待开始')
      expect(STATUS_LABELS.in_progress).toBe('进行中')
      expect(STATUS_LABELS.integrating).toBe('联调中')
      expect(STATUS_LABELS.testing).toBe('测试中')
      expect(STATUS_LABELS.in_review).toBe('待复核')
      expect(STATUS_LABELS.done).toBe('已完成')
      expect(STATUS_LABELS.canceled).toBe('已取消')
    })

    it('getStatusColor() 应返回正确颜色', () => {
      expect(getStatusColor('todo')).toBe('#e5e7eb')
      expect(getStatusColor('in_progress')).toBe('#3b82f6')
      expect(getStatusColor('integrating')).toBe('#f59e0b')
      expect(getStatusColor('testing')).toBe('#eab308')
      expect(getStatusColor('in_review')).toBe('#8b5cf6')
      expect(getStatusColor('done')).toBe('#10b981')
      expect(getStatusColor('canceled')).toBe('#6b7280')
    })
  })

  describe('联调验收 - 综合场景', () => {
    it('场景1：获取 integrate 阶段的卡片颜色', () => {
      const stage = 'integrate'
      const phaseColor = getPhaseColor(stage)
      
      // 期望：integrate 属于 dev-family，颜色为蓝色
      expect(phaseColor).toBe('#3b82f6')
    })

    it('场景2：获取前端卡片的端别颜色', () => {
      const side: Side = 'frontend'
      const sideColor = getSideColor(side)
      const sideLabel = SIDE_LABELS[side]
      
      // 期望：前端为蓝色，标签为"前端"
      expect(sideColor).toBe('#3b82f6')
      expect(sideLabel).toBe('前端')
    })

    it('场景3：获取联调中状态的底色', () => {
      const status: TaskStatus = 'integrating'
      const statusColor = getStatusColor(status)
      const statusLabel = STATUS_LABELS[status]
      
      // 期望：联调中为橙色，标签为"联调中"
      expect(statusColor).toBe('#f59e0b')
      expect(statusLabel).toBe('联调中')
    })

    it('场景4：获取父卡角色的标签', () => {
      const role: TaskRole = 'parent'
      const roleLabel = ROLE_LABELS[role]
      
      // 期望：父卡标签为"父卡"
      expect(roleLabel).toBe('父卡')
    })

    it('场景5：完整卡片四轴查询', () => {
      // 模拟一张卡片：integrate 阶段、前端、父卡、联调中
      const card = {
        stage: 'integrate' as const,
        side: 'frontend' as Side,
        role: 'parent' as TaskRole,
        status: 'integrating' as TaskStatus,
      }

      const result = {
        phaseColor: getPhaseColor(card.stage),
        sideColor: getSideColor(card.side),
        sideLabel: SIDE_LABELS[card.side],
        roleLabel: ROLE_LABELS[card.role],
        statusColor: getStatusColor(card.status),
        statusLabel: STATUS_LABELS[card.status],
      }

      // 期望响应
      const expected = {
        phaseColor: '#3b82f6',   // dev-family 蓝色
        sideColor: '#3b82f6',    // 前端蓝色
        sideLabel: '前端',
        roleLabel: '父卡',
        statusColor: '#f59e0b',  // 联调中橙色
        statusLabel: '联调中',
      }

      expect(result).toEqual(expected)
    })
  })
})
