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
    // RFC 008：非 dryRun 成功应用为 candidate 后回填登记信息（供调用方追踪观察期）
    candidate_id?: string;
    observe_until?: string;
    stage?: 'candidate' | 'active';
  }>;
}

export const promptEvolverPrompt: ToolPrompt<PromptEvolverParams> = {
  description: 'P1-2 提示词进化：接收 distill 建议，生成段更新提案，调用 genome_update 应用。用于：每日蒸馏、手动应用改进、A/B 测试新规则。',
  useCases: [
    '每日蒸馏后生成提示词改进提案',
    '手动提交单条改进建议（A/B 测试新规则）',
    '批量应用多条蒸馏建议为 candidate 观察版',
  ],
  notes: [
    'dry_run=true（默认）只生成提案预览，不实际修改基因组',
    'dry_run=false 会以 candidate 观察版应用，须经 validation_gate 裁决转正',
    'rules 段规则 ID 只允许新增，不允许删除或修改已有 ID',
    '改写失败自动回退为追加模式，保证可用性',
  ],
  relatedTools: ['genome_update', 'learning_distill', 'validation_gate', 'candidate_status'],
  parameters: {
    suggestions: {
      type: 'array',
      description: 'experience_distill 输出的建议数组，每个建议包含 type/section/content/reason',
      required: true,
      items: { type: 'object', additionalProperties: true },
    } as ParameterDefinition,

    dry_run: {
      type: 'boolean',
      description: 'true（默认）：只生成预览，不执行；false：以 candidate 观察版应用（须经 validation_gate 裁决转正）',
    } as ParameterDefinition,

    observe_days: {
      type: 'number',
      description: 'candidate 观察期（天），默认 5',
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
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        proposals: {
          type: 'array',
          items: { type: 'object', additionalProperties: true },
        },
        summary: { type: 'string' },
        applied_count: { type: 'number' },
        results: {
          type: 'array',
          items: { type: 'object', additionalProperties: true },
        },
      },
    },
    render: (args: PromptEvolverParams, data: any) => [{
      type: 'text',
      text: [
        `## 提示词进化结果`,
        `**模式**: ${args.dry_run === false ? '应用' : '预览'}`,
        `**概要**: ${data?.summary ?? ''}`,
        ``,
        ...(data?.proposals ?? []).map((p: any, i: number) =>
          `### 提案 ${i + 1}: ${p.section} (${p.method})\n${p.reason ?? ''}\n\`\`\`\n${p.content ?? ''}\n\`\`\``
        ),
      ].join('\n'),
    }],
  },
};
