/**
 * ValidationGateTool - 验证门模板
 */

import type { ToolPrompt, ParameterDefinition } from '@pi-investment/core-tool';

export interface ValidationGateParams {
  force?: boolean;
  min_samples?: number;
}

export interface ValidationGateResult {
  verdicts: Array<{
    id: string;
    section: string;
    genome_version: string;
    verdict: 'watching' | 'promoted' | 'rejected' | 'extended' | 'rejected_by_backtest';
    cand_avg?: number;
    base_avg?: number;
    cand_samples?: number;
    rolled_back_to?: number;
    observe_until?: string;
    note?: string;
    backtest_verdict?: any;
  }>;
  summary: string;
  total_candidates: number;
  promoted_count: number;
  rejected_count: number;
  watching_count: number;
}

export const validationGatePrompt: ToolPrompt<ValidationGateParams> = {
  name: 'validation_gate',
  description: 'RFC 008 验证门：裁决观察期到期的 candidate 版本（对比基准期打标经验），决定提升或回滚。用于：每日自动裁决、人工强制裁决。',

  parameters: {
    force: {
      type: 'boolean',
      description: 'true：跳过时间与样本数门槛，强制裁决所有 watching 状态的 candidate；false（默认）：仅裁决观察期到期的',
      required: false,
    } as ParameterDefinition,

    min_samples: {
      type: 'number',
      description: 'candidate 期最小样本数门槛，默认 3（少于此数会延期 2 天）',
      required: false,
    } as ParameterDefinition,
  },

  examples: [
    {
      title: '自动裁决（定时任务）',
      params: {
        force: false,
        min_samples: 3,
      },
      expectedResult: '仅裁决观察期到期且样本充足的 candidate',
    },
    {
      title: '人工强制裁决',
      params: {
        force: true,
        min_samples: 1,
      },
      expectedResult: '强制裁决所有 watching 状态的 candidate（用于紧急情况）',
    },
  ],
};
