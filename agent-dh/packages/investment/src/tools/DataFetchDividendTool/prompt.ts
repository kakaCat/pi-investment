/**
 * DataFetchDividendTool - 股息/分红数据工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataFetchDividendParams {
  mode: 'history' | 'screen';
  symbol?: string;
  min_yield?: number;
  min_years?: number;
}

export const dataFetchDividendPrompt: ToolPrompt<DataFetchDividendParams> = {
  description: '股息与分红数据：history=个股历史分红（股息率/分红记录，波段框架的"股息率锚"数据源）；screen=高股息筛选（全市场按最低股息率+连续年数过滤）。适用于：防御型/央企标的的估值锚定、高股息策略选股。⚠️ 依赖 akshare 数据源，夜间/数据源维护时段可能不可用（会返回明确错误，白天重试）。',

  parameters: {
    mode: {
      type: 'string',
      enum: ['history', 'screen'],
      description: 'history=个股分红历史（需 symbol）；screen=高股息筛选',
      required: true,
    },
    symbol: {
      type: 'string',
      description: '股票代码（history 模式必填），如 601857',
    },
    min_yield: {
      type: 'number',
      description: 'screen 模式：最低股息率 %（默认 3）',
    },
    min_years: {
      type: 'integer',
      description: 'screen 模式：连续分红年数（默认 5）/ history 模式：回溯年数',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
    },
    render: (_args: DataFetchDividendParams, value: any) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },

  examples: [
    'data_fetch_dividend({ mode: "history", symbol: "601857" }) // 中石油分红历史',
    'data_fetch_dividend({ mode: "screen", min_yield: 4, min_years: 3 }) // 股息率≥4%且连续3年分红',
  ],

  notes: [
    '2026-09-02 上线（对标 agent-ts data_fetch_dividend；后端 /api/provider/dividend + screen-high-dividend）',
    '⚠️ akshare 数据源夜间常不可用，遇"All data providers failed"白天重试',
    '股息率锚用法：防御型标的买区对应股息率 4.4%+ 时分批建仓（参考 agent-ts 中石油框架）',
  ],

  relatedTools: [
    { name: 'pe_percentile', relationship: '估值分位', useCase: '股息率+PE分位双锚定防御型标的' },
    { name: 'swing_points', relationship: '波段统计', useCase: '高股息标的的波段弹性验证' },
  ],
};
