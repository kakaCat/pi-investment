/**
 * IndexConstituentsTool - 指数成分股（基准成分池）
 *
 * 背景（2026-09-11，REQ-cf627b，w-f436d4ea）：基准数据此前不可达，risk_metrics 已接入
 * 沪深300 做业绩归因，但「成分股清单」维度缺失——导致无法按基准池选股、无法校验个股
 * 是否属于主流指数。后端 /api/provider/index/{symbol}/constituents 已具备该能力，
 * 本工具把它接到 Agent 可用面。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface IndexConstituentsParams {
  symbol: string;
}

export interface IndexConstituentsResult {
  symbol: string;
  count: number;
  constituents: string[];
  available: boolean;
  source?: string;
  note?: string;
}

export const indexConstituentsPrompt: ToolPrompt<IndexConstituentsParams, IndexConstituentsResult> = {
  name: 'index_constituents',
  description: '查询指数成分股代码清单（只读）。适用于：①按基准成分池选股/做相对强弱比较（如只在沪深300内选）；②核验个股是否属于主流宽基或行业指数；③与 risk_metrics 的业绩归因（benchmark=000300）配套做基准核对。注意：返回的是成分代码清单，不含权重与调样日期。',

  parameters: {
    symbol: {
      type: 'string',
      description: '指数代码（6位数字）：000300=沪深300、000905=中证500、000852=中证1000、399006=创业板指、000016=上证50',
      required: true,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string', description: '指数代码' },
        count: { type: 'integer', description: '成分股数量' },
        constituents: { type: 'array', items: { type: 'string' }, description: '成分股6位代码清单' },
        available: { type: 'boolean', description: '数据是否可用' },
        source: { type: 'string', description: '数据来源' },
        note: { type: 'string', description: '口径说明（不含权重、取数时点）' },
      },
      additionalProperties: true,
    },
    render: (_args: IndexConstituentsParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    { scenario: '查沪深300成分股', params: { symbol: '000300' }, expectedBehavior: '返回 count 与 constituents 代码数组' },
    { scenario: '查创业板指成分股', params: { symbol: '399006' }, expectedBehavior: '返回该指数成分清单' },
  ],

  useCases: [
    { title: '基准池内选股', description: '把候选限定在基准成分池内，避免买到流动性差的小票', example: "index_constituents({ symbol: '000300' })" },
    { title: '归因配套核对', description: 'risk_metrics 的 attribution 用 000300 作基准，本工具给出该基准的成分口径', example: '对比组合持仓与基准成分的重合度' },
  ],

  notes: [
    '2026-09-11 上线（REQ-cf627b）：后端端点早已存在但未暴露为工具，本工具补上接线。',
    '数据源失败与空结果语义不同：失败必须显式报错，禁止静默返回空清单（否则会被误判为「该指数无成分股」）。',
    '不返回权重与调样日期；权重维度需后端补齐后再扩展。',
  ],

  relatedTools: [
    { name: 'risk_metrics', relationship: '业绩归因', useCase: '归因基准 000300 与成分清单配套使用' },
    { name: 'screening', relationship: '条件选股', useCase: '先用本工具锁定股票池范围，再用 screening 做条件筛选' },
  ],
};
