/**
 * RotationSimulateTool - 轮动模拟工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface RotationSimulateParams {
  proposals: Array<{
    // 2026-09-01：与后端 strategy_rotation_engine 对齐（原 buy/sell 与后端
    // activate/deactivate/adjust_weight 语义不匹配，会被静默忽略）
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    symbol?: string;
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
      description: '轮动方案列表（通常由 rotation_proposal 工具生成，也可手动构造）。action 取值与后端一致：activate（启用策略）/ deactivate（停用策略）/ adjust_weight（调整权重）',
      example: [{ action: 'deactivate', strategy_id: 3, strategy_name: '均线突破策略' }],
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
      title: '模拟停用表现差的策略',
      params: {
        proposals: [{ action: 'deactivate', strategy_id: 3, strategy_name: '均线突破策略' }],
        account_name: 'default',
        check_constraints: true,
      },
      expectedResult: '返回清仓模拟、资金释放、风险变化',
    },
    {
      title: '模拟完整轮动方案',
      params: {
        proposals: [
          { action: 'deactivate', strategy_id: 3, strategy_name: '均线突破策略' },
          { action: 'adjust_weight', strategy_id: 1, strategy_name: 'MACD金叉策略', old_weight: 1.0, new_weight: 0.5 },
        ],
        check_constraints: true,
      },
      expectedResult: '检查停用策略清仓与权重调整的可行性',
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
    render: (_args, data) => {
      const sim = data.simulation ?? {};
      const warnings = Array.isArray(sim.warnings) ? sim.warnings : [];
      const positions = Array.isArray(sim.expected_positions) ? sim.expected_positions : [];
      const feasible = sim.feasible === true;
      const cashRequired = Number(sim.cash_required ?? 0);
      const cashAvailable = Number(sim.cash_available ?? 0);
      return [
        { type: 'text', text: `🎮 轮动模拟完成` },
        { type: 'text', text: `` },
        { type: 'text', text: `${feasible ? '✅' : '❌'} 方案可行性: ${feasible ? '可行' : '不可行'}` },
        { type: 'text', text: `💰 所需资金: ${cashRequired.toFixed(2)}` },
        { type: 'text', text: `💵 可用资金: ${cashAvailable.toFixed(2)}` },
        { type: 'text', text: `` },
        ...(warnings.length > 0 ? [
          { type: 'text' as const, text: `⚠️ 警告:` },
          ...warnings.map((w: string) => ({ type: 'text' as const, text: `  • ${w}` })),
          { type: 'text' as const, text: `` }
        ] : []),
        { type: 'text', text: `📊 预期持仓 (${positions.length} 只):` },
        ...positions.slice(0, 5).map((p: any) => ({
          type: 'text' as const,
          text: `  • ${p.symbol} ${p.name}: ${p.shares}股 (${(Number(p.weight ?? 0) * 100).toFixed(1)}%)`
        })),
      ];
    },
  },
};
