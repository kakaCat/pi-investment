/**
 * SelfStatusTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface SelfStatusParams {
  detailed?: boolean;
}

export interface SelfStatusResult {
  success: boolean;
  status: string;
  uptime: number;
  health: Record<string, any>;
}

export const selfStatusPrompt: ToolPrompt<SelfStatusParams, SelfStatusResult> = {
  description: '查询 Agent 运行状态。返回运行时长、健康度等信息。',
  useCases: ['检查运行状态', '监控健康度', '故障诊断'],
  examples: [
    {
      title: '查询详细状态',
      params: { detailed: true },
      expectedResult: '返回详细的运行状态信息',
    },
  ],
  parameters: {
    detailed: { type: 'boolean', required: false, description: '是否返回详细信息' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        status: { type: 'string' },
        uptime: { type: 'number' },
        health: { type: 'object', additionalProperties: true },
      },
    },
    render: (args, data) => {
      let output = '## 📊 Agent 状态\n\n';
      output += `- **状态**: ${data.status}\n`;
      output += `- **运行时长**: ${data.uptime}s\n`;
      if (args.detailed && data.health) {
        output += `- **健康度**: ${JSON.stringify(data.health, null, 2)}\n`;
      }
      return [{ type: 'text', text: output }];
    },
  },
};
