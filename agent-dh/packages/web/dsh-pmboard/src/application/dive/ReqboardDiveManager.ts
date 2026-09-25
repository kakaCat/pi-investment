/**
 * Dive 模式管理器（REQ-260925212722-96e7）
 *
 * 负责 Dive 模式的核心逻辑：
 * - 检查需求是否处于 Dive 模式（armed && active）
 * - 检查回合数限制（roundsInStage < maxRoundsPerStage）
 * - 发起续跑（调用 ctx.agents.get(agentId).followup()）
 *
 * @module dsh-pmboard/application/dive/ReqboardDiveManager
 */

import { Context, Service } from '@deepseek-ai/cordis'
import { getStageConfig } from './stage-configs.js'
import type { RequirementRecord, RequirementStatus } from '../../shared/protocol.js'

export default class ReqboardDiveManager extends Service {
  static inject = ['agents', 'reqboard']

  constructor(ctx: Context) {
    super(ctx, 'dive-manager')
  }

  /**
   * 检查并继续 Dive 模式执行
   *
   * @param agentId Agent ID
   * @param requirementId 需求 ID（可选，不传则检查该 agent 的所有进行中需求）
   * @returns 是否发起了续跑
   */
  async checkAndContinue(agentId: string, requirementId?: string): Promise<boolean> {
    try {
      // 1. 获取需求
      const requirement = await this.getActiveRequirement(requirementId)
      if (!requirement) {
        this.ctx.logger('dive-manager').debug(`No active requirement found for agent ${agentId}`)
        return false
      }

      // 2. 检查是否处于 Dive 模式
      if (!this.isArmed(requirement)) {
        this.ctx.logger('dive-manager').debug(`Requirement ${requirement.id} is not armed`)
        return false
      }

      // 3. 检查是否处于 active 阶段
      if (!this.isActive(requirement)) {
        this.ctx.logger('dive-manager').debug(`Requirement ${requirement.id} is not active (phase: ${requirement.dive?.phase})`)
        return false
      }

      // 4. 检查回合数限制
      if (!this.canContinue(requirement)) {
        this.ctx.logger('dive-manager').warn(`Requirement ${requirement.id} reached max rounds limit`)
        // 达到回合数限制，暂停 Dive 模式
        await this.pauseDive(requirement.id, 'max_rounds_reached')
        return false
      }

      // 5. 发起续跑
      const agent = this.ctx.agents.get(agentId)
      if (!agent) {
        this.ctx.logger('dive-manager').error(`Agent ${agentId} not found`)
        return false
      }

      await agent.followup(`继续执行需求 ${requirement.id}（Dive 模式，第 ${(requirement.dive?.roundsInStage || 0) + 1} 回合）`)
      
      // 6. 更新回合数
      await this.incrementRound(requirement.id)
      
      this.ctx.logger('dive-manager').info(`Dive mode continued for requirement ${requirement.id}`)
      return true
    } catch (error) {
      this.ctx.logger('dive-manager').error(`Failed to check and continue: ${error}`)
      return false
    }
  }

  /**
   * 检查需求是否 armed（开启 Dive 模式）
   */
  private isArmed(requirement: RequirementRecord): boolean {
    return requirement.dive?.armed === true
  }

  /**
   * 检查需求是否处于 active 阶段
   */
  private isActive(requirement: RequirementRecord): boolean {
    return requirement.dive?.phase === 'active'
  }

  /**
   * 检查是否可以继续（未达到回合数限制）
   */
  private canContinue(requirement: RequirementRecord): boolean {
    const dive = requirement.dive
    if (!dive) return false

    const stageConfig = getStageConfig(requirement.status)
    const roundsInStage = dive.roundsInStage || 0
    const maxRounds = stageConfig.maxRounds

    return roundsInStage < maxRounds
  }

  /**
   * 获取活跃的需求
   */
  private async getActiveRequirement(requirementId?: string): Promise<RequirementRecord | null> {
    // TODO: 从 reqboard 服务获取需求
    // 这里需要访问 reqboard 的数据存储
    // 暂时返回 null，待集成时实现
    return null
  }

  /**
   * 暂停 Dive 模式
   */
  private async pauseDive(requirementId: string, reason: string): Promise<void> {
    // TODO: 更新需求的 dive.phase 为 'paused'
    this.ctx.logger('dive-manager').info(`Pausing dive for requirement ${requirementId}: ${reason}`)
  }

  /**
   * 增加回合数
   */
  private async incrementRound(requirementId: string): Promise<void> {
    // TODO: 增加 dive.roundsInStage
    this.ctx.logger('dive-manager').debug(`Incrementing round for requirement ${requirementId}`)
  }
}
