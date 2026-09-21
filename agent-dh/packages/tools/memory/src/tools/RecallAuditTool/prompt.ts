/**
 * RecallAuditTool - 记忆召回审计（memory_recall_audit）
 *
 * 背景（2026-09-11，REQ-cf627b，w-f436d4ea）：R-008 要求「决策前必须检索历史教训」，
 * 但召回长期存在零命中现象——无法区分『库里真没有』与『检索坏了』。后端
 * /api/memory/recall-audit(stats) 记录了每次召回的命中/压制与原因，本工具把它暴露出来，
 * 使 R-008 从「动作合规」升级为「效果可测」。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface RecallAuditParams {
  action?: 'stats' | 'list';
  date_from?: string;
  date_to?: string;
  flow?: string;
  suppressed_only?: boolean;
  page?: number;
  page_size?: number;
}

export const recallAuditPrompt: ToolPrompt<RecallAuditParams, any> = {
  name: 'memory_recall_audit',
  description: '记忆召回审计（只读）：stats=全局统计（总召回/注入/压制/注入率/按 flow 分布/压制原因/分数直方图），list=逐条明细（查询原文/策略/是否降级/压制原因/命中列表及分数）。适用于：①判断「记忆检索零命中」是库里没有还是检索失效——看 suppress_reasons 是否为 empty-result；②验证 R-008「决策前检索」是否真的在起作用；③定位召回质量下降的时间段。',

  parameters: {
    action: {
      type: 'string',
      description: "stats=统计（默认），list=明细",
      enum: ['stats', 'list'],
    },
    date_from: { type: 'string', description: '起始日期 YYYY-MM-DD（可选）' },
    date_to: { type: 'string', description: '结束日期 YYYY-MM-DD（可选）' },
    flow: { type: 'string', description: '按触发来源过滤（list）：interactive-chat / scheduled-task / wake-event / skill-invocation 等' },
    suppressed_only: { type: 'boolean', description: '只看被压制的召回（list，可选）' },
    page: { type: 'integer', description: '页码（list，默认 1）' },
    page_size: { type: 'integer', description: '每页条数（list，默认 20，上限 100）' },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        action: { type: 'string', description: '执行的动作 stats/list' },
        total: { type: 'integer', description: '召回总次数' },
        injected: { type: 'integer', description: '注入到上下文的次数' },
        suppressed: { type: 'integer', description: '被压制的次数' },
        injection_rate: { type: 'number', description: '注入率 0-1' },
        interpretation: { type: 'string', description: '对当前压制原因的口径解读' },
      },
      additionalProperties: true,
    },
    render: (_args: RecallAuditParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    { scenario: '看召回整体健康度', params: { action: 'stats' }, expectedBehavior: '返回 total/injected/suppressed/injection_rate 与压制原因分布' },
    { scenario: '查某次零命中的原因', params: { action: 'list', suppressed_only: true, page_size: 5 }, expectedBehavior: '返回被压制的查询原文与 suppress_reason' },
  ],

  useCases: [
    { title: '区分「无记录」与「检索失效」', description: 'suppress_reasons 全是 empty-result 时说明该主题确实无历史；若出现其他压制原因或命中分数异常低，才是检索问题', example: "memory_recall_audit({ action: 'stats' })" },
    { title: 'R-008 效果验证', description: '按流过滤，验证交互/定时任务场景下召回是否真的注入了上下文', example: "memory_recall_audit({ action: 'list', flow: 'skill-invocation' })" },
  ],

  notes: [
    '2026-09-11 上线（REQ-cf627b）：端点为裸 JSON（非 {success,data} 包裹），客户端已按此契约实现。',
    'injection_rate 低不等于故障：压制主因通常是 empty-result（库里无相关内容），需结合 suppress_reasons 解读。',
  ],

  relatedTools: [
    { name: 'memory_search', relationship: '记忆检索', useCase: 'search 零命中后用本工具判断是库空还是检索坏' },
    { name: 'experience_stats', relationship: '经验胜率', useCase: '经验库样本量与召回效果交叉核对' },
  ],
};
