import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataQualityReportParams {
  data_type?: 'quote' | 'kline' | 'financial' | 'all';
  days?: number;
}

export interface DataQualityReportResult {
  data_type: string;
  check_date: string;
  overall_score: number;
  missing_data: any[];
  delayed_data: any[];
  anomalies: any[];
  summary: string;
}

export const dataQualityReportPrompt: ToolPrompt<DataQualityReportParams, DataQualityReportResult> = {
  description: '生成数据质量报告：整体评分、缺失数据、延迟数据、异常值列表及质量摘要',
  useCases: [
    '定期（如每日盘前）检查数据健康度',
    '发现数据质量问题',
    '评估数据可用性',
    '决策前验证数据准备就绪',
  ],
  examples: [
    {
      input: {
        data_type: 'all',
        days: 7,
      },
      output: {
        data_type: 'all',
        check_date: '2026-08-28',
        overall_score: 92.5,
        missing_data: [
          { symbol: '600519', date: '2026-08-27', type: 'kline' },
        ],
        delayed_data: [
          { symbol: '000858', date: '2026-08-26', type: 'quote', delay_hours: 4 },
        ],
        anomalies: [
          { symbol: '600036', date: '2026-08-25', type: 'price_spike', value: 15.8 },
        ],
        summary: '整体数据质量良好，1 处缺失，1 处延迟，1 处异常值需关注',
      },
      description: '检查所有数据类型',
    },
    {
      input: {
        data_type: 'kline',
        days: 3,
      },
      output: {
        data_type: 'kline',
        check_date: '2026-08-28',
        overall_score: 98.0,
        missing_data: [],
        delayed_data: [],
        anomalies: [],
        summary: 'K线数据质量优秀，无问题',
      },
      description: '检查 K线数据质量',
    },
  ],
};
