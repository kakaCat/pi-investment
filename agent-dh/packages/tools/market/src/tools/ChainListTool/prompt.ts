import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ChainListParams { /** 无参数 */ }

export const chainListPrompt: ToolPrompt<ChainListParams, any> = {
  name: 'chain_list',
  description: '列出全部产业链（只读）。适用于：① 决策原则#4「链式扫描」的入口——先看有哪些链可扫；② 确认链名后再用 chain_scan 下钻。每条链返回成员数、环节数与最近刷新时间。',
  parameters: {},
  output: {
    schema: { type: 'object', additionalProperties: true, properties: {
      count: { type: 'integer', description: '产业链条数' },
      chains: { type: 'array', items: { type: 'object', additionalProperties: true }, description: '链条目（name/member_count/node_count/updated_at）' },
    }, additionalProperties: true },
    render: (_a: ChainListParams, v: any) => [{ type: 'text', text: JSON.stringify(v, null, 2) }],
  },
  examples: [{ scenario: '看有哪些产业链', params: {}, expectedBehavior: '返回链条目与成员数' }],
  useCases: [{ title: '链式扫描入口', description: '确认链名后下钻', example: 'chain_list({})' }],
  notes: ['2026-09-11 上线（P2/RFC 015 §2）。环节拓扑为人工策展（不可 LLM 自动生成），成员归位带 evidence 与 confidence 分级。'],
  relatedTools: [
    { name: 'chain_scan', relationship: '下钻扫描', useCase: '选定链后按环节扫描成员' },
    { name: 'symbol_chain', relationship: '反查', useCase: '已知个股反查所属链' },
  ],
};
