/**
 * M4CircuitBreakerTool - 提示词定义
 *
 * 工具描述：M4-2 熔断机制检查
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface CircuitBreakerCheckParams {
  account_name?: string;
}

export interface CircuitBreakerStatus {
  active: boolean;
  triggered_at?: string;
  triggered_drawdown?: number;
  actions_taken?: string[];
  unblock_condition?: string;
  unblocked_at?: string;
  checked_at: string;
}

export interface CircuitBreakerCheckResult {
  checked_at: string;
  max_drawdown: number;
  triggered: boolean;
  unblocked: boolean;
  actions: string[];
  circuit_breaker_status: CircuitBreakerStatus | null;
  error?: string;
}

export const circuitBreakerPrompt: ToolPrompt<CircuitBreakerCheckParams, CircuitBreakerCheckResult> = {
  description:
    'M4-2 熔断机制：检查组合60日回撤，触发条件 <-8%（减仓一半+禁止开仓），解除条件 >=-8%',

  useCases: [
    '每日盘后检查回撤是否触发熔断',
    '交易前确认熔断状态',
    '监控熔断解除条件',
  ],

  examples: [
    {
      title: '检查熔断状态',
      params: {
        account_name: 'agent_virtual',
      },
      expectedResult: '60日回撤: -5.2%, 无熔断',
    },
  ],

  notes: [
    '⚠️  触发阈值：60日最大回撤 < -8%',
    '⚠️  触发动作：减仓一半 + 禁止开仓',
    '⚠️  解除条件：60日回撤 >= -8%',
    '💡 API 失败时降级为 0（不触发熔断）',
  ],

  relatedTools: ['position_list', 'account_info', 'quantsys_v2_status'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
      example: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        checked_at: { type: 'string', description: '检查时间' },
        max_drawdown: { type: 'number', description: '60日最大回撤（%）' },
        triggered: { type: 'boolean', description: '本次是否触发熔断' },
        unblocked: { type: 'boolean', description: '本次是否解除熔断' },
        actions: { type: 'array', items: { type: 'string' }, description: '执行的动作列表' },
        circuit_breaker_status: {
          type: 'object', additionalProperties: true,
          description: '当前熔断状态（null 表示无熔断）'
        },
        error: { type: 'string', description: 'API 错误（降级模式）' },
      },
      additionalProperties: true,
    },
    render: (args: CircuitBreakerCheckParams, value: CircuitBreakerCheckResult) => {
      let output = `## M4-2 熔断检查结果\n\n`;
      output += `**检查时间**: ${value.checked_at}\n`;
      output += `**60日最大回撤**: ${value.max_drawdown.toFixed(2)}%\n`;
      output += `**熔断状态**: ${value.circuit_breaker_status?.active ? '🔴 激活中' : '🟢 未激活'}\n\n`;

      if (value.error) {
        output += `⚠️ **检查失败（API 不可用）**\n`;
        output += `错误信息: ${value.error}\n`;
        output += `降级处理: 跳过本次熔断判定\n`;
      } else if (value.triggered) {
        output += `🚨 **熔断触发**\n\n`;
        output += `**执行动作**:\n`;
        value.actions.forEach(action => {
          output += `- ${action}\n`;
        });
      } else if (value.unblocked) {
        output += `✅ **熔断解除**\n\n`;
        output += `回撤已修复到 ${value.max_drawdown.toFixed(2)}%，恢复允许开仓\n`;
      } else {
        output += `**状态**: 无变化\n`;
        output += `${value.actions[0]}\n`;
      }

      if (value.circuit_breaker_status) {
        output += `\n**熔断配置**:\n`;
        output += `- 触发阈值: 60日回撤 < -8%\n`;
        output += `- 触发动作: 减仓一半 + 禁止开仓\n`;
        output += `- 解除条件: 60日回撤 >= -8%\n`;
      }

      return [{ type: 'text', text: output }];
    },
  },
};
