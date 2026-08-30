import type { ToolPrompt } from '@pi-investment/core-tool';

export interface KlineDailySyncParams {
  date?: string;
  symbols?: string[];
  force?: boolean;
}

export interface KlineDailySyncResult {
  sync_date: string;
  total_symbols: number;
  success_count: number;
  failed_count: number;
  skipped_count: number;
  failed_symbols: string[];
  duration_seconds: number;
  message: string;
}

export const klineDailySyncPrompt: ToolPrompt<KlineDailySyncParams, KlineDailySyncResult> = {
  description: '同步日K线数据：默认同步今日全市场，支持指定日期、股票列表、强制更新',
  useCases: [
    '每日收盘后同步当日K线数据',
    '补充历史缺失的K线数据',
    '强制重新同步有问题的K线',
    '同步特定股票池的K线数据',
  ],
  parameters: {
    date: {
      type: 'string',
      description: '日期（YYYY-MM-DD），默认为今日',
    },
    symbols: {
      type: 'array',
      description: '股票代码列表，不指定则同步全市场',
    },
    force: {
      type: 'boolean',
      description: '是否强制更新已存在的数据',
      default: false,
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        sync_date: { type: 'string' },
        total_symbols: { type: 'number' },
        success_count: { type: 'number' },
        failed_count: { type: 'number' },
        skipped_count: { type: 'number' },
        failed_symbols: { type: 'array', items: { type: 'string' } },
        duration_seconds: { type: 'number' },
        message: { type: 'string' },
      },
    },
  },
  examples: [
    {
      input: {
        date: '2026-08-28',
      },
      output: {
        sync_date: '2026-08-28',
        total_symbols: 5000,
        success_count: 4998,
        failed_count: 2,
        skipped_count: 0,
        failed_symbols: ['600001', '000001'],
        duration_seconds: 120,
        message: '同步完成：4998 成功，2 失败',
      },
      description: '同步指定日期全市场K线',
    },
    {
      input: {
        date: '2026-08-28',
        symbols: ['600519', '000858', '600036'],
      },
      output: {
        sync_date: '2026-08-28',
        total_symbols: 3,
        success_count: 3,
        failed_count: 0,
        skipped_count: 0,
        failed_symbols: [],
        duration_seconds: 5,
        message: '同步完成：3 成功，0 失败',
      },
      description: '同步指定股票列表的K线',
    },
    {
      input: {
        date: '2026-08-27',
        symbols: ['600519'],
        force: true,
      },
      output: {
        sync_date: '2026-08-27',
        total_symbols: 1,
        success_count: 1,
        failed_count: 0,
        skipped_count: 0,
        failed_symbols: [],
        duration_seconds: 2,
        message: '强制同步完成：1 成功，0 失败',
      },
      description: '强制重新同步已存在的K线',
    },
  ],
};
