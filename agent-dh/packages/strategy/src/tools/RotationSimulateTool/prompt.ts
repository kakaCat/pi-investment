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
      description: '轮动方案列表（通常由 rotation_proposal 工具生成，也可手动构造）',
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
  examples: [
    {
      title: '模拟买入平安银行',
      params: {
        proposals: [{ action: 'buy', symbol: '000001', weight: 0.1 }],
        account_name: 'default',
        check_constraints: true,
      },
      expectedResult: '返回资金是否充足、预期持仓、约束检查结果',
    },
    {
      title: '模拟轮动方案',
      params: {
        proposals: [
          { action: 'sell', symbol: '600519' },
          { action: 'buy', symbol: '000858', weight: 0.15 },
        ],
        check_constraints: true,
      },
      expectedResult: '检查卖出茅台、买入五粮液的可行性',
    },
  ],

  notes: [
    '💡 proposals 参数通常由 rotation_proposal 工具自动生成',
    '💡 也可手动构造 proposals 数组进行假设性模拟',
    '⚠️ 确保 rotation_proposal 依赖的后端服务正常运行',
  ],

  relatedTools: ['rotation_proposal', 'rotation_execute'],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        simulation: { type: 'object', additionalProperties: true, description: '模拟结果' },
        constraints_check: { type: 'object', additionalProperties: true, description: '约束检查' },
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
