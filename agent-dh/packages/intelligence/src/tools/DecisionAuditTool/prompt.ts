/**
 * DecisionAuditTool - 决策审计工具（记录 + 评估）
 *
 * 对标 agent-ts decision_record：重要决策落审计库，形成可复盘的决策轨迹。
 * 闭环：record → （N 天后）evaluate → evaluation_status 回填 + 知识提炼
 * 
 * 2026-09-11 更新：支持新决策类型（observation/skip），接入 DDD 评估引擎
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DecisionAuditParams {
  action: 'record' | 'evaluate';
  decision_type?: string;
  decision_subtype?: string;  // 新增：trade/observation/skip/pool_management
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
  description: '决策审计闭环（写操作）：record 记录重要决策（交易/观察/跳过/池子管理/风控/挂单等）到审计库；evaluate 触发事后评估（DDD 评估引擎：观察决策、跳过决策、交易决策分别对应专门策略，自动检测错过机会并提炼知识）。与 memory_write 的分工：memory 存"结论供检索"，decision_audit 存"决策供复盘评估"——重要决策两者都应写。',

  parameters: {
    action: {
      type: 'string',
      enum: ['record', 'evaluate'],
      description: 'record：记录决策；evaluate：触发评估（单笔传 decision_id，批量传 days）',
      required: true,
    },
    decision_type: {
      type: 'string',
      description: '决策类型（record 必填，旧格式兼容）：trade_buy/trade_sell/pool_create/pool_update/risk_control/pending_order/watch_rule/skip_trade 等',
    },
    decision_subtype: {
      type: 'string',
      description: '决策子类型（新格式，推荐使用）：trade（交易）/observation（观察"等回调"、"观察突破"）/skip（跳过"不追"、"估值高"）/pool_management（池子管理）',
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
      description: '决策参数（必填）：具体操作内容。trade={symbol,action,quantity,price}；observation={symbol,reason,targetPrice?,watchDays?}；skip={symbol,reason,checkDays?}；pool_management={poolId,action}',
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
      scenario: '记录一笔买入决策（新格式）',
      params: {
        action: 'record',
        decision_subtype: 'trade',
        reasoning: 'R-009 A级信号：主线+技术+资金三维共振，swing_points 显示处于历史验证买区',
        context: { regime: 'risk_on', window: 'w-ac60b8e8' },
        parameters: { symbol: '601857', action: 'BUY', quantity: 1000, price: 10.5 },
        related_entity_type: 'stock',
        related_entity_id: '601857',
      },
      expectedBehavior: '返回 decision_id，决策进入审计库（evaluation_status=pending），5天后 evaluate 会用 TradeEvaluationStrategy 计算真实收益',
    },
    {
      scenario: '记录观察决策（等回调）',
      params: {
        action: 'record',
        decision_subtype: 'observation',
        reasoning: '看好标的但当前估值偏高，等待回调至目标价再介入',
        parameters: { symbol: '600519', reason: '等待回调', targetPrice: 1800, watchDays: 5 },
        related_entity_type: 'stock',
        related_entity_id: '600519',
      },
      expectedBehavior: '5天后 evaluate 会用 ObservationEvaluationStrategy 判断：等回调成功 vs 直接起飞错过机会',
    },
    {
      scenario: '记录跳过决策（主动不追）',
      params: {
        action: 'record',
        decision_subtype: 'skip',
        reasoning: '技术面走坏，虽然基本面尚可但短期风险较大，主动跳过',
        parameters: { symbol: '600519', reason: '技术面走坏', checkDays: 10 },
        related_entity_type: 'stock',
        related_entity_id: '600519',
      },
      expectedBehavior: '10天后 evaluate 会用 MissedOpportunityStrategy 自动检测：跳过合理 vs 错过重大机会（涨>15%）',
    },
    {
      scenario: '批量评估 7 天前的决策',
      params: { action: 'evaluate', days: 7 },
      expectedBehavior: '返回 evaluated_count/success_count/failed_count，自动提取经验教训到 memory，发送评估报告',
    },
  ],

  useCases: [
    { title: '交易决策留痕', description: '每笔重要买卖记录推理与上下文，供盘后/周末复盘', example: 'portfolio_trade 后立即 decision_audit record，decision_subtype=trade' },
    { title: '观察决策记录', description: '记录"等回调"、"观察突破"等观察动作，评估观察策略质量', example: 'decision_subtype=observation + reason="等回调"' },
    { title: '主动不追记录（自动错过机会检测）', description: 'skip 记录"为什么没买"，10天后自动检测是否错过机会（涨>15%），零交易日同样产生可复盘资产', example: 'decision_subtype=skip + reason="估值过高"' },
    { title: '盘后评估闭环', description: '每日/每周批量评估到期决策，回填成败并自动提炼知识', example: 'action=evaluate, days=7' },
  ],

  notes: [
    '2026-09-11 DDD 重构：新增 observation/skip 决策类型，接入策略模式评估引擎',
    '自动错过机会检测：skip 决策 10 天后自动检测是否涨 >15%，量化机会成本',
    '观察决策评估：等回调成功 vs 直接起飞、观察突破有效 vs 横盘',
    '评估时机：不同决策类型有不同数据窗口（trade 5天、observation 5天、skip 10天）',
    'evaluation_status：pending（待评估）→ evaluated（已评估，含 success/score/lesson）',
    '向后兼容：decision_type 旧格式仍可用，后端自动推断为对应的 decision_subtype',
    '与 signal_track 的分工：signal_track 跟踪买入信号的价格表现，decision_audit 跟踪决策本身的推理质量',
  ],

  relatedTools: [
    { name: 'decision_history', relationship: '查询已记录的决策', useCase: 'record 后用 decision_history 回看/找待评估决策' },
    { name: 'signal_track', relationship: '信号级追踪', useCase: '买入信号的价格表现跟踪' },
    { name: 'memory_write', relationship: '结论沉淀', useCase: '评估后的教训写 memory' },
    { name: 'swing_points', relationship: '波段买卖点', useCase: 'observation 决策的目标价参考' },
  ],
};
