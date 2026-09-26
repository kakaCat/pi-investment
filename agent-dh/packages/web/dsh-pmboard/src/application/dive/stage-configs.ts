/**
 * Dive 模式阶段配置（REQ-260925212722-96e7）
 *
 * 定义每个需求阶段的自动化行为：是否需要人工确认、是否自动执行、回合数限制。
 *
 * @module dsh-pmboard/application/dive/stage-configs
 */

import type { RequirementStatus } from '../../shared/protocol.js'

/** 阶段配置接口 */
export interface StageConfig {
  /** 是否需要人工确认才能推进到下一阶段 */
  requiresConfirmation: boolean
  
  /** 是否自动执行任务（implementing 阶段适用） */
  autoExecute: boolean
  
  /** 每阶段最大回合数限制（防止无限循环） */
  maxRounds: number
  
  /** 阶段描述 */
  description: string
}

/** 所有阶段的配置映射 */
export const STAGE_CONFIGS: Readonly<Record<RequirementStatus, StageConfig>> = {
  // 立项阶段：草稿状态，无 Dive 行为
  draft: {
    requiresConfirmation: false,
    autoExecute: false,
    maxRounds: 1,
    description: '立项草稿，无自动化行为'
  },
  
  // 需求分析阶段：头脑风暴，需要人工确认需求文档
  brainstorming: {
    requiresConfirmation: true,
    autoExecute: false,
    maxRounds: 10,
    description: '需求分析阶段，需人工确认需求文档'
  },
  
  // 设计阶段：编写设计文档，需要人工确认设计
  design: {
    requiresConfirmation: true,
    autoExecute: false,
    maxRounds: 10,
    description: '设计阶段，需人工确认设计文档'
  },
  
  // 拆分阶段：编写拆分计划，需要人工批准计划
  decomposing: {
    requiresConfirmation: true,
    autoExecute: false,
    maxRounds: 5,
    description: '拆分阶段，需人工批准拆分计划'
  },
  
  // 实施阶段：全自动执行任务，无需人工确认（Dive 模式核心）
  implementing: {
    requiresConfirmation: false,
    autoExecute: true,
    maxRounds: 100, // 任务数量可能较多
    description: '实施阶段，全自动执行任务（Dive 模式）'
  },
  
  // 验收阶段：需要人工验收
  accepting: {
    requiresConfirmation: true,
    autoExecute: true,
    maxRounds: 5,
    description: '验收阶段，需人工验收'
  },
  
  // 已完成：无后续行为
  done: {
    requiresConfirmation: false,
    autoExecute: false,
    maxRounds: 1,
    description: '已完成，无后续行为'
  },
  
  // 已归档：无后续行为
  archived: {
    requiresConfirmation: false,
    autoExecute: false,
    maxRounds: 1,
    description: '已归档，无后续行为'
  },
  
  // 已取消：无后续行为
  canceled: {
    requiresConfirmation: false,
    autoExecute: false,
    maxRounds: 1,
    description: '已取消，无后续行为'
  }
}

/**
 * 获取指定阶段的配置
 */
export function getStageConfig(stage: RequirementStatus): StageConfig {
  return STAGE_CONFIGS[stage]
}

/**
 * 检查阶段是否需要人工确认
 */
export function requiresConfirmation(stage: RequirementStatus): boolean {
  return STAGE_CONFIGS[stage].requiresConfirmation
}

/**
 * 检查阶段是否自动执行
 */
export function isAutoExecute(stage: RequirementStatus): boolean {
  return STAGE_CONFIGS[stage].autoExecute
}

/**
 * 获取阶段的最大回合数
 */
export function getMaxRounds(stage: RequirementStatus): number {
  return STAGE_CONFIGS[stage].maxRounds
}
