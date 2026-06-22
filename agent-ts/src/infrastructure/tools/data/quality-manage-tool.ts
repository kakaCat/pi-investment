/**
 * 数据质量管理工具
 *
 * 提供数据质量检查、缺失检测、数据补充等功能
 */
import type { Tool } from '@mariozechner/pi-agent-core';
import { logger } from '../../../infrastructure/logging/index.js';
import {
  checkDataQuality,
  detectMissingData,
  backfillMissingData,
  validateDataQuality,
} from '../../../infrastructure/adapters/quant/quant-v2-client.js';

interface DataQualityParams {
  action: 'check' | 'detect' | 'backfill' | 'validate';
  symbols?: string[];
  start_date?: string;
  end_date?: string;
  mode?: 'auto' | 'force';
  max_workers?: number;
  include_report?: boolean;
}

export const dataQualityManageTool: Tool = {
  name: 'data_quality_manage',
  description: `数据质量管理工具 - 检测和修复数据缺失、验证数据质量

**功能：**
- check: 检查数据质量（缺失、重复、异常）
- detect: 检测缺失的交易日数据
- backfill: 补充缺失的数据（从多数据源自动获取）
- validate: 验证数据质量（价格范围、涨跌幅、成交量）

**使用场景：**
- 回测前检查数据完整性
- 发现数据缺失自动补充
- 定期数据质量监控
- 数据异常诊断

**数据源：**
- 使用 DataSourceManager 多数据源（AkShare、东方财富、新浪等）
- 自动 failover 和熔断保护
- 批量并行处理，高效快速`,

  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['check', 'detect', 'backfill', 'validate'],
        description: '操作类型：check=检查质量, detect=检测缺失, backfill=补充数据, validate=验证质量'
      },
      symbols: {
        type: 'array',
        items: { type: 'string' },
        description: '股票代码列表（可选，默认热门股票池）'
      },
      start_date: {
        type: 'string',
        description: '开始日期 YYYY-MM-DD（可选，默认最近30天）'
      },
      end_date: {
        type: 'string',
        description: '结束日期 YYYY-MM-DD（可选，默认今天）'
      },
      mode: {
        type: 'string',
        enum: ['auto', 'force'],
        description: '补充模式（仅 backfill 使用）：auto=仅补充缺失, force=强制重新获取'
      },
      max_workers: {
        type: 'number',
        description: '并行线程数（可选，默认8）'
      },
      include_report: {
        type: 'boolean',
        description: '是否生成详细报告（仅 check 使用）'
      }
    },
    required: ['action']
  },

  execute: async (_toolCallId, params: DataQualityParams) => {
    const { action, symbols, start_date, end_date, mode, max_workers, include_report } = params;

    logger.info(`执行数据质量管理: action=${action}, symbols=${symbols?.length || 'all'}`);

    try {
      let result: any;

      switch (action) {
        case 'check':
          // 检查数据质量
          result = await checkDataQuality({
            symbols,
            start_date,
            end_date,
            include_report
          });
          return formatCheckResult(result);

        case 'detect':
          // 检测缺失数据
          result = await detectMissingData({
            symbols,
            start_date,
            end_date
          });
          return formatDetectResult(result);

        case 'backfill':
          // 补充缺失数据
          result = await backfillMissingData({
            symbols,
            start_date,
            end_date,
            mode: mode || 'auto',
            max_workers: max_workers || 8
          });
          return formatBackfillResult(result);

        case 'validate':
          // 验证数据质量
          result = await validateDataQuality({
            symbols,
            start_date,
            end_date
          });
          return formatValidateResult(result);

        default:
          return `错误：未知操作类型 "${action}"`;
      }
    } catch (error: any) {
      logger.error(`数据质量管理失败: ${error.message}`);
      return `执行失败: ${error.message}`;
    }
  }
};

// ========================================
// 格式化函数
// ========================================

function formatCheckResult(result: any): string {
  if (!result.success) {
    return `❌ 检查失败: ${result.error}`;
  }

  const { summary, stocks_with_issues } = result;
  const lines: string[] = [
    '📊 数据质量检查报告',
    '=' .repeat(60),
    '',
    '📈 总体统计：',
    `  • 检查股票数: ${summary.total_stocks}`,
    `  • 有问题股票: ${summary.stocks_with_issues}`,
    `  • 缺失交易日: ${summary.total_missing_days}`,
    `  • 平均覆盖率: ${summary.avg_coverage_rate}%`,
    `  • 数据质量分: ${summary.data_quality_score}/100`,
    ''
  ];

  // 质量评级
  const score = summary.data_quality_score;
  let grade = '';
  if (score >= 95) grade = '🟢 优秀 (A+)';
  else if (score >= 90) grade = '🟢 良好 (A)';
  else if (score >= 80) grade = '🟡 中等 (B)';
  else if (score >= 70) grade = '🟠 较差 (C)';
  else grade = '🔴 很差 (D)';

  lines.push(`  质量评级: ${grade}`, '');

  // 问题股票列表
  if (stocks_with_issues && stocks_with_issues.length > 0) {
    lines.push('⚠️  问题股票列表（前10个）：', '');

    const topIssues = stocks_with_issues.slice(0, 10);
    for (const stock of topIssues) {
      const issues: string[] = [];
      if (stock.missing_days_count > 0) {
        issues.push(`缺失${stock.missing_days_count}天`);
      }
      if (stock.has_duplicates) {
        issues.push(`重复${stock.duplicate_count}条`);
      }
      if (stock.has_anomalies) {
        issues.push(`异常${stock.anomaly_count}处`);
      }

      lines.push(
        `  ${stock.symbol}`,
        `    覆盖率: ${stock.coverage_rate}% | 质量分: ${stock.quality_score}`,
        `    问题: ${issues.join(', ')}`
      );
    }

    if (stocks_with_issues.length > 10) {
      lines.push('', `  ... 还有 ${stocks_with_issues.length - 10} 只股票有问题`);
    }
  } else {
    lines.push('✅ 所有股票数据质量良好！');
  }

  lines.push('', '=' .repeat(60));

  if (result.report_url) {
    lines.push(`📄 详细报告: ${result.report_url}`);
  }

  return lines.join('\n');
}

function formatDetectResult(result: any): string {
  if (!result.success) {
    return `❌ 检测失败: ${result.error}`;
  }

  const { summary, gaps } = result;
  const lines: string[] = [
    '🔍 数据缺失检测报告',
    '=' .repeat(60),
    '',
    '📊 缺失统计：',
    `  • 检查股票数: ${summary.total_stocks}`,
    `  • 缺失股票数: ${summary.stocks_with_gaps}`,
    `  • 总缺失天数: ${summary.total_missing_days}`,
    `  • 平均覆盖率: ${summary.avg_coverage_rate}%`,
    ''
  ];

  if (summary.stocks_with_gaps === 0) {
    lines.push('✅ 未发现数据缺失！');
  } else {
    lines.push('📋 缺失详情（覆盖率最低的前10只）：', '');

    const worstStocks = summary.worst_stocks.slice(0, 10);
    for (const stock of worstStocks) {
      const gap = gaps[stock.symbol];
      lines.push(
        `  ${stock.symbol}`,
        `    覆盖率: ${stock.coverage_rate}% | 缺失: ${stock.missing_days} 天`
      );

      // 显示缺失段
      if (gap && gap.missing_segments && gap.missing_segments.length > 0) {
        const segments = gap.missing_segments.slice(0, 3);
        for (const seg of segments) {
          if (seg.start === seg.end) {
            lines.push(`      - ${seg.start}`);
          } else {
            lines.push(`      - ${seg.start} ~ ${seg.end} (${seg.days}天)`);
          }
        }
        if (gap.missing_segments.length > 3) {
          lines.push(`      ... 还有 ${gap.missing_segments.length - 3} 个缺失段`);
        }
      }
    }
  }

  lines.push('', '=' .repeat(60));
  return lines.join('\n');
}

function formatBackfillResult(result: any): string {
  if (!result.success) {
    return `❌ 补充失败: ${result.error}`;
  }

  const { summary, failed_symbols } = result;
  const lines: string[] = [
    '🔧 数据补充完成报告',
    '=' .repeat(60),
    '',
    '📊 补充统计：',
    `  • 处理股票数: ${summary.total_stocks}`,
    `  • 成功股票数: ${summary.success_count}`,
    `  • 失败股票数: ${summary.failed_count}`,
    `  • 补充交易日: ${summary.total_days_filled} 天`,
    `  • 耗时: ${summary.elapsed_time}s`,
    ''
  ];

  // 成功率
  const successRate = (summary.success_count / summary.total_stocks * 100).toFixed(1);
  let statusIcon = '';
  if (summary.failed_count === 0) {
    statusIcon = '✅';
  } else if (parseFloat(successRate) >= 90) {
    statusIcon = '🟡';
  } else {
    statusIcon = '🔴';
  }

  lines.push(`  ${statusIcon} 成功率: ${successRate}%`, '');

  // 失败股票列表
  if (failed_symbols && failed_symbols.length > 0) {
    lines.push('⚠️  失败股票列表：', '');
    const displayFailed = failed_symbols.slice(0, 20);
    for (const symbol of displayFailed) {
      lines.push(`  - ${symbol}`);
    }
    if (failed_symbols.length > 20) {
      lines.push(`  ... 还有 ${failed_symbols.length - 20} 只`);
    }
    lines.push('', '💡 建议: 使用 data_quality_manage(action="backfill", symbols=[失败列表], mode="force") 重试');
  } else {
    lines.push('✅ 所有股票数据补充成功！');
  }

  lines.push('', '=' .repeat(60));
  return lines.join('\n');
}

function formatValidateResult(result: any): string {
  if (!result.success) {
    return `❌ 验证失败: ${result.error}`;
  }

  const { summary, validation_results } = result;
  const lines: string[] = [
    '✔️  数据质量验证报告',
    '=' .repeat(60),
    '',
    '📊 验证统计：',
    `  • 验证股票数: ${summary.total_stocks}`,
    `  • 有问题股票: ${summary.stocks_with_issues}`,
    ''
  ];

  if (summary.stocks_with_issues === 0) {
    lines.push('✅ 所有股票数据验证通过！');
  } else {
    lines.push('⚠️  验证问题列表（前10个）：', '');

    const topIssues = validation_results.slice(0, 10);
    for (const item of topIssues) {
      lines.push(
        `  ${item.symbol}`,
        `    有效记录: ${item.total_records - item.invalid_records}/${item.total_records}`
      );

      const issues: string[] = [];
      if (item.invalid_records > 0) {
        issues.push(`${item.invalid_records}条无效`);
      }
      if (item.has_duplicates) {
        issues.push(`${item.duplicate_count}条重复`);
      }
      if (item.has_anomalies) {
        issues.push(`${item.anomaly_count}处异常`);
      }

      if (issues.length > 0) {
        lines.push(`    问题: ${issues.join(', ')}`);
      }

      // 显示前几个验证错误
      if (item.validation_errors && item.validation_errors.length > 0) {
        const firstError = item.validation_errors[0];
        lines.push(`    示例: ${firstError.date} - ${firstError.errors.join(', ')}`);
      }
    }
  }

  lines.push('', '=' .repeat(60));
  return lines.join('\n');
}
