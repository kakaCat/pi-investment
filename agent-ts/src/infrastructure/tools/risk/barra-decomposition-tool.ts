/**
 * Risk Barra Decomposition Tool - Barra风险分解工具
 *
 * 基于Barra风险模型进行投资组合风险分解分析。
 *
 * 【功能】
 * - 总风险分解（因子风险 + 特质风险）
 * - 行业因子暴露分析
 * - 风格因子暴露分析（规模、价值、成长、动量等）
 * - 边际风险贡献（Marginal VaR）
 * - 风险归因（哪些股票贡献了多少风险）
 *
 * 【应用场景】
 * - 风险管理：识别风险集中度
 * - 组合优化：调整高风险持仓
 * - 风险预算：分配各因子风险
 * - 压力测试：评估极端情况影响
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface BarraDecompositionParams {
  portfolio: string[];
  weights?: number[];
  date?: string;
}

interface RiskContribution {
  symbol: string;
  weight: number;
  marginal_var: number;
  risk_contribution: number;
  risk_percentage: number;
}

interface FactorRisk {
  factor_name: string;
  exposure: number;
  risk_contribution: number;
}

interface BarraResult {
  total_risk?: number;
  factor_risk?: number;
  specific_risk?: number;
  industry_exposure?: Record<string, number>;
  style_exposure?: Record<string, number>;
  risk_contributions?: RiskContribution[];
  factor_risks?: FactorRisk[];
  [key: string]: any;
}

export const riskBarraDecompositionTool: ToolDefinition = {
  name: "risk_barra_decomposition",
  label: "Barra风险分解分析",
  description:
    "使用Barra风险模型对投资组合进行风险分解分析。" +
    "将总风险分解为因子风险（系统性）和特质风险（个股），" +
    "识别行业和风格因子暴露，计算每只股票的边际风险贡献。" +
    "适用场景：风险管理、组合优化、风险预算、压力测试。",

  parameters: Type.Object({
    portfolio: Type.Array(Type.String(), {
      description: "投资组合股票代码列表。例如：[\"600519.SH\", \"000858.SZ\", \"000001.SZ\"]"
    }),
    weights: Type.Optional(
      Type.Array(Type.Number(), {
        description: "各股票权重，与portfolio对应。不传则等权。权重之和必须为1.0"
      })
    ),
    date: Type.Optional(
      Type.String({
        description: "分析日期，格式：YYYY-MM-DD。不传则使用最新交易日",
        pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      })
    )
  }),

  execute: async (_toolCallId: string, params: BarraDecompositionParams) => {
    try {
      const { portfolio, weights, date } = params;

      // 参数验证
      if (portfolio.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: "❌ 投资组合不能为空"
          }],
          details: null
        };
      }

      if (weights && weights.length !== portfolio.length) {
        return {
          content: [{
            type: "text" as const,
            text: "❌ 权重数组长度必须与股票数量一致"
          }],
          details: null
        };
      }

      if (weights) {
        const sum = weights.reduce((a, b) => a + b, 0);
        if (Math.abs(sum - 1.0) > 0.01) {
          return {
            content: [{
              type: "text" as const,
              text: `❌ 权重之和必须为1.0（当前：${sum.toFixed(4)}）`
            }],
            details: null
          };
        }
      }

      // 调用 quantsys-v2 API
      const result = await runQuantV2("factor.barra", {
        portfolio,
        weights,
        date
      });

      if (!result.ok) {
        throw new Error((result as any).error || "Barra风险分解失败");
      }

      // 格式化输出
      const formattedOutput = formatBarraResult(
        (result as any).data as BarraResult,
        portfolio,
        weights
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
          text: `❌ Barra风险分解失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化Barra风险分解结果
 */
function formatBarraResult(
  data: BarraResult,
  portfolio: string[],
  weights?: number[]
): string {
  if (!data) {
    return "❌ 未获取到Barra风险分解数据";
  }

  let output = "📊 **Barra风险分解分析**\n\n";

  // 组合信息
  output += `### 投资组合\n\n`;
  output += `- **股票数量**：${portfolio.length}只\n`;
  output += `- **股票列表**：${portfolio.join(", ")}\n`;

  if (weights) {
    const weightStr = weights.map((w, i) => `${portfolio[i]}(${(w * 100).toFixed(1)}%)`).join(", ");
    output += `- **权重分配**：${weightStr}\n`;
  } else {
    output += `- **权重分配**：等权配置\n`;
  }

  output += "\n";

  // 总体风险分解
  if (data.total_risk !== undefined) {
    output += `### 📈 总体风险分解\n\n`;
    const totalRisk = (data.total_risk * 100).toFixed(2);
    output += `- **总风险（年化波动率）**：${totalRisk}%\n`;

    if (data.factor_risk !== undefined) {
      const factorRisk = (data.factor_risk * 100).toFixed(2);
      const factorPct = ((data.factor_risk / data.total_risk) * 100).toFixed(1);
      output += `- **因子风险（系统性）**：${factorRisk}% (${factorPct}%)\n`;
    }

    if (data.specific_risk !== undefined) {
      const specificRisk = (data.specific_risk * 100).toFixed(2);
      const specificPct = ((data.specific_risk / data.total_risk) * 100).toFixed(1);
      output += `- **特质风险（个股）**：${specificRisk}% (${specificPct}%)\n`;
    }

    output += "\n";

    // 风险解读
    if (data.factor_risk && data.specific_risk && data.total_risk) {
      const factorRatio = data.factor_risk / data.total_risk;
      if (factorRatio > 0.7) {
        output += `💡 **风险特征**：因子风险占比高，组合主要受市场系统性因素影响\n\n`;
      } else if (factorRatio < 0.4) {
        output += `💡 **风险特征**：特质风险占比高，组合受个股因素影响较大，分散度不足\n\n`;
      } else {
        output += `💡 **风险特征**：因子风险和特质风险较为均衡\n\n`;
      }
    }
  }

  // 行业因子暴露
  if (data.industry_exposure && Object.keys(data.industry_exposure).length > 0) {
    output += `### 🏭 行业因子暴露\n\n`;
    output += "| 行业 | 暴露比例 | 风险评估 |\n";
    output += "|------|----------|----------|\n";

    const industries = Object.entries(data.industry_exposure)
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, 10); // 显示前10个

    for (const [industry, exposure] of industries) {
      const expPct = (exposure * 100).toFixed(1);
      const riskLevel = getRiskLevel(exposure);
      output += `| ${industry} | ${expPct}% | ${riskLevel} |\n`;
    }

    output += "\n";

    // 行业集中度分析
    const maxExposure = Math.max(...Object.values(data.industry_exposure));
    if (maxExposure > 0.3) {
      const topIndustry = Object.entries(data.industry_exposure)
        .find(([_, exp]) => exp === maxExposure)?.[0];
      output += `⚠️ **行业集中度风险**：${topIndustry} 行业暴露过高（${(maxExposure * 100).toFixed(1)}%），建议分散配置\n\n`;
    }
  }

  // 风格因子暴露
  if (data.style_exposure && Object.keys(data.style_exposure).length > 0) {
    output += `### 🎨 风格因子暴露\n\n`;
    output += "| 风格因子 | 暴露值 | 风格特征 |\n";
    output += "|----------|--------|----------|\n";

    const styleNames: Record<string, string> = {
      "size": "规模",
      "value": "价值",
      "growth": "成长",
      "momentum": "动量",
      "volatility": "波动率",
      "liquidity": "流动性",
      "leverage": "杠杆"
    };

    for (const [style, exposure] of Object.entries(data.style_exposure)) {
      const styleName = styleNames[style] || style;
      const expValue = exposure.toFixed(3);
      const characteristic = interpretStyleExposure(style, exposure);
      output += `| ${styleName} | ${expValue} | ${characteristic} |\n`;
    }

    output += "\n";
  }

  // 个股风险贡献
  if (data.risk_contributions && data.risk_contributions.length > 0) {
    output += `### 💰 个股风险贡献\n\n`;
    output += "| 股票 | 权重 | 边际VaR | 风险贡献 | 占比 |\n";
    output += "|------|------|---------|----------|------|\n";

    const contributions = data.risk_contributions
      .sort((a, b) => b.risk_contribution - a.risk_contribution);

    for (const contrib of contributions) {
      const weight = (contrib.weight * 100).toFixed(1);
      const marginalVar = (contrib.marginal_var * 100).toFixed(2);
      const riskContrib = (contrib.risk_contribution * 100).toFixed(2);
      const riskPct = (contrib.risk_percentage * 100).toFixed(1);
      output += `| ${contrib.symbol} | ${weight}% | ${marginalVar}% | ${riskContrib}% | ${riskPct}% |\n`;
    }

    output += "\n";

    // 风险集中度分析
    const topRiskContributor = contributions[0];
    if (topRiskContributor.risk_percentage > 0.4) {
      output += `⚠️ **风险集中度警告**：${topRiskContributor.symbol} 贡献了${(topRiskContributor.risk_percentage * 100).toFixed(1)}%的风险，建议降低仓位\n\n`;
    }
  }

  // 因子风险贡献
  if (data.factor_risks && data.factor_risks.length > 0) {
    output += `### 📊 因子风险贡献\n\n`;
    output += "| 因子 | 暴露值 | 风险贡献 |\n";
    output += "|------|--------|----------|\n";

    const factorRisks = data.factor_risks
      .sort((a, b) => Math.abs(b.risk_contribution) - Math.abs(a.risk_contribution))
      .slice(0, 10);

    for (const factor of factorRisks) {
      const exposure = factor.exposure.toFixed(3);
      const riskContrib = (factor.risk_contribution * 100).toFixed(2);
      output += `| ${factor.factor_name} | ${exposure} | ${riskContrib}% |\n`;
    }

    output += "\n";
  }

  // 风险管理建议
  output += generateRiskManagementAdvice(data, portfolio);

  return output;
}

/**
 * 获取风险等级
 */
function getRiskLevel(exposure: number): string {
  const absExp = Math.abs(exposure);
  if (absExp > 0.3) return "🔴 高风险";
  if (absExp > 0.2) return "🟡 中风险";
  if (absExp > 0.1) return "🟢 低风险";
  return "⚪ 极低";
}

/**
 * 解读风格因子暴露
 */
function interpretStyleExposure(style: string, exposure: number): string {
  const interpretations: Record<string, { positive: string; negative: string }> = {
    "size": {
      positive: "偏向小盘股",
      negative: "偏向大盘股"
    },
    "value": {
      positive: "偏向价值股",
      negative: "偏向成长股"
    },
    "growth": {
      positive: "偏向高成长",
      negative: "偏向低成长"
    },
    "momentum": {
      positive: "追涨动量",
      negative: "逆势反转"
    },
    "volatility": {
      positive: "高波动性",
      negative: "低波动性"
    },
    "liquidity": {
      positive: "高流动性",
      negative: "低流动性"
    },
    "leverage": {
      positive: "高杠杆",
      negative: "低杠杆"
    }
  };

  const interp = interpretations[style];
  if (!interp) return exposure > 0 ? "正暴露" : "负暴露";

  if (Math.abs(exposure) < 0.1) return "中性";
  return exposure > 0 ? interp.positive : interp.negative;
}

/**
 * 生成风险管理建议
 */
function generateRiskManagementAdvice(data: BarraResult, portfolio: string[]): string {
  let output = "### 💡 风险管理建议\n\n";

  const advice: string[] = [];

  // 总风险分析
  if (data.total_risk !== undefined) {
    if (data.total_risk > 0.25) {
      advice.push("⚠️ **高风险组合**：年化波动率超过25%，建议降低仓位或增加防御性持仓");
    } else if (data.total_risk < 0.10) {
      advice.push("🛡️ **低风险组合**：年化波动率较低，适合稳健投资者");
    }
  }

  // 因子风险vs特质风险
  if (data.factor_risk && data.specific_risk && data.total_risk) {
    const specificRatio = data.specific_risk / data.total_risk;
    if (specificRatio > 0.6) {
      advice.push("📊 **分散度不足**：特质风险占比过高，建议增加持仓数量以分散风险");
    }
  }

  // 行业集中度
  if ((data as any).industry_exposure) {
    const maxIndustryExp = Math.max(...Object.values(data.industry_exposure));
    if (maxIndustryExp > 0.4) {
      advice.push("🏭 **行业集中度高**：单一行业暴露超过40%，建议跨行业配置");
    }
  }

  // 个股风险贡献
  if (data.risk_contributions && data.risk_contributions.length > 0) {
    const topContributor = data.risk_contributions
      .sort((a, b) => b.risk_contribution - a.risk_contribution)[0];

    if (topContributor.risk_percentage > 0.3) {
      advice.push(`💰 **个股风险集中**：${topContributor.symbol} 贡献了${(topContributor.risk_percentage * 100).toFixed(1)}%的风险，考虑降低权重`);
    }
  }

  // 优化建议
  if (portfolio.length < 10) {
    advice.push("📈 **增加持仓数量**：当前持仓较少，建议增加至10-15只股票以优化分散效果");
  }

  if (advice.length === 0) {
    advice.push("✅ 组合风险结构合理，各项指标均在正常范围内");
  }

  output += advice.map(s => `- ${s}`).join("\n");
  output += "\n\n";

  // 风险提示
  output += "⚠️ **风险提示**：Barra风险分解基于历史数据和统计模型，不能完全预测未来风险。投资需谨慎。\n";

  return output;
}
