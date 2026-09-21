/**
 * LearningTrackTool - 经验追踪工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { learningTrackPrompt, LearningTrackParams, LearningTrackResult } from './prompt';

/**
 * 经验追踪工具类
 */
export class LearningTrackTool extends BaseTool<LearningTrackParams, LearningTrackResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'learning_track',
    category: 'learning',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = learningTrackPrompt;

  constructor(
    private experienceBuffer: any[],
    private persistExperience: (entry: any) => Promise<void>,
    private extractTagsFromContext: (context: any) => string[]
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: LearningTrackParams): ValidationResult {
    // 校验 action_type
    const validActionTypes = ['trade', 'analysis', 'strategy_execution', 'system_operation', 'custom'];
    if (!args.action_type || !validActionTypes.includes(args.action_type)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'action_type',
          issue: `action_type 必须是: ${validActionTypes.join(', ')}`,
          expected: validActionTypes.join(' | '),
        },
      };
    }

    // 校验 context
    if (!args.context || typeof args.context !== 'object') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'context',
          issue: 'context 必须是对象',
          expected: 'object',
        },
      };
    }

    // 校验 outcome
    if (!args.outcome || typeof args.outcome !== 'object') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'outcome',
          issue: 'outcome 必须是对象',
          expected: 'object',
        },
      };
    }

    if (typeof args.outcome.success !== 'boolean') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'outcome.success',
          issue: 'outcome.success 必须是布尔值',
          expected: 'boolean',
        },
      };
    }

    // 校验 reward
    if (typeof args.reward !== 'number') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'reward',
          issue: 'reward 必须是数字',
          expected: 'number',
        },
      };
    }

    if (args.reward < -1 || args.reward > 1) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'reward',
          issue: 'reward 必须在 -1.0 到 1.0 之间',
          expected: 'number between -1.0 and 1.0',
        },
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: LearningTrackParams, _context: ToolContext): Promise<LearningTrackResult> {
    const entry = {
      id: `exp_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      timestamp: new Date().toISOString(),
      agent_version: process.env.AGENT_VERSION || 'dev',
      action: { type: args.action_type, context: args.context },
      context: args.context,
      outcome: args.outcome,
      reward: args.reward,
      reasoning_trace: args.reasoning_trace,
      tags: this.extractTagsFromContext(args.context),
    };

    this.experienceBuffer.push(entry);
    await this.persistExperience(entry);

    return {
      success: true,
      experience_id: entry.id,
      message: `经验已记录：${args.action_type}，奖励 ${args.reward}`,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: LearningTrackResult): ToolResponse<LearningTrackResult> {
    return { success: true, data: result };
  }
}
