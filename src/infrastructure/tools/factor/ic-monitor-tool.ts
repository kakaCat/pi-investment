/**
 * Factor IC Monitor Tool - 因子IC时序监控
 *
 * 功能：监控因子IC随时间的变化，检测因子衰减
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorICMonitorParams {
  factor_name: string;
  symbols?: string[];
  start_date: string;
  end_date: string;
  rolling_window?: number;
  alert_threshold?: number;
}

export const factorICMonitorTool: ToolDefinition = {
  name: "factor_ic_monitor",
  label: "因子IC监控",
  description:
    "监控因子IC随时间的变化，检测因子衰减。" +
    "\n\n📈 **核心功能**：" +
    "\n  • 计算因子IC时间序列" +
    "\n  • 检测IC趋势（上升/下降/稳定）" +
    "\n  • 识别因子衰减期" +
    "\n  • 生成预警信号" +
    "\n\n📊 **监控指标**：" +
    "\n  • IC均值和标准差" +
    "\n  • IC正值比例（胜率）" +
    "\n  • 滚动IC趋势" +
    "\n  • 衰减速度" +
    "\n\n💡 **使用场景**：" +
    "\n  • 策略上线后持续监控因子有效性" +
    "\n  • 检测市场环境变化对因子的影响" +
    "\n  • 及时发现因子失效，调整策略" +
    "\n  • 定期生成因子健康报告" +
    "\n\n⚠️ **预警规则**：" +
    "\n  • IC连续N期为负 → 因子可能失效" +
    "\n  • IC标准差显著增加 → 因子不稳定" +
    "\n  • 滚动IC持续下降 → 因子衰减" +
    "\n  • IC均值低于阈值 → 因子质量下降",

  parameters: Type.Object({
    factor_name: Type.String({
      description: "要监控的因子名称（如 rsi14, momentum_20d）"
    }),
    symbols: Type.Optional(
      Type.Array(
        Type.String(),
        {
          description: "股票池范围（可选），A股6位代码列表。不提供则使用默认股票池"
        }
      )
    ),
    start_date: Type.String({
      description: "监控起始日期（YYYY-MM-DD格式）"
    }),
    end_date: Type.String({
      description: "监控结束日期（YYYY-MM-DD格式）"
    }),
    rolling_window: Type.Optional(
      Type.Number({
        description: "滚动窗口天数（可选，默认20）。用于计算滚动IC均值，检测趋势"
      })
    ),
    alert_threshold: Type.Optional(
      Type.Number({
        description: "IC预警阈值（可选，默认0.02）。低于此值时发出预警"
      })
    )
  }),

  execute: async (_toolCallId, params: FactorICMonitorParams) => {
    const {
      factor_name,
      symbols,
      start_date,
      end_date,
      rolling_window = 20,
      alert_threshold = 0.02
    } = params;

    try {
      // 调用 quantsys-v2 API
      const QUANTSYS_API_URL = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = `${QUANTSYS_API_URL}/api/analysis/factor-ic-monitor`;

      const requestBody = {
        factor_name,
        symbols,
        start_date,
        end_date,
        rolling_window,
        alert_threshold
      };

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`API 请求失败: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();

      if (!result.success) {
        throw new Error(result.error || '因子IC监控失败');
      }

      const data = result.data;

      // 提取关键指标
      const icStats = data.ic_statistics || {};
      const trend = data.trend || {};
      const alerts = data.alerts || [];
      const recentIC = data.recent_ic || [];

      // 格式化输出
      let outputText = `📈 因子IC监控报告\n\n`;
      outputText += `因子: ${factor_name}\n`;
      outputText += `监控期间: ${start_date} ~ ${end_date}\n`;
      outputText += `股票数量: ${data.n_stocks || 'N/A'}\n\n`;

      // IC统计
      outputText += `📊 **IC统计**:\n`;
      outputText += `  • 均值: ${icStats.mean?.toFixed(4) || 'N/A'}\n`;
      outputText += `  • 标准差: ${icStats.std?.toFixed(4) || 'N/A'}\n`;
      outputText += `  • 最大值: ${icStats.max?.toFixed(4) || 'N/A'}\n`;
      outputText += `  • 最小值: ${icStats.min?.toFixed(4) || 'N/A'}\n`;
      outputText += `  • 正值比例: ${((icStats.positive_ratio || 0) * 100).toFixed(1)}%\n`;
      outputText += `  • t统计量: ${icStats.t_stat?.toFixed(2) || 'N/A'}\n\n`;

      // 趋势分析
      if (trend.direction) {
        const trendEmoji = trend.direction === 'up' ? '📈' : trend.direction === 'down' ? '📉' : '➡️';
        outputText += `${trendEmoji} **趋势分析**:\n`;
        outputText += `  • 趋势方向: ${getTrendText(trend.direction)}\n`;
        outputText += `  • 趋势强度: ${trend.strength || 'N/A'}\n`;
        if (trend.slope) {
          outputText += `  • 变化率: ${(trend.slope * 100).toFixed(2)}%/天\n`;
        }
        outputText += `\n`;
      }

      // 预警信息
      if (alerts.length > 0) {
        outputText += `⚠️ **预警信号** (${alerts.length}个):\n`;
        alerts.forEach((alert: any) => {
          outputText += `  • ${alert.type}: ${alert.message}\n`;
        });
        outputText += `\n`;
      } else {
        outputText += `✅ 无预警信号，因子状态正常\n\n`;
      }

      // 最近表现
      if (recentIC.length > 0) {
        outputText += `📅 **最近表现** (最近${Math.min(5, recentIC.length)}期):\n`;
        recentIC.slice(-5).forEach((item: any) => {
          const icValue = item.ic.toFixed(4);
          const emoji = item.ic > 0 ? '✅' : '❌';
          outputText += `  ${emoji} ${item.date}: IC = ${icValue}\n`;
        });
        outputText += `\n`;
      }

      // 建议
      outputText += generateRecommendations(icStats, trend, alerts);

      return {
        content: [{
          type: "text" as const,
          text: outputText
        }],
        details: data
      };

    } catch (error) {
      return createErrorResponse(error);
    }
  }
};

/**
 * 获取趋势文本
 */
function getTrendText(direction: string): string {
  switch (direction) {
    case 'up': return '上升（因子增强）';
    case 'down': return '下降（因子衰减）';
    case 'stable': return '稳定';
    default: return '未知';
  }
}

/**
 * 生成建议
 */
function generateRecommendations(
  icStats: any,
  trend: any,
  alerts: any[]
): string {
  const recommendations: string[] = ['💡 **建议**:'];

  // 基于IC均值
  const icMean = icStats.mean || 0;
  if (icMean < 0.01) {
    recommendations.push('  • ⚠️ IC均值过低，建议停用该因子或重新训练');
  } else if (icMean > 0.05) {
    recommendations.push('  • ✅ IC均值较高，因子表现优秀，可继续使用');
  }

  // 基于趋势
  if (trend.direction === 'down') {
    recommendations.push('  • 📉 IC呈下降趋势，密切监控，考虑调整因子参数');
  } else if (trend.direction === 'up') {
    recommendations.push('  • 📈 IC呈上升趋势，因子适应性增强');
  }

  // 基于稳定性
  const icStd = icStats.std || 0;
  const icStdRatio = icMean !== 0 ? Math.abs(icStd / icMean) : Infinity;
  if (icStdRatio > 2) {
    recommendations.push('  • ⚠️ IC波动较大，因子不稳定，建议降低权重或组合使用');
  }

  // 基于预警
  if (alerts.length > 0) {
    recommendations.push('  • 🚨 存在预警信号，建议立即检查因子有效性');
  }

  // 如果一切正常
  if (recommendations.length === 1 && alerts.length === 0 && icMean > 0.02) {
    recommendations.push('  • ✅ 因子状态健康，继续监控即可');
  }

  return recommendations.join('\n');
}
