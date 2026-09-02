/**
 * DecisionAuditTool - 决策审计工具（记录 + 评估）
 *
 * 对标 agent-ts decision_record：重要决策落审计库，形成可复盘的决策轨迹。
 * 闭环：record → （N 天后）evaluate → evaluation_status 回填 + 知识提炼
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DecisionAuditParams {
  action: 'record' | 'evaluate';
  decision_type?: string;
  reasoning?: string;
  context?: Record<string, any>;
  parameters?: Record<string, any>;
  related_entity_type?: string;
  related_entity_id?: string;
  decision_id?: string;
  days?: number;
}

export const decisionAuditPrompt: ToolPrompt<DecisionAuditParams> = {
  name: 'decision_audit',
  description: '决策审计闭环（写操作）：record 记录重要决策（建池/调仓/选股/风控/挂单等）到审计库；evaluate 触发事后评估（按决策类型回填 outcome + 更新评估状态 + 提炼知识）。与 memory_write 的分工：memory 存"结论供检索"，decision_audit 存"决策供复盘评估"——重要交易/调仓决策两者都应写。',

  parameters: {
    action: {
      type: 'string',
      enum: ['record', 'evaluate'],
      description: 'record：记录决策；evaluate：触发评估（单笔传 decision_id，批量传 days）',
      required: true,
    },
    decision_type: {
      type: 'string',
      description: '决策类型（record 必填）：如 trade_buy/trade_sell/pool_create/pool_update/risk_control/pending_order/watch_rule/skip_trade（主动不交易也值得记录）',
    },
    reasoning: {
      type: 'string',
      description: '决策推理（record 必填）：为什么做这个决策，引用规则ID+数据依据',
    },
    context: {
      type: 'object', additionalProperties: true,
      description: '决策上下文（可选）：市场环境、regime、触发原因等',
    },
    parameters: {
      type: 'object', additionalProperties: true,
      description: '决策参数（可选）：具体操作内容，如 {symbol, quantity, price}',
    },
    related_entity_type: {
      type: 'string',
      description: '关联实体类型（可选）：pool/stock/account/strategy',
    },
    related_entity_id: {
      type: 'string',
      description: '关联实体ID（可选）：如股票代码、池子ID',
    },
    decision_id: {
      type: 'string',
      description: '决策ID（evaluate 单笔时必填）',
    },
    days: {
      type: 'integer',
      description: '批量评估时的天数阈值（默认 7，评估创建超过 N 天的 pending 决策）',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        success: { type: 'boolean', description: '是否成功' },
        action: { type: 'string', description: '执行的操作' },
        decision_id: { type: 'string', description: '决策ID（record 返回）' },
        data: { type: 'object', additionalProperties: true, description: '后端返回详情' },
      },
      additionalProperties: true,
    },
    render: (_args: DecisionAuditParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      scenario: '记录一笔买入决策',
      params: {
        action: 'record',
        decision_type: 'trade_buy',
        reasoning: 'R-009 A级信号：主线+技术+资金三维共振，swing_points 显示处于历史验证买区',
        context: { regime: 'risk_on', window: 'w-ac60b8e8' },
        parameters: { symbol: '601857', quantity: 1000, price: 10.5 },
        related_entity_type: 'stock',
        related_entity_id: '601857',
      },
      expectedBehavior: '返回 decision_id，决策进入审计库（evaluation_status=pending）',
    },
    {
      scenario: '批量评估 7 天前的决策',
      params: { action: 'evaluate', days: 7 },
      expectedBehavior: '返回 evaluated_count/success_count/failed_count/knowledge_extracted',
    },
  ],

  useCases: [
    { title: '交易决策留痕', description: '每笔重要买卖记录推理与上下文，供盘后/周末复盘', example: 'portfolio_trade 后立即 decision_audit record' },
    { title: '主动不交易记录', description: 'skip_trade 记录"为什么没买"，零交易日同样产生可复盘资产', example: 'decision_type=skip_trade + reasoning' },
    { title: '盘后评估闭环', description: '每日/每周批量评估到期决策，回填成败并自动提炼知识', example: 'action=evaluate, days=7' },
  ],

  notes: [
    '2026-09-01 上线：同步修复了后端 /api/decisions/* 的 decision_service getter 未调用缺陷（原必 500）',
    '评估时机：决策做出后 N 天（默认 7 天）再评估，给市场留出验证时间',
    'evaluation_status：pending（待评估）→ 评估后回填 success/failed + outcome',
    '与 signal_track 的分工：signal_track 跟踪买入信号的价格表现，decision_audit 跟踪决策本身的推理质量',
  ],

  relatedTools: [
    { name: 'decision_history', relationship: '查询已记录的决策', useCase: 'record 后用 decision_history 回看/找待评估决策' },
    { name: 'signal_track', relationship: '信号级追踪', useCase: '买入信号的价格表现跟踪' },
    { name: 'memory_write', relationship: '结论沉淀', useCase: '评估后的教训写 memory' },
  ],
};
