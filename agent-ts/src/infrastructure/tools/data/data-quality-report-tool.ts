/**
 * Data Quality Report Tool - 数据质量监控工具
 *
 * 监控和报告数据质量状况：
 * - 数据完整性检查
 * - 异常值检测
 * - 数据质量评分
 * - 质量趋势分析
 *
 * 应用场景：
 * - 数据可靠性保障
 * - 异常数据识别
 * - 数据清洗指导
 * - 数据源质量对比
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface DataQualityParams {
  action: "report" | "stats" | "summary" | "trend";
  symbol?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  min_score?: number;
  max_score?: number;
  grade?: string;
}

interface QualityRecord {
  symbol: string;
  date: string;
  score: number;
  grade: string;
  issues: string[];
  completeness: number;
  accuracy: number;
  consistency: number;
}

interface QualityStats {
  total_records: number;
  avg_score: number;
  grade_distribution: Record<string, number>;
  common_issues: Array<{ issue: string; count: number }>;
}

interface DataQualityResult {
  records?: QualityRecord[];
  stats?: QualityStats;
  summary?: {
    overall_score: number;
    overall_grade: string;
    total_symbols: number;
    total_days: number;
  };
  trend?: Array<{
    date: string;
    avg_score: number;
    record_count: number;
  }>;
  [key: string]: any;
}

export const dataQualityReportTool: ToolDefinition = {
  name: "data_quality_report",
  label: "数据质量监控",
  description:
    "监控和报告数据质量状况，包括完整性、准确性、一致性检查。" +
    "支持查询质量报告、统计信息、趋势分析。" +
    "适用场景：数据可靠性保障、异常识别、数据清洗指导。",

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("report"),
      Type.Literal("stats"),
      Type.Literal("summary"),
      Type.Literal("trend")
    ], {
      description:
        "操作类型。" +
        "report: 查询质量报告（详细记录）；" +
        "stats: 查询统计信息（汇总数据）；" +
        "summary: 查询概要信息（总体评价）；" +
        "trend: 查询趋势分析（时间序列）"
    }),
    symbol: Type.Optional(Type.String({
      description: "股票代码。不提供则查询全部股票"
    })),
    start_date: Type.Optional(Type.String({
      description: "开始日期，格式：YYYY-MM-DD",
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
    })),
    end_date: Type.Optional(Type.String({
      description: "结束日期，格式：YYYY-MM-DD",
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
    })),
    limit: Type.Optional(Type.Integer({
      description: "返回记录数量。默认：100",
      minimum: 1,
      maximum: 1000
    })),
    min_score: Type.Optional(Type.Number({
      description: "最低质量评分（0-100）",
      minimum: 0,
      maximum: 100
    })),
    max_score: Type.Optional(Type.Number({
      description: "最高质量评分（0-100）",
      minimum: 0,
      maximum: 100
    })),
    grade: Type.Optional(Type.String({
      description: "质量评级过滤：A+, A, B, C, D"
    }))
  }),

  execute: async (_toolCallId, params: DataQualityParams) => {
    try {
      const { action, ...queryParams } = params;

      // 构建API命令
      const commandMap: Record<string, string> = {
        "report": "data.quality-report",
        "stats": "data.quality-stats",
        "summary": "data.quality-summary",
        "trend": "data.quality-trend"
      };

      const command = commandMap[action];
      if (!command) {
        throw new Error(`未知的操作类型: ${action}`);
      }

      // 调用 quantsys-v2 API
      const result = await runQuantV2(command, queryParams);

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "数据质量查询失败";
        throw new Error(errorMsg);
      }

      // 格式化输出
      const formattedOutput = formatDataQualityResult(
        action,
        (result as any).data as DataQualityResult,
        params
      );

      return {
        content: [{
          type: "text" as const,
          text: formattedOutput
        }],
        details: (result as any).data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 数据质量查询失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化数据质量结果
 */
function formatDataQualityResult(
  action: string,
  data: DataQualityResult,
  params: DataQualityParams
): string {
  if (!data) {
    return "❌ 未获取到数据质量信息";
  }

  let output = "📊 **数据质量监控报告**\n\n";

  // 查询条件
  output += `### 查询条件\n\n`;
  output += `- **操作类型**：${getActionName(action)}\n`;
  if (params.symbol) {
    output += `- **股票代码**：${params.symbol}\n`;
  }
  if (params.start_date || params.end_date) {
    output += `- **时间范围**：${params.start_date || '不限'} 至 ${params.end_date || '不限'}\n`;
  }
  output += "\n";

  // 根据操作类型格式化
  if (action === "report" && data.records) {
    output += formatQualityReport(data.records, params);
  } else if (action === "stats" && data.stats) {
    output += formatQualityStats(data.stats);
  } else if (action === "summary" && data.summary) {
    output += formatQualitySummary(data.summary);
  } else if (action === "trend" && data.trend) {
    output += formatQualityTrend(data.trend);
  }

  return output;
}

/**
 * 格式化质量报告
 */
function formatQualityReport(records: QualityRecord[], params: DataQualityParams): string {
  let output = `### 📋 质量报告\n\n`;

  if (records.length === 0) {
    return output + "暂无符合条件的质量记录\n\n";
  }

  output += `**记录数量**：${records.length}条\n\n`;

  // 显示记录表格
  output += "| 股票 | 日期 | 评分 | 等级 | 完整性 | 准确性 | 一致性 | 问题数 |\n";
  output += "|------|------|------|------|--------|--------|--------|--------|\n";

  const displayRecords = records.slice(0, 20); // 最多显示20条
  for (const record of displayRecords) {
    const gradeEmoji = getGradeEmoji(record.grade);
    const completeness = (record.completeness * 100).toFixed(0);
    const accuracy = (record.accuracy * 100).toFixed(0);
    const consistency = (record.consistency * 100).toFixed(0);
    const issueCount = record.issues ? record.issues.length : 0;

    output += `| ${record.symbol} | ${record.date} | ${record.score.toFixed(1)} | ${gradeEmoji} ${record.grade} | ${completeness}% | ${accuracy}% | ${consistency}% | ${issueCount} |\n`;
  }

  if (records.length > 20) {
    output += `\n*（仅显示前20条，共${records.length}条记录）*\n`;
  }

  output += "\n";

  // 显示低质量数据的详细问题
  const lowQualityRecords = records.filter(r => r.score < 70 && r.issues && r.issues.length > 0);
  if (lowQualityRecords.length > 0) {
    output += `### ⚠️ 数据质量问题（评分<70）\n\n`;

    for (const record of lowQualityRecords.slice(0, 5)) {
      output += `**${record.symbol} (${record.date})**：评分 ${record.score.toFixed(1)}\n`;
      for (const issue of record.issues) {
        output += `- ${issue}\n`;
      }
      output += "\n";
    }
  }

  return output;
}

/**
 * 格式化质量统计
 */
function formatQualityStats(stats: QualityStats): string {
  let output = `### 📊 质量统计\n\n`;

  output += `**总记录数**：${stats.total_records}条\n`;
  output += `**平均评分**：${stats.avg_score.toFixed(1)}分\n\n`;

  // 评级分布
  if (stats.grade_distribution) {
    output += `**评级分布**：\n\n`;
    output += "| 评级 | 数量 | 占比 |\n";
    output += "|------|------|------|\n";

    const grades = ['A+', 'A', 'B', 'C', 'D'];
    for (const grade of grades) {
      const count = stats.grade_distribution[grade] || 0;
      const percentage = stats.total_records > 0
        ? ((count / stats.total_records) * 100).toFixed(1)
        : '0.0';
      const emoji = getGradeEmoji(grade);

      output += `| ${emoji} ${grade} | ${count} | ${percentage}% |\n`;
    }

    output += "\n";
  }

  // 常见问题
  if (stats.common_issues && stats.common_issues.length > 0) {
    output += `### ⚠️ 常见数据问题（Top 10）\n\n`;
    output += "| 问题 | 出现次数 |\n";
    output += "|------|----------|\n";

    const topIssues = stats.common_issues.slice(0, 10);
    for (const issue of topIssues) {
      output += `| ${issue.issue} | ${issue.count} |\n`;
    }

    output += "\n";
  }

  return output;
}

/**
 * 格式化质量概要
 */
function formatQualitySummary(summary: any): string {
  let output = `### 🎯 质量概要\n\n`;

  if (summary.overall_score !== undefined) {
    const gradeEmoji = getGradeEmoji(summary.overall_grade);
    output += `**总体评分**：${summary.overall_score.toFixed(1)}分\n`;
    output += `**总体评级**：${gradeEmoji} ${summary.overall_grade}\n`;
  }

  if (summary.total_symbols !== undefined) {
    output += `**覆盖股票**：${summary.total_symbols}只\n`;
  }

  if (summary.total_days !== undefined) {
    output += `**覆盖天数**：${summary.total_days}天\n`;
  }

  output += "\n";

  // 质量判断
  if (summary.overall_score !== undefined) {
    const score = summary.overall_score;
    let assessment = "";

    if (score >= 90) {
      assessment = "✅ **数据质量优秀**：数据可靠性高，可放心使用";
    } else if (score >= 80) {
      assessment = "✅ **数据质量良好**：数据基本可靠，少量问题不影响使用";
    } else if (score >= 70) {
      assessment = "⚠️ **数据质量一般**：存在一些问题，建议检查后使用";
    } else if (score >= 60) {
      assessment = "⚠️ **数据质量较差**：问题较多，需要清洗后再使用";
    } else {
      assessment = "❌ **数据质量很差**：严重问题，不建议使用";
    }

    output += `${assessment}\n\n`;
  }

  return output;
}

/**
 * 格式化质量趋势
 */
function formatQualityTrend(trend: Array<{ date: string; avg_score: number; record_count: number }>): string {
  let output = `### 📈 质量趋势\n\n`;

  if (trend.length === 0) {
    return output + "暂无趋势数据\n\n";
  }

  output += `**数据点数**：${trend.length}个\n\n`;

  // 显示趋势表格
  output += "| 日期 | 平均评分 | 记录数 | 趋势 |\n";
  output += "|------|----------|--------|------|\n";

  const displayTrend = trend.slice(-15); // 显示最近15个数据点
  for (let i = 0; i < displayTrend.length; i++) {
    const point = displayTrend[i];
    let trendIcon = "➡️";

    // 计算趋势
    if (i > 0) {
      const prevScore = displayTrend[i - 1].avg_score;
      if (point.avg_score > prevScore + 1) {
        trendIcon = "📈";
      } else if (point.avg_score < prevScore - 1) {
        trendIcon = "📉";
      }
    }

    output += `| ${point.date} | ${point.avg_score.toFixed(1)} | ${point.record_count} | ${trendIcon} |\n`;
  }

  output += "\n";

  // 趋势分析
  if (trend.length >= 2) {
    const first = trend[0];
    const last = trend[trend.length - 1];
    const change = last.avg_score - first.avg_score;
    const changePercent = ((change / first.avg_score) * 100).toFixed(1);

    let trendDesc = "";
    if (change > 5) {
      trendDesc = `📈 **质量显著提升**：平均评分上升 ${change.toFixed(1)}分 (${changePercent}%)`;
    } else if (change > 2) {
      trendDesc = `📈 **质量稳步提升**：平均评分上升 ${change.toFixed(1)}分 (${changePercent}%)`;
    } else if (change < -5) {
      trendDesc = `📉 **质量显著下降**：平均评分下降 ${Math.abs(change).toFixed(1)}分 (${changePercent}%)`;
    } else if (change < -2) {
      trendDesc = `📉 **质量逐步下降**：平均评分下降 ${Math.abs(change).toFixed(1)}分 (${changePercent}%)`;
    } else {
      trendDesc = `➡️ **质量保持稳定**：平均评分变化不大`;
    }

    output += `${trendDesc}\n\n`;
  }

  return output;
}

/**
 * 获取操作名称
 */
function getActionName(action: string): string {
  const names: Record<string, string> = {
    "report": "质量报告",
    "stats": "统计信息",
    "summary": "概要信息",
    "trend": "趋势分析"
  };
  return names[action] || action;
}

/**
 * 获取评级表情
 */
function getGradeEmoji(grade: string): string {
  const emojiMap: Record<string, string> = {
    "A+": "🏆",
    "A": "✅",
    "B": "👍",
    "C": "⚠️",
    "D": "❌"
  };
  return emojiMap[grade] || "➖";
}
