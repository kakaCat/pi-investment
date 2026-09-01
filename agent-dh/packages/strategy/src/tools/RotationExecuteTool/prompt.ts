/**
 * RotationExecuteTool - 轮动执行工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface RotationExecuteParams {
  proposals: Array<{
    // 2026-09-01：与后端 strategy_rotation_engine 对齐（原 buy/sell 会被 422/忽略）
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    symbol?: string;
    weight?: number;
  }>;
  account_name?: string;
  dry_run?: boolean;
}

export interface RotationExecuteResult {
  execution: {
    success: boolean;
    orders_placed: number;
    orders_failed: number;
    details: Array<{
      symbol: string;
      action: string;
      status: 'success' | 'failed' | 'skipped';
      order_id?: string;
      message?: string;
    }>;
  };
  post_execution_positions?: Array<{
    symbol: string;
    shares: number;
    value: number;
  }>;
}

export const rotationExecutePrompt: ToolPrompt<RotationExecuteParams, RotationExecuteResult> = {
  description: '执行轮动方案，实际下单买入卖出',
  useCases: [
    '执行定期调仓',
    '板块轮动切换',
    '止盈止损调整',
    '策略信号执行',
  ],
  parameters: {
    proposals: {
      type: 'array',
      required: true,
      description: '轮动方案列表（由 rotation_proposal 生成）。action 取值：activate（启用策略）/ deactivate（停用策略）/ adjust_weight（调整权重）',
      example: [{ action: 'deactivate', strategy_id: 3, strategy_name: '均线突破策略' }],
    },
    account_name: {
      type: 'string',
      description: '账户名称',
      example: 'default',
    },
    dry_run: {
      type: 'boolean',
      description: '是否模拟执行（不实际下单，2026-09-01 起后端支持）',
      example: false,
    },
  },
  examples: [
    'rotation_execute({ proposals: [{action: "deactivate", strategy_id: 3, strategy_name: "均线突破策略"}], dry_run: true }) // 模拟执行',
    'rotation_execute({ proposals: [{action: "adjust_weight", strategy_id: 1, new_weight: 0.5}], account_name: "default" }) // 实际执行权重调整',
  ],

  notes: [
    '⚠️ dry_run=false 时会实际下单交易，请谨慎操作',
    '💡 建议先用 rotation_simulate 预览方案，再用本工具执行',
    '执行前会自动检查账户余额、持仓、交易时间等限制',
  ],

  relatedTools: ['rotation_proposal', 'rotation_simulate'],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        execution: { type: 'object', additionalProperties: true, description: '执行结果' },
        post_execution_positions: { type: 'array', description: '执行后持仓' },
      },
    },
    render: (args, data) => [
      { type: 'text', text: `🚀 轮动执行${args.dry_run ? '（模拟）' : ''}完成` },
      { type: 'text', text: `` },
      { type: 'text', text: `${data.execution.success ? '✅' : '⚠️'} 整体状态: ${data.execution.success ? '成功' : '部分失败'}` },
      { type: 'text', text: `📊 下单成功: ${data.execution.orders_placed} 笔` },
      { type: 'text', text: `❌ 下单失败: ${data.execution.orders_failed} 笔` },
      { type: 'text', text: `` },
      ...data.execution.details.map(d => {
        const icon = d.status === 'success' ? '✅' : d.status === 'failed' ? '❌' : '⏭️';
        return { type: 'text' as const, text: `${icon} ${d.symbol} ${d.action} - ${d.message || d.status}` };
      }),
      { type: 'text', text: `` },
      ...(data.post_execution_positions ? [
        { type: 'text' as const, text: `📊 执行后持仓 (${data.post_execution_positions.length} 只):` },
        ...data.post_execution_positions.slice(0, 5).map(p => ({
          type: 'text' as const,
          text: `  • ${p.symbol}: ${p.shares}股 (市值: ${p.value.toFixed(2)})`
        })),
      ] : []),
    ],
  },
};
