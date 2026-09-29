/**
 * card-types.ts 联调测试（REQ-260927182328-6e7d integrate 阶段）
 */

import { describe, it, expect } from 'vitest'
import type { StageKind } from '../src/domain/task/SubtaskTemplate.js'
import type { TaskRole, TaskStatus } from '../src/domain/task/TaskStatus.js'
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
} from '../src/domain/card-types.js'

describe('card-types 联调测试', () => {
  it('Phase 系统：7种颜色族', () => {
    expect(PHASE_COLOR_FAMILIES).toHaveLength(7)
  })

  it('Phase 系统：覆盖16种StageKind', () => {
    expect(Object.keys(STAGE_TO_PHASE_COLOR)).toHaveLength(16)
  })

  it('Phase 系统：颜色映射完整', () => {
    PHASE_COLOR_FAMILIES.forEach(family => {
      expect(PHASE_COLOR_MAP[family]).toMatch(/^#[0-9a-f]{6}$/i)
    })
  })

  it('Side 系统：4种端别', () => {
    expect(SIDES).toHaveLength(4)
    expect(SIDES).toEqual(['frontend', 'backend', 'fullstack', 'doc'])
  })

  it('Side 系统：颜色映射完整', () => {
    SIDES.forEach(side => {
      expect(SIDE_COLOR_MAP[side]).toMatch(/^#[0-9a-f]{6}$/i)
    })
  })

  it('Status 系统：7种状态颜色映射', () => {
    expect(Object.keys(STATUS_COLOR_MAP)).toHaveLength(7)
  })

  it('工具函数：getPhaseColor', () => {
    expect(getPhaseColor('dev')).toBe('#3b82f6')
  })

  it('工具函数：getSideColor', () => {
    expect(getSideColor('frontend')).toBe('#3b82f6')
  })

  it('工具函数：getStatusColor', () => {
    expect(getStatusColor('done')).toBe('#10b981')
  })
})
