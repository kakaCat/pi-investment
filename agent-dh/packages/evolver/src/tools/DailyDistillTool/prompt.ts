/**
 * DailyDistillTool - 每日蒸馏模板
 */

import type { ToolPrompt, ParameterDefinition } from '@pi-investment/core-tool';

export interface DailyDistillParams {
  days?: number;
  auto_apply?: boolean;
}

export interface DailyDistillResult {
  distill_summary: {
    genome_version: string;
    period: {
      from: string;
      to: string;
    };
    stats: {
      total_experiences: number;
      avg_reward: number;
      success_rate: number;
    };
  };
  evolver_result: {
    proposals: Array<{
      section: string;
      action: string;
      method: string;
      content: string;
      reason: string;
    }>;
    summary: string;
    applied_count: number;
  };
  summary: string;
}

export const dailyDistillPrompt: ToolPrompt<DailyDistillParams> = {
  name: 'daily_distill',
  description: 'P1-3 每日蒸馏编排：自动执行 experience_distill → prompt_evolver → 通知。用于：盘后自动化、手动触发完整蒸馏流程。推荐每日 16:00 执行。',

  parameters: {
    days: {
      type: 'number',
      description: '分析最近 N 天经验（默认 7）',
      required: false,
    } as ParameterDefinition,

    auto_apply: {
      type: 'boolean',
      description: 'true：自动应用改进（调用 genome_update）；false（默认）：只生成预览',
      required: false,
    } as ParameterDefinition,
  },

  examples: [
    {
      title: '预览模式（每日定时任务）',
      params: {
        days: 7,
        auto_apply: false,
      },
      expectedResult: '生成蒸馏报告和改进提案预览，不实际应用',
    },
    {
      title: '自动应用模式',
      params: {
        days: 7,
        auto_apply: true,
      },
      expectedResult: '生成提案并自动应用为 candidate 版本',
    },
  ],
};
