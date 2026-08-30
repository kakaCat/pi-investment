/**
 * MainlineStocksTool - 主线个股明细查询工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 主线个股明细查询参数
 */
export interface MainlineStocksParams {
  /** 板块名称（如"电力设备"） */
  sector: string;
  /** 查询天数（默认 5） */
  days?: number;
}

/**
 * 主线个股明细查询结果
 */
export interface MainlineStocksResult {
  /** 板块名称 */
  sector: string;
  /** 个股列表 */
  stocks: Array<{
    /** 股票代码（如 "600519"） */
    symbol: string;
    /** 股票名称（如 "贵州茅台"） */
    name: string;
    /** 涨跌幅（百分比） */
    change_pct?: number;
    /** 成交量 */
    volume?: number;
    /** 市值（亿元） */
    market_cap?: number;
    /** 所属行业 */
    industry?: string;
    /** 备注信息 */
    note?: string;
  }>;
  /** 查询时间范围 */
  days: number;
}

/**
 * 主线个股明细查询工具提示词定义
 */
export const mainlineStocksPrompt: ToolPrompt<MainlineStocksParams, MainlineStocksResult> = {
  description: '获取特定主线板块的个股明细列表',
  useCases: [
    '查看某个热门板块的成分股和表现',
    '分析主线板块内的个股分化情况',
    '选取板块内强势个股作为交易标的',
  ],
  examples: [
    {
      title: '查询电力设备板块个股',
      params: { sector: '电力设备', days: 5 },
      expectedResult: '返回电力设备板块的成分股列表，包含宁德时代、比亚迪等龙头股',
    },
  ],
  notes: [
    '板块名称需要精确匹配',
    '返回结果按市值排序',
  ],
  relatedTools: ['mainline_scan', 'sector_analysis'],
  parameters: {
    sector: {
      type: 'string',
      description: '板块名称（如"电力设备"、"新能源汽车"等）',
      required: true,
    },
    days: {
      type: 'number',
      description: '查询天数（1-90），默认 5 天',
      default: 5,
      minimum: 1,
      maximum: 90,
      example: 5,
    },
  },
  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        sector: { type: 'string', description: '板块名称' },
        stocks: {
          type: 'array',
          description: '个股列表数组，包含代码、名称、涨跌幅、成交量等信息',
        },
        days: { type: 'number', description: '实际查询天数' },
      },
    },
    render: (_args: MainlineStocksParams, data: MainlineStocksResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
