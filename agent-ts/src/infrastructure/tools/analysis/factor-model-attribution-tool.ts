/**
 * Factor Model Attribution Tool - 因子模型归因分析
 *
 * 支持多种因子模型：
 * - Fama-French 三因子模型（市场、规模、价值）
 * - Fama-French 五因子模型（+ 盈利、投资）
 * - Carhart 四因子模型（+ 动量）
 * - Barra 风险模型
 *
 * 用途：
 * - 绩效归因分析
 * - Alpha/Beta分解
 * - 风险因子暴露
 * - 超额收益来源分析
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface FactorAttributionParams {
  model: "fama_french_3" | "fama_french_5" | "carhart" | "barra";
  portfolio: string[];
  weights?: number[];
  start_date: string;
  end_date: string;
}

interface FactorExposure {
  factor_name: string;
  exposure: number;
  t_stat?: number;
  p_value?: number;
}

interface AttributionResult {
  alpha?: number;
  beta_mkt?: number;
  beta_smb?: number;
  beta_hml?: number;
  beta_rmw?: number;
  beta_cma?: number;
  beta_mom?: number;
  r_squared?: number;
  factors?: FactorExposure[];
  [key: string]: any;
}

export const factorModelAttributionTool: ToolDefinition = {
  name: "factor_model_attribution",
  label: "因子模型归因分析",
  description:
    "使用因子模型（Fama-French、Carhart、Barra）进行投资组合归因分析。" +
    "分解收益来源，识别Alpha和各因子的Beta暴露，评估风格偏好。" +
    "适用场景：绩效归因、风格分析、超额收益来源识别、投资策略评估。",

  parameters: Type.Object({
    model: Type.Union([
      Type.Literal("fama_french_3"),
      Type.Literal("fama_french_5"),
      Type.Literal("carhart"),
      Type.Literal("barra")
    ], {
      description:
        "因子模型类型。" +
        "fama_french_3: Fama-French三因子（市场、规模SMB、价值HML）；" +
        "fama_french_5: Fama-French五因子（+ 盈利RMW、投资CMA）；" +
        "carhart: Carhart四因子（Fama-French三因子 + 动量MOM）；" +
        "barra: Barra风险模型（行业因子 + 风格因子）"
    }),
    portfolio: Type.Array(Type.String(), {
      description: "投资组合股票代码列表。例如：[\"600519.SH\", \"000858.SZ\"]"
    }),
    weights: Type.Optional(
      Type.Array(Type.Number(), {
        description: "各股票权重，与portfolio对应。不传则等权。例如：[0.6, 0.4]"
      })
    ),
    start_date: Type.String({
      description: "开始日期，格式：YYYY-MM-DD",
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
    }),
    end_date: Type.String({
      description: "结束日期，格式：YYYY-MM-DD",
      pattern: "^\\d{4}-\\d{2}-\\d{2}$"
    })
  }),

  execute: async (_toolCallId, params: FactorAttributionParams) => {
    try {
      const { model, portfolio, weights, start_date, end_date } = params;

      // 参数验证
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
      const apiPath = getApiPath(model);
      const result = await runQuantV2(apiPath, {
        portfolio,
        weights,
        start_date,
        end_date
      });

      if (!result.ok) {
        throw new Error((result as any).error || "因子归因分析失败");
      }

      // 格式化输出
      const formattedOutput = formatAttributionResult(
        model,
        (result as any).data as AttributionResult,
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
          text: `❌ 因子归因分析失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 获取API路径
 */
function getApiPath(model: string): string {
  const pathMap: Record<string, string> = {
    "fama_french_3": "factor.fama_french_3",
    "fama_french_5": "factor.fama_french_5",
    "carhart": "factor.carhart",
    "barra": "factor.barra"
  };
  return pathMap[model] || "factor.fama_french_3";
}

/**
 * 格式化归因结果输出
 */
function formatAttributionResult(
  model: string,
  data: AttributionResult,
  portfolio: string[],
  weights?: number[]
): string {
  if (!data) {
    return "❌ 未获取到归因分析数据";
  }

  let output = "📊 **因子模型归因分析**\n\n";

  // 模型信息
  output += `### 模型信息\n\n`;
  output += `- **模型类型**：${getModelName(model)}\n`;
  output += `- **组合股票**：${portfolio.join(", ")}\n`;

  if (weights) {
    const weightStr = weights.map((w, i) => `${portfolio[i]}(${(w * 100).toFixed(1)}%)`).join(", ");
    output += `- **权重分配**：${weightStr}\n`;
  } else {
    output += `- **权重分配**：等权配置\n`;
  }

  output += "\n";

  // Alpha分析
  if (data.alpha !== undefined) {
    output += `### 🎯 Alpha分析\n\n`;
    const alphaPercent = (data.alpha * 100).toFixed(2);
    const alphaEmoji = data.alpha > 0 ? "✅" : (data.alpha < 0 ? "❌" : "➡️");
    output += `- **Alpha（超额收益）**：${alphaEmoji} ${alphaPercent}%\n`;

    if (data.alpha > 0.02) {
      output += `- **解读**：组合产生了显著正Alpha，说明选股能力优秀\n`;
    } else if (data.alpha < -0.02) {
      output += `- **解读**：组合产生了负Alpha，选股策略需要优化\n`;
    } else {
      output += `- **解读**：Alpha接近0，收益主要来自市场Beta\n`;
    }

    output += "\n";
  }

  // Beta因子暴露
  output += `### 📈 因子暴露\n\n`;
  output += formatFactorExposures(model, data);

  // R平方
  if (data.r_squared !== undefined) {
    output += `### 📐 模型拟合度\n\n`;
    const rSquaredPercent = (data.r_squared * 100).toFixed(1);
    output += `- **R²（决定系数）**：${rSquaredPercent}%\n`;

    if (data.r_squared > 0.8) {
      output += `- **解读**：模型拟合度很好，因子能很好地解释组合收益\n`;
    } else if (data.r_squared > 0.6) {
      output += `- **解读**：模型拟合度较好，因子能较好地解释组合收益\n`;
    } else {
      output += `- **解读**：模型拟合度一般，组合收益受其他因素影响较大\n`;
    }

    output += "\n";
  }

  // 投资建议
  output += generateInvestmentInsights(model, data);

  return output;
}

/**
 * 获取模型中文名称
 */
function getModelName(model: string): string {
  const nameMap: Record<string, string> = {
    "fama_french_3": "Fama-French 三因子模型",
    "fama_french_5": "Fama-French 五因子模型",
    "carhart": "Carhart 四因子模型",
    "barra": "Barra 风险模型"
  };
  return nameMap[model] || model;
}

/**
 * 格式化因子暴露
 */
function formatFactorExposures(model: string, data: AttributionResult): string {
  let output = "| 因子 | Beta | 解读 |\n";
  output += "|------|------|------|\n";

  // 市场因子
  if (data.beta_mkt !== undefined) {
    const betaMkt = data.beta_mkt.toFixed(2);
    const mktInterpret = interpretMarketBeta(data.beta_mkt);
    output += `| 市场因子（Mkt） | ${betaMkt} | ${mktInterpret} |\n`;
  }

  // 规模因子
  if (data.beta_smb !== undefined) {
    const betaSmb = data.beta_smb.toFixed(2);
    const smbInterpret = interpretSMB(data.beta_smb);
    output += `| 规模因子（SMB） | ${betaSmb} | ${smbInterpret} |\n`;
  }

  // 价值因子
  if (data.beta_hml !== undefined) {
    const betaHml = data.beta_hml.toFixed(2);
    const hmlInterpret = interpretHML(data.beta_hml);
    output += `| 价值因子（HML） | ${betaHml} | ${hmlInterpret} |\n`;
  }

  // 盈利因子（仅五因子）
  if (data.beta_rmw !== undefined) {
    const betaRmw = data.beta_rmw.toFixed(2);
    const rmwInterpret = interpretRMW(data.beta_rmw);
    output += `| 盈利因子（RMW） | ${betaRmw} | ${rmwInterpret} |\n`;
  }

  // 投资因子（仅五因子）
  if (data.beta_cma !== undefined) {
    const betaCma = data.beta_cma.toFixed(2);
    const cmaInterpret = interpretCMA(data.beta_cma);
    output += `| 投资因子（CMA） | ${betaCma} | ${cmaInterpret} |\n`;
  }

  // 动量因子（仅Carhart）
  if (data.beta_mom !== undefined) {
    const betaMom = data.beta_mom.toFixed(2);
    const momInterpret = interpretMOM(data.beta_mom);
    output += `| 动量因子（MOM） | ${betaMom} | ${momInterpret} |\n`;
  }

  output += "\n";

  // Barra模型的额外因子
  if (model === "barra" && data.factors && data.factors.length > 0) {
    output += "**风格因子暴露**：\n\n";
    output += "| 因子 | 暴露值 | 显著性 |\n";
    output += "|------|--------|--------|\n";

    for (const factor of data.factors) {
      const significance = getSignificance(factor.p_value);
      output += `| ${factor.factor_name} | ${factor.exposure.toFixed(3)} | ${significance} |\n`;
    }

    output += "\n";
  }

  return output;
}

/**
 * 解读市场Beta
 */
function interpretMarketBeta(beta: number): string {
  if (beta > 1.2) return "高风险高收益，波动性高于市场";
  if (beta > 0.8) return "与市场同步波动";
  if (beta > 0.5) return "防御性组合，波动性低于市场";
  return "与市场相关性弱";
}

/**
 * 解读规模因子（SMB）
 */
function interpretSMB(beta: number): string {
  if (beta > 0.3) return "明显偏向小盘股";
  if (beta > 0) return "略偏小盘股";
  if (beta > -0.3) return "略偏大盘股";
  return "明显偏向大盘股";
}

/**
 * 解读价值因子（HML）
 */
function interpretHML(beta: number): string {
  if (beta > 0.3) return "明显偏向价值股";
  if (beta > 0) return "略偏价值股";
  if (beta > -0.3) return "略偏成长股";
  return "明显偏向成长股";
}

/**
 * 解读盈利因子（RMW）
 */
function interpretRMW(beta: number): string {
  if (beta > 0.3) return "明显偏向高盈利股";
  if (beta > 0) return "略偏高盈利股";
  if (beta > -0.3) return "略偏低盈利股";
  return "明显偏向低盈利股";
}

/**
 * 解读投资因子（CMA）
 */
function interpretCMA(beta: number): string {
  if (beta > 0.3) return "明显偏向保守投资";
  if (beta > 0) return "略偏保守投资";
  if (beta > -0.3) return "略偏激进投资";
  return "明显偏向激进投资";
}

/**
 * 解读动量因子（MOM）
 */
function interpretMOM(beta: number): string {
  if (beta > 0.3) return "明显的动量效应，追涨策略";
  if (beta > 0) return "略有动量效应";
  if (beta > -0.3) return "略有反转效应";
  return "明显的反转效应，逆势策略";
}

/**
 * 获取显著性标记
 */
function getSignificance(pValue?: number): string {
  if (!pValue) return "-";
  if (pValue < 0.01) return "***（高度显著）";
  if (pValue < 0.05) return "**（显著）";
  if (pValue < 0.1) return "*（边际显著）";
  return "不显著";
}

/**
 * 生成投资建议
 */
function generateInvestmentInsights(model: string, data: AttributionResult): string {
  let output = "### 💡 投资洞察\n\n";

  const insights: string[] = [];

  // Alpha分析
  if (data.alpha !== undefined) {
    if (data.alpha > 0.02) {
      insights.push("✅ **优秀的选股能力**：组合产生了显著正Alpha，说明选股策略有效");
    } else if (data.alpha < -0.02) {
      insights.push("⚠️ **选股策略需优化**：组合产生负Alpha，建议重新审视选股逻辑");
    }
  }

  // 市场Beta分析
  if (data.beta_mkt !== undefined) {
    if (data.beta_mkt > 1.2) {
      insights.push("⚡ **高Beta组合**：适合牛市，但需注意熊市风险");
    } else if (data.beta_mkt < 0.8) {
      insights.push("🛡️ **防御性组合**：适合震荡市和熊市，但牛市弹性不足");
    }
  }

  // 规模因子分析
  if (data.beta_smb !== undefined) {
    if (Math.abs(data.beta_smb) > 0.3) {
      const preference = data.beta_smb > 0 ? "小盘股" : "大盘股";
      insights.push(`📊 **规模偏好明显**：组合明显偏向${preference}，注意风格轮动风险`);
    }
  }

  // 价值成长分析
  if (data.beta_hml !== undefined) {
    if (Math.abs(data.beta_hml) > 0.3) {
      const preference = data.beta_hml > 0 ? "价值股" : "成长股";
      insights.push(`💎 **风格偏好明显**：组合明显偏向${preference}，注意风格轮动`);
    }
  }

  // 动量分析（Carhart）
  if (data.beta_mom !== undefined) {
    if (Math.abs(data.beta_mom) > 0.3) {
      const strategy = data.beta_mom > 0 ? "追涨" : "逆势";
      insights.push(`🎯 **${strategy}策略特征**：注意市场趋势变化的风险`);
    }
  }

  // R²分析
  if (data.r_squared !== undefined && data.r_squared < 0.6) {
    insights.push("📐 **模型拟合度偏低**：组合收益受其他因素影响较大，建议增加因子或调整持仓");
  }

  if (insights.length === 0) {
    insights.push("组合因子暴露较为均衡，风格特征不明显");
  }

  output += insights.map(s => `- ${s}`).join("\n");
  output += "\n\n";

  // 风险提示
  output += "⚠️ **风险提示**：因子归因分析基于历史数据，不保证未来表现。投资需谨慎。\n";

  return output;
}
