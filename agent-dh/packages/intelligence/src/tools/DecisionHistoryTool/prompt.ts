/**
 * DecisionHistoryTool - 决策历史查询工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DecisionHistoryParams {
  action?: 'history' | 'pending' | 'report';
  entity_type?: string;
  entity_id?: string;
  decision_type?: string;
  limit?: number;
  days?: number;
}

export const decisionHistoryPrompt: ToolPrompt<DecisionHistoryParams> = {
  name: 'decision_history',
  description: '查询决策审计历史（只读）：history=决策时间线（可按实体/类型过滤），pending=待评估决策（创建超 N 天未评估），report=按实体聚合的决策报告。适用于：盘前/盘后复盘"当时为什么这么决策"、找逾期未评估的决策、评估决策质量。',

  parameters: {
    action: {
      type: 'string',
      enum: ['history', 'pending', 'report'],
      description: '查询类型，默认 history',
      default: 'history',
    },
    entity_type: {
      type: 'string',
      description: '关联实体类型过滤（history/report）：pool/stock/account/strategy',
    },
    entity_id: {
      type: 'string',
      description: '关联实体ID过滤（history/report 必填）：如股票代码、池子ID',
    },
    decision_type: {
      type: 'string',
      description: '决策类型过滤（history）：trade_buy/trade_sell/risk_control 等',
    },
    limit: {
      type: 'integer',
      description: '返回条数上限（history，默认 50）',
    },
    days: {
      type: 'integer',
      description: 'pending 模式的天数阈值（默认 7）',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        action: { type: 'string', description: '查询类型' },
        items: { type: 'array', description: '决策列表（history/pending）' },
        report: { type: 'object', additionalProperties: true, description: '决策报告（report）' },
      },
      additionalProperties: true,
    },
    render: (_args: DecisionHistoryParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      scenario: '查看某股票的所有决策',
      params: { action: 'history', entity_type: 'stock', entity_id: '601857' },
      expectedBehavior: '返回该股票的决策时间线（含推理与评估状态）',
    },
    {
      scenario: '查逾期未评估决策',
      params: { action: 'pending', days: 7 },
      expectedBehavior: '返回创建超 7 天仍 pending 的决策列表',
    },
  ],

  useCases: [
    { title: '复盘决策链', description: '回看当时推理 vs 事后结果，识别决策模式', example: 'action=history + entity 过滤' },
    { title: '评估逾期巡检', description: 'pending 列表为空=评估闭环健康；有积压则调 decision_audit evaluate', example: 'action=pending' },
  ],

  notes: [
    '2026-09-01 上线（对标 agent-ts decision_history）',
    'report 模式必须传 entity_type + entity_id',
    'evaluation_status 字段：pending=待评估，其他=已评估（含 outcome）',
  ],

  relatedTools: [
    { name: 'decision_audit', relationship: '记录/评估决策', useCase: 'pending 积压时调 decision_audit evaluate' },
  ],
};
