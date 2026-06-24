/**
 * Data Fetch Macro Tool - L1 数据管道层
 *
 * 获取宏观经济数据，包括 GDP、CPI、PMI、利率、汇率等指标。
 *
 * 【支持的指标】
 * - gdp: GDP增长率
 * - cpi: 消费者物价指数
 * - ppi: 生产者物价指数
 * - pmi: 制造业采购经理指数
 * - m1: 货币供应M1
 * - m2: 货币供应M2
 * - interest_rate: 基准利率
 * - exchange_rate: 人民币汇率
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

interface MacroParams {
  indicators?: string[];
  start_date?: string;
  end_date?: string;
}

interface MacroDataPoint {
  date?: string;
  value?: number | string;
  // 后端返回中文字段
  日期?: string;
  今值?: number | null;
  前值?: number | null;
  预测值?: number | null;
  [key: string]: any;  // 允许其他字段（如 GDP 的季度、绝对值等）
}

interface MacroData {
  indicators?: Record<string, MacroDataPoint[]>;
  [key: string]: any;
}

export const dataFetchMacroTool: ToolDefinition = {
  name: "data_fetch_macro",
  label: "获取宏观经济数据",
  description:
    "获取宏观经济指标数据，包括 GDP、CPI、PPI、PMI、M1/M2、利率、汇率等。" +
    "支持单个或多个指标同时查询，返回时间序列数据。" +
    "适用场景：宏观经济分析、市场环境判断、货币政策研究。",

  parameters: Type.Object({
    indicators: Type.Optional(
      Type.Array(Type.String(), {
        description:
          "宏观指标列表。可选值：" +
          "gdp（GDP增长率）、cpi（消费者物价指数）、ppi（生产者物价指数）、" +
          "pmi（制造业PMI）、m1（货币供应M1）、m2（货币供应M2）、" +
          "interest_rate（利率）、exchange_rate（汇率）。" +
          "不传则返回所有可用指标。"
      })
    ),
    start_date: Type.Optional(
      Type.String({
        description: "开始日期，格式：YYYY-MM-DD。默认：近1年",
        pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      })
    ),
    end_date: Type.Optional(
      Type.String({
        description: "结束日期，格式：YYYY-MM-DD。默认：今天",
        pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      })
    )
  }),

  execute: async (_toolCallId, params: MacroParams) => {
    try {
      const { indicators, start_date, end_date } = params;

      // 调用 quantsys-v2 API
      const result = await runQuantV2("market.macro", {
        indicators,
        start_date,
        end_date
      });

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "获取宏观数据失败";
        throw new Error(errorMsg);
      }

      // 格式化输出并使用统一响应处理
      // Note: Backend returns { gdp: [...], cpi: [...] } directly, not wrapped in "indicators"
      const macroData = { indicators: (result as any).data } as MacroData;
      const formattedOutput = formatMacroData(macroData);

      return handleToolResponse({
        toolName: 'data_fetch_macro',
        data: { formattedText: formattedOutput, rawData: (result as any).data },
        formatter: (d) => d.formattedText,
        metadata: { indicators, start_date, end_date },
        threshold: 20 * 1024, // 20KB
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 获取宏观数据失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化宏观数据输出
 */
function formatMacroData(data: MacroData): string {
  if (!data || !data.indicators) {
    return "❌ 未获取到宏观数据";
  }

  const indicators = data.indicators;
  const indicatorKeys = Object.keys(indicators);

  if (indicatorKeys.length === 0) {
    return "❌ 没有可用的宏观指标数据";
  }

  let output = "📊 **宏观经济数据**\n\n";

  for (const indicator of indicatorKeys) {
    const values = indicators[indicator];

    output += `## ${getIndicatorName(indicator)}\n\n`;

    if (Array.isArray(values) && values.length > 0) {
      // 显示最近5条数据
      const recent = values.slice(-5);

      output += "| 日期 | 数值 |\n";
      output += "|------|------|\n";

      for (const item of recent) {
        // 后端返回中文字段：日期、今值
        const date = item['日期'] || item.date || 'N/A';
        const value = item['今值'] !== undefined && item['今值'] !== null ? item['今值'] : item.value;
        const formattedValue = value !== undefined && value !== null ? formatValue(indicator, value) : 'N/A';
        output += `| ${date} | ${formattedValue} |\n`;
      }

      // 添加趋势分析
      if (values.length >= 2) {
        const latest = values[values.length - 1];
        const previous = values[values.length - 2];
        const latestValue = latest['今值'] !== undefined && latest['今值'] !== null ? latest['今值'] : latest.value;
        const previousValue = previous['今值'] !== undefined && previous['今值'] !== null ? previous['今值'] : previous.value;

        if (latestValue !== undefined && previousValue !== undefined && latestValue !== null && previousValue !== null) {
          const trend = analyzeTrend(indicator, previousValue, latestValue);
          output += `\n**趋势**：${trend}\n`;
        }
      }

      output += "\n";
    } else {
      output += "暂无数据\n\n";
    }
  }

  return output;
}

/**
 * 获取指标中文名称和单位
 */
function getIndicatorName(indicator: string): string {
  const names: Record<string, string> = {
    gdp: "GDP增长率",
    cpi: "消费者物价指数（CPI）",
    ppi: "生产者物价指数（PPI）",
    pmi: "制造业采购经理指数（PMI）",
    m1: "货币供应M1",
    m2: "货币供应M2",
    interest_rate: "基准利率",
    exchange_rate: "人民币汇率（USD/CNY）"
  };

  return names[indicator] || indicator.toUpperCase();
}

/**
 * 格式化数值（添加单位）
 */
function formatValue(indicator: string, value: number | string): string {
  const numValue = typeof value === 'string' ? parseFloat(value) : value;

  if (isNaN(numValue)) {
    return String(value);
  }

  switch (indicator) {
    case 'gdp':
    case 'cpi':
    case 'ppi':
    case 'interest_rate':
      return `${numValue.toFixed(2)}%`;

    case 'pmi':
      return numValue.toFixed(1);

    case 'm1':
    case 'm2':
      return `${(numValue / 10000).toFixed(2)} 万亿元`;

    case 'exchange_rate':
      return numValue.toFixed(4);

    default:
      return numValue.toFixed(2);
  }
}

/**
 * 分析趋势
 */
function analyzeTrend(indicator: string, previous: number | string, latest: number | string): string {
  const prevNum = typeof previous === 'string' ? parseFloat(previous) : previous;
  const latestNum = typeof latest === 'string' ? parseFloat(latest) : latest;

  if (isNaN(prevNum) || isNaN(latestNum)) {
    return "数据不足";
  }

  const change = latestNum - prevNum;
  const changePercent = ((change / prevNum) * 100).toFixed(2);

  let arrow = "";
  let description = "";

  if (change > 0) {
    arrow = "📈";
    description = "上升";
  } else if (change < 0) {
    arrow = "📉";
    description = "下降";
  } else {
    arrow = "➡️";
    description = "持平";
  }

  // 特定指标的解读
  let interpretation = "";
  switch (indicator) {
    case 'gdp':
      interpretation = change > 0 ? "（经济增长加速）" : "（经济增长放缓）";
      break;
    case 'cpi':
    case 'ppi':
      if (latestNum > 3) {
        interpretation = "（通胀压力较大）";
      } else if (latestNum < 1) {
        interpretation = "（通缩风险）";
      }
      break;
    case 'pmi':
      if (latestNum > 50) {
        interpretation = "（制造业扩张）";
      } else if (latestNum < 50) {
        interpretation = "（制造业收缩）";
      } else {
        interpretation = "（制造业持平）";
      }
      break;
  }

  return `${arrow} ${description} ${changePercent}% ${interpretation}`;
}
