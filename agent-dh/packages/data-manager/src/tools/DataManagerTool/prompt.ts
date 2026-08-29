import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataManagerParams {
  operation: 'status' | 'refresh' | 'cleanup' | 'backup';
  data_type?: 'quote' | 'kline' | 'financial' | 'all';
  symbol?: string;
  start_date?: string;
  end_date?: string;
}

export interface DataManagerResult {
  operation: string;
  data_type: string;
  status: string;
  message: string;
  details?: any;
}

export const dataManagerPrompt: ToolPrompt<DataManagerParams, DataManagerResult> = {
  description: '数据管理工具：查询状态、刷新数据、清理缓存、备份数据',
  useCases: [
    '查询数据源状态和最新更新时间',
    '刷新特定股票或时间段的数据',
    '清理过期缓存释放存储空间',
    '备份关键数据防止丢失',
  ],
  examples: [
    {
      input: {
        operation: 'status',
        data_type: 'all',
      },
      output: {
        operation: 'status',
        data_type: 'all',
        status: 'success',
        message: '数据状态查询成功',
        details: {
          quote: { last_update: '2026-08-28 15:00:00', count: 5000 },
          kline: { last_update: '2026-08-28 15:00:00', count: 1500000 },
          financial: { last_update: '2026-08-27 20:00:00', count: 45000 },
        },
      },
      description: '查询所有数据类型的状态',
    },
    {
      input: {
        operation: 'refresh',
        data_type: 'kline',
        symbol: '600519',
        start_date: '2026-08-01',
        end_date: '2026-08-28',
      },
      output: {
        operation: 'refresh',
        data_type: 'kline',
        status: 'success',
        message: '数据刷新成功',
        details: {
          symbol: '600519',
          records_updated: 20,
          time_range: '2026-08-01 至 2026-08-28',
        },
      },
      description: '刷新特定股票的K线数据',
    },
    {
      input: {
        operation: 'cleanup',
        data_type: 'all',
      },
      output: {
        operation: 'cleanup',
        data_type: 'all',
        status: 'success',
        message: '缓存清理完成',
        details: {
          space_freed: '2.3 GB',
          records_deleted: 150000,
        },
      },
      description: '清理所有过期缓存',
    },
  ],
};
