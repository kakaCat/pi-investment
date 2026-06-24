/**
 * Factor Analyze Tool - L2 因子工厂层（v2 增强版）
 *
 * 分析因子的 IC、分层收益、换手率等专业指标
 *
 * 🆕 v2 增强：集成 alphalens-reloaded 专业因子分析
 * 🆕 集成统一响应处理系统：分析结果自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { analyzeFactors, generateFactorReport } from "../../adapters/quant/quant-v2-client.js";
import { formatFactorAnalysis, formatFactorReport } from "../../adapters/quant/formatters.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorAnalyzeParams {
  factors: string[];
  start_date: string;
  end_date: string;
  universe?: string[];
  use_alphalens?: boolean;
  generate_report?: boolean;
  output_dir?: string;
}

export const factorAnalyzeTool: ToolDefinition = {
  name: "factor_analyze",
  label: "因子分析（alphalens增强）",
  description:
    "L2 因子工厂工具：分析因子的有效性和稳定性（v2 增强版）。" +
    "\n\n💡 **核心功能**：" +
    "\n  • IC 分析（信息系数时间序列、t统计量、p值检验）" +
    "\n  • 分层收益分析（5分位数收益对比、多空价差）" +
    "\n  • 换手率分析（因子稳定性、自相关性）" +
    "\n  • 多周期对比（1日、5日、10日持有期）" +
    "\n\n🔬 **使用 alphalens-reloaded 专业分析库**（Quantopian标准）" +
    "\n\n📊 **适用场景**：" +
    "\n  • 评估新因子的预测能力" +
    "\n  • 多因子组合前的相关性检查" +
    "\n  • 因子有效性持续监控" +
    "\n\n📄 **HTML 报告**：" +
    "\n  • 设置 generate_report=true 生成完整 HTML 报告" +
    "\n  • 包含 IC 时间序列图、分层收益图、累计收益曲线等" +
    "\n  • 报告保存到 output_dir（默认 /tmp）" +
    "\n\n💾 分析结果自动保存到本地文件。",

  parameters: Type.Object({
    factors: Type.Array(
      Type.String(),
      {
        description: "要分析的因子列表（如 ['rsi', 'macd', 'roe']）"
      }
    ),
    start_date: Type.String({
      description: "开始日期，格式 YYYY-MM-DD（如 2024-01-01）"
    }),
    end_date: Type.String({
      description: "结束日期，格式 YYYY-MM-DD（如 2024-12-31）"
    }),
    universe: Type.Optional(
      Type.Array(
        Type.String(),
        {
          description: "股票池范围（可选），A股6位代码列表（如 ['600519', '000858']）。不提供则使用默认股票池（沪深300成分股前100只）"
        }
      )
    ),
    use_alphalens: Type.Optional(
      Type.Boolean({
        description: "是否使用 alphalens 专业分析（可选，默认 true）。设为 false 则使用基础分析（模拟数据）"
      })
    ),
    generate_report: Type.Optional(
      Type.Boolean({
        description: "是否生成 HTML 报告（可选，默认 false）。设为 true 时会生成包含图表的完整 HTML 报告"
      })
    ),
    output_dir: Type.Optional(
      Type.String({
        description: "HTML 报告保存目录（可选，默认 /tmp）。仅在 generate_report=true 时有效"
      })
    )
  }),

  execute: async (_toolCallId, params: FactorAnalyzeParams) => {
    const { factors, start_date, end_date, universe, use_alphalens = true, generate_report = false, output_dir } = params;

    try {
      // 如果需要生成报告，调用报告生成 API
      if (generate_report) {
        const reportResult = await generateFactorReport({
          factors,
          start_date,
          end_date,
          universe,
          output_dir
        });

        if (!reportResult.success) {
          return createErrorResponse(reportResult.error || "生成报告失败");
        }

        // 使用统一响应处理（报告生成结果）
        return handleToolResponse({
          toolName: 'factor_analyze_report',
          data: reportResult,
          formatter: formatFactorReport,
          metadata: {
            factor_count: factors.length,
            period: `${start_date} ~ ${end_date}`,
            universe_size: universe?.length || 'default',
            report_count: reportResult.reports?.length || 0,
            success_count: reportResult.success_count || 0
          },
          threshold: 30 * 1024, // 30KB，报告元数据较小
        });
      }

      // 否则，执行普通的因子分析
      // 调用 v2 API 分析因子
      const result = await analyzeFactors({
        factors,
        start_date,
        end_date,
        universe,
        use_alphalens
      });

      if (!(result as any).success) {
        return createErrorResponse((result as any).error || "未知错误");
      }

      // 使用统一响应处理（自动持久化）
      return handleToolResponse({
        toolName: 'factor_analyze',
        data: result,
        formatter: formatFactorAnalysis,
        metadata: {
          factor_count: factors.length,
          period: `${start_date} ~ ${end_date}`,
          universe_size: universe?.length || 'default',
          method: result.method || 'unknown',
          use_alphalens: use_alphalens
        },
        threshold: 50 * 1024, // 50KB，因子分析数据中等大小
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  }
};
