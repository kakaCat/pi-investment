/**
 * Signal Push Tool - 推送交易信号到Web前端
 *
 * 通过WebSocket实时推送买卖信号，供前端展示和通知
 */

import type { ToolDefinition } from '@mariozechner/pi-coding-agent';
import { Type } from '@sinclair/typebox';

export const signalPushTool: ToolDefinition = {
  name: 'signal_push',
  label: '推送交易信号',
  description: '推送交易信号到Web前端（通过WebSocket）',
  parameters: Type.Object({
    symbol: Type.String({ description: '股票代码（如 600519.SH）' }),
    name: Type.String({ description: '股票名称（如 贵州茅台）' }),
    action: Type.Union([
      Type.Literal('buy'),
      Type.Literal('sell'),
      Type.Literal('hold')
    ], { description: '信号动作：buy（买入）、sell（卖出）、hold（持有）' }),
    price: Type.Number({ description: '当前价格' }),
    strategy: Type.String({ description: '策略名称' }),
    reasons: Type.Optional(Type.Array(Type.String(), { description: '信号原因列表' })),
    risk_level: Type.Optional(Type.Union([
      Type.Literal('low'),
      Type.Literal('medium'),
      Type.Literal('high')
    ], { description: '风险等级' })),
    confidence: Type.Optional(Type.Number({ description: '信号置信度（0-1）' }))
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      // 调用后端推送API
      const apiUrl = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const response = await fetch(`${apiUrl}/api/signals/push`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(params),
      });

      const result = await response.json() as { success: boolean; clients_notified?: number; error?: string };

      if (result.success) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: true,
              message: `信号已推送到 ${result.clients_notified} 个客户端`,
              clients_notified: result.clients_notified
            }, null, 2)
          }],
          details: result,
        };
      } else {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: false,
              error: result.error || '推送失败'
            }, null, 2)
          }],
          details: result,
        };
      }
    } catch (error: any) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message || '推送异常'
          }, null, 2)
        }],
        details: { error: error.message },
      };
    }
  },
};
