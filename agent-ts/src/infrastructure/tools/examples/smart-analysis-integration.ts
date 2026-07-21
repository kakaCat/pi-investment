/**
 * Agent工具 - 数据健康检查集成示例
 *
 * 在调用analysis_swing_points等工具前，先检查数据健康状况
 */

import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface DataHealthResult {
  valid: boolean;
  exists: boolean;
  has_recent_data: boolean;
  data_summary?: {
    first_date: string;
    last_date: string;
    total_records: number;
    days_since_update: number;
  };
  suggestions?: string[];
  similar_codes?: string[];
}

/**
 * 检查股票数据健康状况
 */
export async function checkStockDataHealth(symbol: string): Promise<DataHealthResult> {
  try {
    const result = await runQuantV2<DataHealthResult>('analysis.data_health', { symbol });
    if (!result.ok || !result.data) {
      return {
        valid: false,
        exists: false,
        has_recent_data: false,
        suggestions: [result.error?.message || '数据健康检查失败，请稍后重试']
      };
    }
    return result.data;
  } catch (error) {
    return {
      valid: false,
      exists: false,
      has_recent_data: false,
      suggestions: ['数据健康检查失败，请稍后重试']
    };
  }
}

/**
 * 智能波段分析 - 带数据预检查
 *
 * 使用示例：
 * ```typescript
 * const result = await smartSwingPointsAnalysis('600519', { min_change: 5 });
 * if (result.success) {
 *   console.log('分析成功:', result.data);
 * } else {
 *   console.log('失败原因:', result.error);
 *   console.log('建议:', result.suggestions);
 * }
 * ```
 */
export async function smartSwingPointsAnalysis(
  symbol: string,
  options: {
    start_date?: string;
    end_date?: string;
    min_change?: number;
    skip_health_check?: boolean;  // 跳过健康检查（用于已验证的场景）
  } = {}
) {
  // 1. 数据健康预检查（可选但推荐）
  if (!options.skip_health_check) {
    const health = await checkStockDataHealth(symbol);

    if (!health.valid) {
      return {
        success: false,
        error: `股票代码 ${symbol} 无效或无数据`,
        suggestions: health.suggestions || [],
        health_check: health
      };
    }

    // 警告：数据不够新鲜
    if (!health.has_recent_data && health.data_summary) {
      const days = health.data_summary.days_since_update;
      console.warn(
        `[警告] ${symbol} 数据已 ${days} 天未更新，分析结果可能不准确`
      );
    }
  }

  // 2. 执行波段分析
  try {
    const result = await runQuantV2<Record<string, unknown>>('analysis.swing_points', {
      symbol,
      start_date: options.start_date,
      end_date: options.end_date,
      min_change: options.min_change || 5
    });

    if (!result.ok) {
      return {
        success: false,
        error: result.error?.message || '波段分析失败',
        suggestions: [
          '请检查参数是否正确',
          '如果问题持续，请联系技术支持'
        ]
      };
    }

    return {
      success: true,
      data: result.data
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      suggestions: [
        '请检查参数是否正确',
        '如果问题持续，请联系技术支持'
      ]
    };
  }
}

/**
 * 批量股票健康检查 - 用于早盘任务
 *
 * 在早盘分析前，批量检查待分析股票的数据健康状况
 */
export async function batchHealthCheck(symbols: string[]): Promise<{
  healthy: string[];
  warnings: Array<{ symbol: string; reason: string }>;
  invalid: Array<{ symbol: string; reason: string }>;
}> {
  const results = {
    healthy: [] as string[],
    warnings: [] as Array<{ symbol: string; reason: string }>,
    invalid: [] as Array<{ symbol: string; reason: string }>
  };

  for (const symbol of symbols) {
    const health = await checkStockDataHealth(symbol);

    if (!health.valid) {
      results.invalid.push({
        symbol,
        reason: health.suggestions?.[0] || '数据不存在'
      });
    } else if (!health.has_recent_data) {
      results.warnings.push({
        symbol,
        reason: `数据已 ${health.data_summary?.days_since_update} 天未更新`
      });
    } else {
      results.healthy.push(symbol);
    }

    // 避免请求过快
    await new Promise(resolve => setTimeout(resolve, 50));
  }

  return results;
}

/**
 * Agent早盘分析工作流 - 集成示例
 */
export async function morningAnalysisWorkflow(stockPool: string[]) {
  console.log('🌅 开始早盘分析...');
  console.log(`📋 股票池: ${stockPool.length}只股票\n`);

  // 1. 批量健康检查
  console.log('🔍 步骤1: 数据健康检查');
  const healthCheck = await batchHealthCheck(stockPool);

  console.log(`  ✅ 健康: ${healthCheck.healthy.length}只`);
  console.log(`  ⚠️  警告: ${healthCheck.warnings.length}只`);
  console.log(`  ❌ 无效: ${healthCheck.invalid.length}只\n`);

  if (healthCheck.invalid.length > 0) {
    console.log('  无效股票:');
    healthCheck.invalid.forEach(item => {
      console.log(`    • ${item.symbol}: ${item.reason}`);
    });
    console.log('');
  }

  // 2. 仅对健康的股票执行波段分析
  console.log('📊 步骤2: 波段分析');
  const analysisResults = [];

  for (const symbol of healthCheck.healthy) {
    const result = await smartSwingPointsAnalysis(symbol, {
      min_change: 5,
      skip_health_check: true  // 已检查过，跳过
    });

    if (result.success) {
      console.log(`  ✅ ${symbol}: 分析完成`);
      analysisResults.push({ symbol, ...result.data });
    } else {
      console.log(`  ❌ ${symbol}: ${result.error}`);
    }
  }

  // 3. 生成报告
  console.log('\n📝 早盘分析报告:');
  console.log(`  • 总股票数: ${stockPool.length}`);
  console.log(`  • 成功分析: ${analysisResults.length}`);
  console.log(`  • 跳过(无效): ${healthCheck.invalid.length}`);
  console.log(`  • 跳过(数据陈旧): ${healthCheck.warnings.length}`);

  return {
    total: stockPool.length,
    analyzed: analysisResults,
    skipped: [...healthCheck.invalid, ...healthCheck.warnings]
  };
}

// 导出
export default {
  checkStockDataHealth,
  smartSwingPointsAnalysis,
  batchHealthCheck,
  morningAnalysisWorkflow
};
