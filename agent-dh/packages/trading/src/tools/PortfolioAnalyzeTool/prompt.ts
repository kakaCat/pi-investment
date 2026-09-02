/**
 * PortfolioAnalyzeTool - 持仓健康一键分析
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface PortfolioAnalyzeParams {
  account_name?: string;
}

export const portfolioAnalyzePrompt: ToolPrompt<PortfolioAnalyzeParams> = {
  description: '持仓健康一键分析（只读）：逐只检查盈亏状态、止盈止损线距离、T+1 可卖性，输出按优先级排序的操作建议（stop_loss > take_profit > review > hold）+ 组合健康度。适用于：早盘持仓评估、盘后复盘、"看看我的持仓有没有问题"。止损线口径：主板蓝筹 -8%、创业板/科创（30/68 开头）-10%；止盈参考 +10%。',

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        account: { type: 'string', description: '账户名' },
        urgent: { type: 'array', description: '需立即处理的持仓（止损/止盈触发）' },
        positions: { type: 'array', description: '逐只分析（盈亏/建议/优先级）' },
        health: { type: 'object', additionalProperties: true, description: '组合健康度' },
      },
      additionalProperties: true,
    },
    render: (_args: PortfolioAnalyzeParams, value: any) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },

  examples: [
    { scenario: '早盘持仓体检', params: {}, expectedBehavior: '返回逐只建议（止损/止盈/持有/等T+1）按优先级排序' },
  ],

  useCases: [
    { title: '早盘评估', description: '开盘前逐只检查是否触发止损/止盈', example: 'portfolio_analyze({})' },
    { title: '盘后复盘', description: '组合健康度 + 问题持仓清单', example: '配合 trade_verify 使用' },
  ],

  notes: [
    '2026-09-02 上线（对标 agent-ts portfolio_analyze + portfolio-review skill 健康指标）',
    '止损线为规则参考值（蓝筹-8%/创业科创-10%），实际止损以 watch 规则与交易宪法为准',
    'price_stale=true 时价格不可信，输出会标注且不给止损/止盈结论',
    '持仓复盘五问（逻辑是否成立等）需要结合基本面工具，本工具只做风险维度快检',
  ],

  relatedTools: [
    { name: 'position_list', relationship: '原始持仓数据', useCase: '看明细字段' },
    { name: 'watch_manage', relationship: '止损规则补位', useCase: 'analyze 发现裸仓后立即挂 pnl_pct 规则' },
    { name: 'risk_controller', relationship: '精确止损价计算', useCase: '需要 ATR 止损价时' },
  ],
};
