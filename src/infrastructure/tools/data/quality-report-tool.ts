/**
 * 数据质量报告工具
 *
 * 用于查询和展示K线数据质量报告
 */

import type { ToolDefinition } from '@mariozechner/pi-coding-agent';
import { Type } from '@sinclair/typebox';
import { runQuantV2 } from '../../adapters/quant/quant-v2-client.js';

interface DataQualityReportParams {
  action: 'report' | 'stats' | 'summary' | 'trend';
  symbol?: string;
  start_date?: string;
  end_date?: string;
  min_score?: number;
  max_score?: number;
  grade?: 'A+' | 'A' | 'B' | 'C' | 'D';
  limit?: number;
  offset?: number;
  days?: number;
}

export const dataQualityReportTool: ToolDefinition = {
  name: 'data_quality_report',
  label: '数据质量报告',
  description: `
查询K线数据质量报告和统计信息

支持四种操作：
1. report - 查询质量记录列表（支持多维度筛选）
2. stats - 查询每日统计数据
3. summary - 查询质量摘要
4. trend - 查询质量趋势（用于图表）

适用场景：
- 查看历史数据质量问题
- 分析数据质量趋势
- 监控特定股票的数据质量
- 生成质量报告
`.trim(),

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('report'),
      Type.Literal('stats'),
      Type.Literal('summary'),
      Type.Literal('trend')
    ], { description: '操作类型：report=查询记录, stats=每日统计, summary=质量摘要, trend=趋势数据' }),
    symbol: Type.Optional(Type.String({ description: '股票代码（可选），如 600519.SH' })),
    start_date: Type.Optional(Type.String({ description: '开始日期 YYYY-MM-DD（可选）' })),
    end_date: Type.Optional(Type.String({ description: '结束日期 YYYY-MM-DD（可选）' })),
    min_score: Type.Optional(Type.Number({ description: '最低评分 0-100（可选）' })),
    max_score: Type.Optional(Type.Number({ description: '最高评分 0-100（可选）' })),
    grade: Type.Optional(Type.Union([
      Type.Literal('A+'),
      Type.Literal('A'),
      Type.Literal('B'),
      Type.Literal('C'),
      Type.Literal('D')
    ], { description: '质量评级（可选）' })),
    limit: Type.Optional(Type.Number({ description: '返回数量（默认100）' })),
    offset: Type.Optional(Type.Number({ description: '偏移量（默认0）' })),
    days: Type.Optional(Type.Number({ description: '统计天数（默认7或30，根据action不同）' }))
  }),

  execute: async (_toolCallId, params: any) => {
    try {
      const typedParams = params as DataQualityReportParams;
      const { action } = typedParams;

      let result: any;

      switch (action) {
        case 'report':
          result = await fetchQualityReport(typedParams);
          break;

        case 'stats':
          result = await fetchQualityStats(typedParams);
          break;

        case 'summary':
          result = await fetchQualitySummary(typedParams);
          break;

        case 'trend':
          result = await fetchQualityTrend(typedParams);
          break;

        default:
          throw new Error(`不支持的操作: ${action}`);
      }

      return {
        content: [{
          type: "text" as const,
          text: result
        }],
        details: { action, success: true },
      };

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `数据质量查询失败: ${errorMessage}`
        }],
        details: { success: false, error: errorMessage },
      };
    }
  },
};

/**
 * 查询质量记录
 */
async function fetchQualityReport(params: DataQualityReportParams): Promise<any> {
  const queryParams: Record<string, any> = {};

  if (params.symbol) queryParams.symbol = params.symbol;
  if (params.start_date) queryParams.start_date = params.start_date;
  if (params.end_date) queryParams.end_date = params.end_date;
  if (params.min_score !== undefined) queryParams.min_score = params.min_score;
  if (params.max_score !== undefined) queryParams.max_score = params.max_score;
  if (params.grade) queryParams.grade = params.grade;
  if (params.limit) queryParams.limit = params.limit;
  if (params.offset) queryParams.offset = params.offset;

  const response = await fetch(
    `${process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001'}/api/data/quality-report?${new URLSearchParams(queryParams).toString()}`
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '查询失败');
  }

  return formatQualityReport(data.data);
}

/**
 * 查询每日统计
 */
async function fetchQualityStats(params: DataQualityReportParams): Promise<any> {
  const queryParams: Record<string, any> = {};

  if (params.symbol) queryParams.symbol = params.symbol;
  if (params.start_date) queryParams.start_date = params.start_date;
  if (params.end_date) queryParams.end_date = params.end_date;
  if (params.limit) queryParams.limit = params.limit;

  const response = await fetch(
    `${process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001'}/api/data/quality-stats?${new URLSearchParams(queryParams).toString()}`
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '查询失败');
  }

  return formatQualityStats(data.data);
}

/**
 * 查询质量摘要
 */
async function fetchQualitySummary(params: DataQualityReportParams): Promise<any> {
  const days = params.days || 7;

  const response = await fetch(
    `${process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001'}/api/data/quality-summary?days=${days}`
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '查询失败');
  }

  return formatQualitySummary(data.data);
}

/**
 * 查询质量趋势
 */
async function fetchQualityTrend(params: DataQualityReportParams): Promise<any> {
  const queryParams: Record<string, any> = {
    days: params.days || 30,
  };

  if (params.symbol) queryParams.symbol = params.symbol;

  const response = await fetch(
    `${process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001'}/api/data/quality-trend?${new URLSearchParams(queryParams).toString()}`
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }

  const data = await response.json();

  if (!data.success) {
    throw new Error(data.error || '查询失败');
  }

  return formatQualityTrend(data.data);
}

/**
 * 格式化质量报告
 */
function formatQualityReport(data: any): string {
  const { records, total, filters } = data;

  const lines: string[] = [];

  lines.push('📊 数据质量报告');
  lines.push('');

  // 筛选条件
  const activeFilters = Object.entries(filters)
    .filter(([_, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${key}=${value}`);

  if (activeFilters.length > 0) {
    lines.push('筛选条件: ' + activeFilters.join(', '));
    lines.push('');
  }

  lines.push(`共找到 ${total} 条记录`);
  lines.push('');

  // 记录列表
  if (records.length === 0) {
    lines.push('暂无数据');
  } else {
    records.slice(0, 20).forEach((record: any, idx: number) => {
      lines.push(`${idx + 1}. ${record.symbol} [${record.period}] - ${record.grade}`);
      lines.push(`   评分: ${record.overall_score.toFixed(1)}% (完整性${record.completeness_score.toFixed(1)}% 一致性${record.consistency_score.toFixed(1)}% 准确性${record.accuracy_score.toFixed(1)}%)`);
      lines.push(`   数据: ${record.original_count}条 → ${record.cleaned_count}条 (移除${record.removed_count} 修复${record.fixed_count})`);
      lines.push(`   问题: 错误${record.error_count}个 警告${record.warning_count}个`);
      lines.push(`   时间: ${record.created_at}`);
      lines.push('');
    });

    if (records.length > 20) {
      lines.push(`... 还有 ${records.length - 20} 条记录`);
    }
  }

  return lines.join('\n');
}

/**
 * 格式化统计数据
 */
function formatQualityStats(data: any): string {
  const { stats, symbol } = data;

  const lines: string[] = [];

  lines.push('📈 数据质量统计');
  lines.push('');

  if (symbol) {
    lines.push(`股票: ${symbol}`);
    lines.push('');
  } else {
    lines.push('范围: 全局统计');
    lines.push('');
  }

  if (stats.length === 0) {
    lines.push('暂无统计数据');
  } else {
    stats.forEach((stat: any) => {
      lines.push(`日期: ${stat.date}`);
      lines.push(`  请求: ${stat.total_requests}次, 数据量: ${stat.total_records}条`);
      lines.push(`  平均评分: ${stat.avg_overall?.toFixed(1) || 'N/A'}%`);
      lines.push(`  问题: 错误${stat.total_errors}个, 警告${stat.total_warnings}个`);
      lines.push(`  清洗: 移除${stat.total_removed}条, 修复${stat.total_fixed}条`);

      const dist = stat.grade_distribution;
      if (dist) {
        const distStr = Object.entries(dist)
          .filter(([_, count]) => (count as number) > 0)
          .map(([grade, count]) => `${grade}:${count}`)
          .join(', ');
        lines.push(`  评级分布: ${distStr || '无'}`);
      }

      lines.push('');
    });
  }

  return lines.join('\n');
}

/**
 * 格式化质量摘要
 */
function formatQualitySummary(data: any): string {
  const { total_checks, avg_score, grade_distribution, top_issues, period } = data;

  const lines: string[] = [];

  lines.push('🎯 数据质量摘要');
  lines.push('');
  lines.push(`统计期间: ${period}`);
  lines.push(`检查次数: ${total_checks}`);
  lines.push(`平均评分: ${avg_score}%`);
  lines.push('');

  // 评级分布
  lines.push('评级分布:');
  Object.entries(grade_distribution).forEach(([grade, count]) => {
    const percentage = total_checks > 0 ? ((count as number) / total_checks * 100).toFixed(1) : '0.0';
    lines.push(`  ${grade}: ${count} (${percentage}%)`);
  });
  lines.push('');

  // 高频问题
  if (top_issues && top_issues.length > 0) {
    lines.push('高频问题 (Top 5):');
    top_issues.forEach((issue: any, idx: number) => {
      lines.push(`  ${idx + 1}. ${issue.type}: ${issue.count}次`);
    });
  } else {
    lines.push('✓ 无常见问题');
  }

  return lines.join('\n');
}

/**
 * 格式化质量趋势
 */
function formatQualityTrend(data: any): string {
  const { dates, scores, error_counts, warning_counts, symbol } = data;

  const lines: string[] = [];

  lines.push('📉 数据质量趋势');
  lines.push('');

  if (symbol) {
    lines.push(`股票: ${symbol}`);
    lines.push('');
  }

  if (dates.length === 0) {
    lines.push('暂无趋势数据');
  } else {
    lines.push(`时间范围: ${dates[0]} ~ ${dates[dates.length - 1]}`);
    lines.push('');

    // 简单的文本图表
    dates.forEach((date: string, idx: number) => {
      const score = scores[idx]?.toFixed(1) || 'N/A';
      const errors = error_counts[idx] || 0;
      const warnings = warning_counts[idx] || 0;

      // 简单的条形图
      const barLength = Math.round((scores[idx] || 0) / 5);
      const bar = '█'.repeat(barLength);

      lines.push(`${date}: ${bar} ${score}% (E:${errors} W:${warnings})`);
    });
  }

  return lines.join('\n');
}
