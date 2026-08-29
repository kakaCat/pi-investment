/**
 * RotationSimulateTool - 轮动模拟工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface RotationSimulateParams {
  proposals: Array<{
    action: 'buy' | 'sell';
    symbol: string;
    weight?: number;
  }>;
  account_name?: string;
  check_constraints?: boolean;
}

export interface RotationSimulateResult {
  simulation: {
    feasible: boolean;
    expected_positions: Array<{
      symbol: string;
      name: string;
      shares: number;
      value: number;
      weight: number;
    }>;
    cash_required: number;
    cash_available: number;
    warnings: string[];
  };
  constraints_check?: {
    passed: boolean;
    violations: string[];
  };
}

export const rotationSimulatePrompt: ToolPrompt<RotationSimulateParams, RotationSimulateResult> = {
  description: '模拟执行轮动方案，检查可行性和约束条件',
  useCases: [
    '验证调仓方案可行性',
    '检查资金是否充足',
    '评估调仓后持仓结构',
    '发现潜在风险',
  ],
  parameters: {
    proposals: {
      type: 'array',
      required: true,
      description: '轮动方案列表',
      example: [{ action: 'buy', symbol: '000001', weight: 0.1 }],
    },
    account_name: {
      type: 'string',
      description: '账户名称',
      example: 'default',
    },
    check_constraints: {
      type: 'boolean',
      description: '是否检查约束条件',
      example: true,
    },
  },
  examples: [],

  notes: [],

  relatedTools: [],


  output: {
    schema: {
      type: 'object',
      properties: {
        simulation: { type: 'object', description: '模拟结果' },
        constraints_check: { type: 'object', description: '约束检查' },
      },
    },
    render: (_args, data) => [
      { type: 'text', text: `🎮 轮动模拟完成` },
      { type: 'text', text: `` },
      { type: 'text', text: `${data.simulation.feasible ? '✅' : '❌'} 方案可行性: ${data.simulation.feasible ? '可行' : '不可行'}` },
      { type: 'text', text: `💰 所需资金: ${data.simulation.cash_required.toFixed(2)}` },
      { type: 'text', text: `💵 可用资金: ${data.simulation.cash_available.toFixed(2)}` },
      { type: 'text', text: `` },
      ...(data.simulation.warnings.length > 0 ? [
        { type: 'text' as const, text: `⚠️ 警告:` },
        ...data.simulation.warnings.map(w => ({ type: 'text' as const, text: `  • ${w}` })),
        { type: 'text' as const, text: `` }
      ] : []),
      { type: 'text', text: `📊 预期持仓 (${data.simulation.expected_positions.length} 只):` },
      ...data.simulation.expected_positions.slice(0, 5).map(p => ({
        type: 'text' as const,
        text: `  • ${p.symbol} ${p.name}: ${p.shares}股 (${(p.weight * 100).toFixed(1)}%)`
      })),
    ],
  },
};
