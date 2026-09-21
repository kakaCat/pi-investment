import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ChainScanParams { name: string; include_quotes?: boolean; }

export const chainScanPrompt: ToolPrompt<ChainScanParams, any> = {
  name: 'chain_scan',
  description: '产业链链式扫描（只读）：按**环节**（上游/中游/下游/终端）分组列出成员标的，可选挂实时行情。适用于：① 决策原则#4「链式扫描铁律」——发现驱动因子后扫全产业链而非只看龙头；② 找同环节的替代标/二线弹性；③ 与 mainline_scan 配合（主线给方向、chain_scan 给产业链全貌）。注意事项：成员带 evidence 与 confidence（主营构成 > 行业分类 > 概念成分），引用时须保留证据口径。',
  parameters: {
    name: { type: 'string', description: "产业链名称，如 '玻纤'、'造船'、'电力'（先用 chain_list 确认）", required: true },
    include_quotes: { type: 'boolean', description: '是否附带实时行情（默认 false，开启会增加耗时）' },
  },
  output: {
    schema: { type: 'object', additionalProperties: true, properties: {
      chain: { type: 'string', description: '链名' },
      stages: { type: 'object', additionalProperties: true, description: '按环节分组的成员 {upstream:[], midstream:[], ...}' },
      member_count: { type: 'integer' },
      evidence_note: { type: 'string', description: '证据口径说明' },
    }, additionalProperties: true },
    render: (_a: ChainScanParams, v: any) => [{ type: 'text', text: JSON.stringify(v, null, 2) }],
  },
  examples: [
    { scenario: '扫玻纤链', params: { name: '玻纤' }, expectedBehavior: '返回上游/中游/下游成员 + evidence' },
    { scenario: '扫链并挂行情', params: { name: '造船', include_quotes: true }, expectedBehavior: '成员带现价与涨跌幅' },
  ],
  useCases: [{ title: '链式扫描铁律落地', description: '把"手写链成员"变成"查表+证据"', example: "chain_scan({ name: '玻纤' })" }],
  notes: ['2026-09-11 上线（P2/RFC 015 §2）：此前链式扫描靠手工硬编码成员，且 sector 名不匹配会直接报错。'],
  relatedTools: [
    { name: 'chain_list', relationship: '入口', useCase: '先看有哪些链' },
    { name: 'mainline_scan', relationship: '方向', useCase: '主线给方向、链扫给全貌' },
  ],
};
