/**
 * PromptEvolverTool - Prompt 模板
 */

import type { ToolPrompt, ParameterDefinition } from '@pi-investment/core-tool';

export interface PromptEvolverParams {
  suggestions: Array<{
    type: string;
    section: string;
    content: string;
    reason: string;
  }>;
  dry_run?: boolean;
  observe_days?: number;
}

export interface PromptEvolverResult {
  proposals: Array<{
    section: string;
    action: string;
    method: string;
    content: string;
    reason: string;
    diff?: string;
  }>;
  summary: string;
  applied_count: number;
  results: Array<{
    success: boolean;
    section: string;
    message: string;
  }>;
}

export const promptEvolverPrompt: ToolPrompt<PromptEvolverParams> = {
  name: 'prompt_evolver',
  description: 'P1-2 提示词进化：接收 distill 建议，生成段更新提案，调用 genome_update 应用。用于：每日蒸馏、手动应用改进、A/B 测试新规则。',

  parameters: {
    suggestions: {
      type: 'array',
      description: 'experience_distill 输出的建议数组，每个建议包含 type/section/content/reason',
      required: true,
    } as ParameterDefinition,

    dry_run: {
      type: 'boolean',
      description: 'true（默认）：只生成预览，不执行；false：以 candidate 观察版应用（须经 validation_gate 裁决转正）',
      required: false,
    } as ParameterDefinition,

    observe_days: {
      type: 'number',
      description: 'candidate 观察期（天），默认 5',
      required: false,
    } as ParameterDefinition,
  },

  examples: [
    {
      title: '预览模式（默认）',
      params: {
        suggestions: [
          {
            type: 'add_rule',
            section: 'rules',
            content: '## R-042: 止损纪律\n\n持仓跌破成本 -8% 强制止损',
            reason: '经验蒸馏：5次深套案例平均损失 -15%，提前止损可避免',
          },
        ],
        dry_run: true,
      },
      expectedResult: '返回提案预览，不实际应用',
    },
    {
      title: '自动应用模式',
      params: {
        suggestions: [
          {
            type: 'strengthen',
            section: 'trading_discipline',
            content: '强化T+1纪律，今日买入明日才能卖出',
            reason: '近期3次违反T+1规则导致交易失败',
          },
        ],
        dry_run: false,
        observe_days: 7,
      },
      expectedResult: '应用为 candidate 版本，观察期 7 天',
    },
  ],
};
