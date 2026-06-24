/**
 * ToolResultPersister 使用示例
 *
 * 展示如何在工具中集成数据持久化功能
 */

import { saveToolResult, PersistedResult } from './result-persister.js';

/**
 * 示例1: 回测工具集成
 */
async function indicatorBacktestExample(params: {
  indicator_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
}): Promise<PersistedResult> {
  // 1. 调用后端API获取数据
  const backtestResult = await fetch(`http://127.0.0.1:5001/api/backtest/indicator`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  }).then(res => res.json());

  // 2. 保存结果到本地文件
  const result = await saveToolResult({
    toolName: 'indicator_backtest',
    data: backtestResult,
    summary: `指标${params.indicator_id}在${params.symbol!}的回测完成`,
    metadata: {
      indicator_id: params.indicator_id,
      symbol: params.symbol!,
      start_date: params.start_date!,
      end_date: params.end_date!,
    },
  });

  // 3. 返回持久化结果（包含文件路径）
  return result;
}

/**
 * 示例2: 股票池验证工具集成
 */
async function poolValidateExample(params: {
  pool_id: number;
  strategy_ids: number[];
}): Promise<PersistedResult> {
  const validateResult = await fetch(`http://127.0.0.1:5001/api/pools/${params.pool_id}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy_ids: params.strategy_ids }),
  }).then(res => res.json());

  // 自定义摘要信息
  const summary = `
    验证池子${params.pool_id}的${params.strategy_ids.length}个策略
    最优策略: ${validateResult.best_strategy?.name || 'N/A'}
    最佳股票: ${validateResult.top_stocks?.slice(0, 3).join(', ') || 'N/A'}
  `.trim();

  return await saveToolResult({
    toolName: 'pool_validate',
    data: validateResult,
    summary,
    metadata: {
      pool_id: params.pool_id,
      strategy_count: params.strategy_ids.length,
    },
  });
}

/**
 * 示例3: 大数据查询工具集成（如市场概览）
 */
async function marketOverviewExample(): Promise<PersistedResult> {
  const marketData = await fetch('http://127.0.0.1:5001/api/market/overview')
    .then(res => res.json());

  return await saveToolResult({
    toolName: 'market_overview',
    data: marketData,
    // 不提供summary时会自动生成
    metadata: {
      query_time: new Date().toISOString(),
    },
  });
}

/**
 * 示例4: 在现有工具定义中使用
 */
export const indicatorBacktestToolDefinition = {
  name: 'indicator_backtest',
  description: '指标回测工具',
  parameters: {
    type: 'object',
    properties: {
      indicator_id: { type: 'number' },
      symbol: { type: 'string' },
      start_date: { type: 'string' },
      end_date: { type: 'string' },
    },
    required: ['indicator_id', 'symbol', 'start_date', 'end_date'],
  },

  async handler(params: any) {
    try {
      // 调用后端
      const response = await fetch('http://127.0.0.1:5001/api/backtest/indicator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });

      const data = await response.json();

      // 保存到本地文件
      const persisted = await saveToolResult({
        toolName: 'indicator_backtest',
        data,
        summary: `指标 ${params.indicator_id} 回测完成：收益率 ${data.return_pct?.toFixed(2)}%`,
        metadata: params,
      });

      // 返回持久化结果（LLM会收到文件路径提示）
      return persisted;

    } catch (error) {
      return {
        success: false,
        message: `回测失败: ${error instanceof Error ? error.message : String(error)}`,
      };
    }
  },
};

/**
 * 示例5: 条件持久化（仅大数据才保存）
 */
async function conditionalPersistExample(data: any): Promise<any> {
  const dataSize = JSON.stringify(data).length;
  const THRESHOLD = 50 * 1024; // 50KB

  if (dataSize > THRESHOLD) {
    // 数据量大，保存到文件
    return await saveToolResult({
      toolName: 'large_data_query',
      data,
      summary: `数据量较大 (${(dataSize / 1024).toFixed(2)} KB)，已保存到文件`,
    });
  } else {
    // 数据量小，直接返回
    return {
      success: true,
      data,
      message: '数据量较小，直接返回',
    };
  }
}

/**
 * 工具返回格式对比
 */

// ❌ 旧方式：直接返回大量数据
const oldWay = {
  success: true,
  data: {
    // 大量回测数据（几千行）
    trades: [], // 数百条交易记录
    daily_returns: [], // 数百天的收益
    // ... 更多数据
  },
};

// ✅ 新方式：返回文件路径 + 摘要
const newWay = {
  success: true,
  filePath: '/path/to/indicator_backtest_20260603_123456.json',
  summary: '大小: 2.5 MB, 包含 245 条交易记录',
  message: '数据已保存到 indicator_backtest_20260603_123456.json。大小: 2.5 MB\n\n💡 使用 Read 工具查看完整数据：Read({ file_path: "/path/to/file.json" })',
  metadata: {
    indicator_id: 1,
    symbol: '600000',
  },
  timestamp: '2026-06-03T12:34:56.789Z',
};
