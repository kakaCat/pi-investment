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
  description: 'P1-3 每日蒸馏编排：自动执行 experience_distill → prompt_evolver → 通知。用于：盘后自动化、手动触发完整蒸馏流程。推荐每日 16:00 执行。',
  useCases: [
    '每日盘后自动运行完整蒸馏流程（定时任务）',
    '手动触发一次蒸馏 + 进化提案生成',
    'auto_apply 模式自动应用改进为 candidate',
  ],
  notes: [
    '流程：experience_distill（分析经验）→ prompt_evolver（生成提案）→ 通知',
    'auto_apply=false（默认）只生成预览，不实际修改基因组',
    'auto_apply=true 会以 candidate 观察版应用改进，须经 validation_gate 裁决',
    '推荐每日 16:00 盘后执行，此时当日经验已沉淀',
  ],
  relatedTools: ['learning_distill', 'prompt_evolver', 'validation_gate', 'feishu_notify'],
  parameters: {
    days: {
      type: 'number',
      description: '分析最近 N 天经验（默认 7）',
    } as ParameterDefinition,

    auto_apply: {
      type: 'boolean',
      description: 'true：自动应用改进（调用 genome_update）；false（默认）：只生成预览',
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
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        distill_summary: { type: 'object', additionalProperties: true },
        evolver_result: { type: 'object', additionalProperties: true },
        summary: { type: 'string' },
      },
    },
    render: (_args: DailyDistillParams, data: any) => {
      const ev = data?.evolver_result;
      return [{
        type: 'text',
        text: [
          `## 每日蒸馏结果`,
          `**概要**: ${data?.summary ?? ''}`,
          `**蒸馏周期**: ${data?.distill_summary?.period?.from ?? '?'} → ${data?.distill_summary?.period?.to ?? '?'}`,
          `**经验统计**: ${data?.distill_summary?.stats?.total_experiences ?? 0} 条，平均奖励 ${data?.distill_summary?.stats?.avg_reward ?? 0}`,
          `**进化提案**: ${ev?.applied_count ?? 0} 条应用`,
          ``,
          ...(ev?.proposals ?? []).map((p: any, i: number) =>
            `### 提案 ${i + 1}: ${p.section} (${p.method})\n${p.reason ?? ''}`
          ),
        ].join('\n'),
      }];
    },
  },
};
