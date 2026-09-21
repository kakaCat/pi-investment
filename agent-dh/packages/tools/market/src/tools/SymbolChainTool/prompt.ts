import type { ToolPrompt } from '@pi-investment/core-tool';

export interface SymbolChainParams { symbol: string; }

export const symbolChainPrompt: ToolPrompt<SymbolChainParams, any> = {
  name: 'symbol_chain',
  description: '反查个股所属的产业链与环节（只读）。适用于：① 看某只票在产业链中的位置（上游/中游/下游）即其受驱动因子的传导路径；② 判断个股是否与当前主线同链；③ 归因时确认"这只票到底靠什么赚钱"。返回含环节、主营占比证据与置信度分级。',
  parameters: {
    symbol: { type: 'string', description: 'A股6位代码，如 600176', required: true },
  },
  output: {
    schema: { type: 'object', additionalProperties: true, properties: {
      symbol: { type: 'string' },
      chains: { type: 'array', items: { type: 'object', additionalProperties: true }, description: '所属链与环节（含 evidence/confidence/exposure）' },
    }, additionalProperties: true },
    render: (_a: SymbolChainParams, v: any) => [{ type: 'text', text: JSON.stringify(v, null, 2) }],
  },
  examples: [{ scenario: '查中国巨石在玻纤链的位置', params: { symbol: '600176' }, expectedBehavior: '返回链名/环节/主营占比证据' }],
  useCases: [{ title: '位置定位', description: '判断该票在链中的传导位置', example: "symbol_chain({ symbol: '600176' })" }],
  notes: ['2026-09-11 上线（P2/RFC 015 §2）。无记录表示该标的尚未归入任何已策展链（不等于"不在任何产业链中"）。'],
  relatedTools: [
    { name: 'chain_scan', relationship: '整链视角', useCase: '看同环节还有哪些替代标的' },
    { name: 'chain_list', relationship: '入口', useCase: '查看已策展的链' },
  ],
};
