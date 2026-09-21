/**
 * ReflectTool - 目标对齐反思工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ReflectParams {
  original_goal: string;
  work_summary: string;
  gaps?: string[];
  evidence?: string[];
}

export const reflectPrompt: ToolPrompt<ReflectParams> = {
  name: 'reflect',
  description: '目标对齐反思（交付前质检）：对照用户原始目标与已完成工作，结构化输出对齐判定（aligned/partial/gaps_found）、检查清单、差距清单与下一步。适用于：完成一个有意义的工作单元后、向用户交付前——防止"做完了但没答到点上"。⚠️ 它是检查点不是终点：拿到 verdict 后必须继续——交付结果/补齐差距/说明情况，禁止拿到反思就沉默。',

  parameters: {
    original_goal: {
      type: 'string',
      description: '用户原始目标（尽量引用原话，不要改写美化）',
      required: true,
    },
    work_summary: {
      type: 'string',
      description: '已完成工作的简要总结（做了什么、关键产出）',
      required: true,
    },
    gaps: {
      type: 'array',
      description: '自查发现的差距/遗漏（可选，诚实列出）',
    },
    evidence: {
      type: 'array',
      description: '支撑"已完成"的证据（可选）：工具返回、数据、文件路径',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        verdict: { type: 'string', description: 'aligned / partial / gaps_found' },
        checklist: { type: 'array', description: '对齐检查清单' },
        next_steps: { type: 'array', description: '建议下一步' },
      },
      additionalProperties: true,
    },
    render: (_args: ReflectParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      scenario: '交付深度分析前反思',
      params: {
        original_goal: '中石油买卖点',
        work_summary: '完成 swing_points 波段分析+价位地图+买区卖点建议',
        evidence: ['swing_points 返回 22 笔历史波段', 'pe_percentile 90.91% 高估'],
      },
      expectedBehavior: '返回 verdict + checklist（是否回答买卖点/是否有价位/是否有风险提示）',
    },
  ],

  useCases: [
    { title: '交付前质检', description: '复杂任务完成后、回复用户前对齐检查', example: 'reflect({ original_goal, work_summary })' },
    { title: '防目标漂移', description: '长链路任务中定期对照原始目标', example: '多步骤任务中途 reflect 一次' },
  ],

  notes: [
    '2026-09-02 上线（对标 agent-ts reflect 工具的检查清单语义；判定由调用方 LLM 完成，本工具强制结构化+留痕）',
    '每个有意义的工作单元最多调一次，不要每个小动作都调',
    '拿到 verdict 后必须继续行动：交付/补差距/解释——reflect 不是终点',
  ],

  relatedTools: [
    { name: 'todo_write', relationship: '执行进度跟踪', useCase: 'reflect 看目标对齐，todo 看步骤完成' },
    { name: 'memory_write', relationship: '教训沉淀', useCase: 'reflect 发现的系统性差距写 memory' },
  ],
};
