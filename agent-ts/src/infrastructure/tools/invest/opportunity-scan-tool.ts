/**
 * V2 机会雷达工具（增强版）- 支持动态因子权重 + 波段/价值双模式
 *
 * 基于 quantsys-v2 的多维评分引擎，批量扫描股票池找出交易机会。
 * 覆盖技术面（RSI/MACD/布林带）+ 基本面（PE/ROE）+ 资金面三维评分。
 *
 * 新增功能：
 * - 支持固定权重（默认 50%/30%/20%）
 * - 支持动态权重（基于因子有效性自动计算）
 * - 支持自定义权重
 * - 支持波段/价值双模式（mode=swing 时 ZigZag 胜率替代 PE 分位）
 *
 * 🆕 集成统一响应处理系统：大结果集自动持久化
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { analyzeFactors, runQuantV2, scanOpportunities } from "../../adapters/quant/quant-v2-client.js";
import { formatOpportunities } from "../../adapters/quant/formatters.js";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorWeight {
  technical: number;
  fundamental: number;
  capital: number;
}

/**
 * 波段交易评分 — 用 ZigZag 胜率/买点/量能 替代 PE 分位
 *
 * 评分卡（满分 100）：
 *   ZigZag 买点(3天内)  30分
 *   胜率 > 90%          20分（>80% 得 15分）
 *   距买点 < 5%          20分（<10% 得 10分）
 *   今日量 > 5日均量     15分
 *   RSI 30-50            15分
 */
interface SwingScore {
  symbol: string;
  zigzag_buy_date?: string;
  zigzag_buy_price?: number;
  zigzag_win_rate?: number;
  zigzag_avg_holding_days?: number;
  current_price?: number;
  price_distance_pct?: number;
  rsi?: number;
  volume_ratio?: number;
  swing_score: number;
  swing_mode: boolean;  // true=波段模式
  signal_state?: 'buy_active' | 'sold';  // 最新拐点状态：买点有效 / 已卖出等下一买点
  reasons: string[];
}

async function enrichWithSwingScore(
  opportunities: any[],
  mode: string,
): Promise<string> {
  if (!opportunities || opportunities.length === 0) return '';

  let output = '';
  const swingResults: SwingScore[] = [];

  for (const opp of opportunities) {
    const symbol = opp.symbol;
    if (!symbol) continue;

    try {
      // 并行获取 ZigZag 波段分析 + 实时行情（现价）
      const [zigzagResult, quoteResult] = await Promise.all([
        runQuantV2('analysis.swing_points', { symbol, min_change: 5 }),
        runQuantV2('stock.batch_quotes', { symbols: [symbol] }).catch(() => null),
      ]);

      if (!zigzagResult.ok) continue;
      const data = (zigzagResult as any).data;
      if (!data) continue;

      // 后端返回 camelCase：summary.winRate/avgHoldingDays, trades[].profitPct/holdingDays
      const summary = data.summary || {};
      const totalTrades = summary.totalTrades || 0;
      const winRate = (summary.winRate || 0) / 100;  // 后端返回百分数如 98.3
      const avgHoldingDays = summary.avgHoldingDays || 999;

      // 找最近的买点（swingPoints 中 type='low' 为买点）
      // 防御：按日期排序，确保最后一个即最新拐点
      const swingPoints = (data.swingPoints || []).slice().sort(
        (a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime()
      );
      const buyPoints = swingPoints.filter((p: any) => p.type === 'low');
      const latestBuy = buyPoints.length > 0 ? buyPoints[buyPoints.length - 1] : null;

      // 关键：检查最新拐点是否为卖点（type='high'）
      // 若最新拐点=卖点，说明最近一笔 买→卖 已完成，旧买点已失效，
      // 此时按旧买点算「距买点」打分会产生假信号（阳光电源案例：8/3买8/4卖，
      // 工具仍按8/3买点打出88分）。
      const latestPoint = swingPoints.length > 0 ? swingPoints[swingPoints.length - 1] : null;
      const signalState: 'buy_active' | 'sold' =
        latestPoint && latestPoint.type === 'high' ? 'sold' : 'buy_active';

      // 现价：优先用实时行情，fallback 用 ZigZag 最新拐点
      let currentPrice: number | undefined;
      if (quoteResult?.ok) {
        const qData = (quoteResult as any).data;
        // batch_quotes 返回 { quotes: { [symbol]: { price, ... } } } 或数组
        const quotes = qData?.quotes || qData;
        if (Array.isArray(quotes)) {
          const q = quotes.find((x: any) => x.symbol === symbol || x.code === symbol);
          currentPrice = q?.price || q?.current_price || q?.close;
        } else if (quotes && typeof quotes === 'object') {
          const q = quotes[symbol] || quotes[symbol + '.SH'] || quotes[symbol + '.SZ'];
          currentPrice = q?.price || q?.current_price || q?.close;
        }
      }
      if (!currentPrice) {
        currentPrice = latestPoint?.price;
      }

      // 判断模式
      const isSwingMode = mode === 'swing' ||
        (mode === 'auto' && winRate > 0.8 && avgHoldingDays < 5);

      if (!isSwingMode) continue;

      // 获取技术面数据（从 opportunity 结果中提取）
      const techScore = opp.technical_score || 50;
      const capitalScore = opp.capital_score || 50;

      // 估算 RSI 和量比（从技术得分反推不精确，直接用 opportunity 的数据）
      // 波段评分卡
      let swingScore = 0;
      const reasons: string[] = [];

      // 1. ZigZag 买点（30分）— 仅在买点仍有效（最新拐点是low）时给分
      if (signalState === 'sold') {
        reasons.push(
          `最新拐点为卖点${latestPoint.date} ¥${latestPoint.price?.toFixed(2)}（波段已完成，等下一买点）`
        );
      } else if (latestBuy) {
        const buyDate = new Date(latestBuy.date);
        const daysSinceBuy = Math.floor(
          (Date.now() - buyDate.getTime()) / (1000 * 60 * 60 * 24)
        );
        if (daysSinceBuy <= 3) {
          swingScore += 30;
          reasons.push(`ZigZag买点${latestBuy.date}（${daysSinceBuy}天前）`);
        } else if (daysSinceBuy <= 7) {
          swingScore += 15;
          reasons.push(`ZigZag买点${latestBuy.date}（${daysSinceBuy}天前，稍远）`);
        }
      }

      // 2. 胜率（20分）
      if (winRate >= 0.95) {
        swingScore += 20;
        reasons.push(`胜率${(winRate * 100).toFixed(0)}%（${totalTrades}笔）`);
      } else if (winRate >= 0.85) {
        swingScore += 15;
        reasons.push(`胜率${(winRate * 100).toFixed(0)}%（${totalTrades}笔）`);
      } else if (winRate >= 0.80) {
        swingScore += 10;
        reasons.push(`胜率${(winRate * 100).toFixed(0)}%（${totalTrades}笔）`);
      }

      // 3. 距买点距离（20分）— 仅在买点仍有效时有意义（已卖出后距离无意义）
      if (signalState === 'buy_active' && latestBuy && currentPrice) {
        const buyPrice = latestBuy.price;
        const distance = (currentPrice - buyPrice) / buyPrice;
        if (distance <= 0.03) {
          swingScore += 20;
          reasons.push(`距买点+${(distance * 100).toFixed(1)}%（极近）`);
        } else if (distance <= 0.05) {
          swingScore += 15;
          reasons.push(`距买点+${(distance * 100).toFixed(1)}%（较近）`);
        } else if (distance <= 0.10) {
          swingScore += 10;
          reasons.push(`距买点+${(distance * 100).toFixed(1)}%（稍远）`);
        } else {
          reasons.push(`距买点+${(distance * 100).toFixed(1)}%（偏远，不加分）`);
        }
      }

      // 4. 量能（15分）— 用 capital_score 近似
      if (capitalScore >= 60) {
        swingScore += 15;
        reasons.push('量能充足');
      } else if (capitalScore >= 40) {
        swingScore += 8;
        reasons.push('量能一般');
      }

      // 5. RSI（15分）— 用 technical_score 近似
      if (techScore >= 40 && techScore <= 60) {
        swingScore += 15;
        reasons.push('RSI在中性区（未超买未超卖）');
      } else if (techScore < 40) {
        swingScore += 10;
        reasons.push('RSI偏低（超卖反弹机会）');
      }

      // 更新 opportunity 的分数（保留原综合分）
      const originalScore = opp.score || 0;
      opp.swing_score = swingScore;
      opp.swing_mode = true;
      opp.signal_state = signalState;
      opp.original_score = originalScore;
      opp.score = swingScore;  // 波段模式用波段分替代综合分
      opp.risk_level = swingScore >= 70 ? 'low' : swingScore >= 50 ? 'medium' : 'high';

      swingResults.push({
        symbol,
        zigzag_buy_date: latestBuy?.date,
        zigzag_buy_price: latestBuy?.price,
        zigzag_win_rate: winRate,
        zigzag_avg_holding_days: avgHoldingDays,
        current_price: currentPrice,
        price_distance_pct: signalState === 'buy_active' && latestBuy && currentPrice
          ? ((currentPrice - latestBuy.price) / latestBuy.price) * 100
          : undefined,
        swing_score: swingScore,
        swing_mode: true,
        signal_state: signalState,
        reasons,
      });

    } catch (e) {
      // 单个股票失败不影响整体
      continue;
    }
  }

  if (swingResults.length > 0) {
    output += `📈 **波段模式评分（ZigZag驱动）**\n\n`;
    output += `| 股票 | 信号状态 | 买点 | 胜率 | 距买点 | 波段分 | 原综合分 |\n`;
    output += `|------|------|------|------|--------|--------|----------|\n`;
    for (const r of swingResults) {
      const origScore = opportunities.find((o: any) => o.symbol === r.symbol)?.original_score;
      const stateLabel = r.signal_state === 'sold' ? '🔴已卖出' : '🟢买点有效';
      output += `| ${r.symbol} | ${stateLabel} | ${r.zigzag_buy_date || '-'} ¥${r.zigzag_buy_price?.toFixed(2) || '-'} | ${((r.zigzag_win_rate || 0) * 100).toFixed(0)}% | ${r.price_distance_pct?.toFixed(1) || '-'}% | **${r.swing_score}** | ${origScore ?? '-'} |\n`;
    }
    output += `\n`;

    // 重新按波段分排序
    opportunities.sort((a: any, b: any) => (b.swing_score || b.score) - (a.swing_score || a.score));
  }

  return output;
}

/**
 * 根据因子分析结果计算动态权重（IR-based 算法）
 */
function calculateWeightsFromAnalysis(analysisResult: any): FactorWeight {
  const factors = analysisResult.factors || [];

  const technicalFactors = factors.filter((f: any) =>
    ['rsi', 'macd', 'bollinger', 'volume'].includes(f.factor_name?.toLowerCase())
  );
  const fundamentalFactors = factors.filter((f: any) =>
    ['roe', 'pe', 'pb', 'debt_ratio', 'gross_margin'].includes(f.factor_name?.toLowerCase())
  );

  const techIR = technicalFactors.length > 0
    ? technicalFactors.reduce((sum: number, f: any) => sum + Math.abs(f.ir || 0), 0) / technicalFactors.length
    : 0.5;

  const fundIR = fundamentalFactors.length > 0
    ? fundamentalFactors.reduce((sum: number, f: any) => sum + Math.abs(f.ir || 0), 0) / fundamentalFactors.length
    : 0.3;

  const capitalIR = 0.2;

  const minWeight = 0.1;
  const adjustedTechIR = Math.max(techIR, minWeight);
  const adjustedFundIR = Math.max(fundIR, minWeight);
  const adjustedCapitalIR = Math.max(capitalIR, minWeight);

  const totalIR = adjustedTechIR + adjustedFundIR + adjustedCapitalIR;

  return {
    technical: adjustedTechIR / totalIR,
    fundamental: adjustedFundIR / totalIR,
    capital: adjustedCapitalIR / totalIR,
  };
}

export const opportunityScanTool: ToolDefinition = {
  name: "opportunity_scan",
  label: "机会雷达（支持动态权重）",
  description:
    "机会雷达扫描：对指定股票池进行三维评分，找出高质量交易机会。\n\n" +
    "【评分模式】\n" +
    "• value: 价值投资模式（PE分位+ROE+毛利率+CF，适合长持）\n" +
    "• swing: 波段交易模式（ZigZag胜率+量比+RSI+距买点，不看PE分位，适合短持1-3天）\n" +
    "• auto: 自动检测（ZigZag胜率>80%且持仓<5天→swing，否则→value，默认）\n\n" +
    "【三种权重模式】\n" +
    "1. 固定权重（默认）: 技术50% + 基本面30% + 资金20%\n" +
    "2. 自定义权重: 手动指定三维权重\n" +
    "3. 动态权重: 基于因子有效性（IC/IR）自动计算最优权重\n\n" +
    "【核心功能】\n" +
    "• 动态评分：技术面+基本面+资金面+周期位置（周期股专属），按股票类型(成长/价值/周期)和市场环境(牛/熊/震荡)自动调权重\n" +
    "• 波段模式：ZigZag胜率替代PE分位，识别高胜率波段交易机会\n" +
    "• 证据链：每个机会附带打分明细、理由列表和实际权重，可复算可归因\n" +
    "• 风险等级：low/medium/high 自动评估\n" +
    "• 筛选条件：支持 RSI超卖、MACD金叉、PE/ROE门槛等\n" +
    "• 行业轮动：自动选择强势行业，精选个股\n\n" +
    "【适用场景】\n" +
    "• 市场扫描找机会（value模式找价值股，swing模式找波段股）\n" +
    "• 策略开发前的股票池构建\n" +
    "• 定期选股调仓\n" +
    "• 多因子策略优化\n\n" +
    "💾 大结果集（>60只股票）自动保存到本地文件，避免污染上下文。",

  parameters: Type.Object({
    mode: Type.Optional(Type.Union([
      Type.Literal('value'),
      Type.Literal('swing'),
      Type.Literal('auto')
    ], {
      description: "评分模式：value=价值投资（看PE分位+ROE+毛利率），swing=波段交易（看ZigZag胜率+量+RSI，不看PE分位），auto=自动检测（ZigZag胜率>80%且持仓<5天→swing，否则→value）。默认 auto。",
      default: 'auto'
    })),
    symbols: Type.Optional(Type.Array(Type.String(), {
      description: "要扫描的股票代码列表，如 ['600519', '000001']。留空=扫描全市场（热门股票池）。",
    })),
    conditions: Type.Optional(Type.Array(Type.String(), {
      description: "筛选条件列表，如 ['rsi_oversold', 'macd_golden_cross', 'pe_lt_20', 'roe_gt_15']",
    })),
    limit: Type.Optional(Type.Number({
      description: "返回前N个结果（默认20）",
      default: 20
    })),

    // === 权重配置（三选一）===
    weights: Type.Optional(Type.Object({
      technical: Type.Number({ description: "技术面权重（0-1）" }),
      fundamental: Type.Number({ description: "基本面权重（0-1）" }),
      capital: Type.Number({ description: "资金面权重（0-1）" })
    }, {
      description: "自定义权重。不传=使用固定权重（50%/30%/20%）。权重会自动归一化。"
    })),

    enable_dynamic_weights: Type.Optional(Type.Boolean({
      description: "是否启用动态权重（基于因子有效性自动计算）。启用后会覆盖 weights 参数。",
      default: false
    })),

    dynamic_weights_config: Type.Optional(Type.Object({
      factors: Type.Optional(Type.Array(Type.String(), {
        description: "要分析的因子列表，如 ['rsi', 'macd', 'roe', 'pe']。留空使用默认因子。"
      })),
      analysis_period: Type.Optional(Type.Object({
        start_date: Type.String({ description: "分析开始日期 YYYY-MM-DD" }),
        end_date: Type.String({ description: "分析结束日期 YYYY-MM-DD" })
      })),
      algorithm: Type.Optional(Type.Union([
        Type.Literal('ir_based'),
        Type.Literal('rating_based')
      ], {
        description: "权重计算算法：ir_based（基于IR，推荐）或 rating_based（基于评级）",
        default: 'ir_based'
      }))
    }, {
      description: "动态权重配置。仅在 enable_dynamic_weights=true 时生效。"
    })),

    // === 行业轮动筛选 ===
    sectorFilter: Type.Optional(Type.Object({
      enabled: Type.Boolean({ description: "是否启用行业轮动筛选" }),
      topN: Type.Optional(Type.Number({
        description: "选择前N个强势行业（默认3）",
        default: 3
      })),
      minSectorScore: Type.Optional(Type.Number({
        description: "行业最低评分（0-1，默认0）",
        default: 0
      })),
      excludeSectors: Type.Optional(Type.Array(Type.String(), {
        description: "排除的行业列表，如 ['银行', '房地产']"
      })),
      market: Type.Optional(Type.Union([Type.Literal('A'), Type.Literal('HK')], {
        description: "市场类型：A=A股，HK=港股（默认A）",
        default: 'A'
      }))
    }, {
      description: "行业轮动筛选配置。启用后，先计算行业相对强度，选出强势行业，再在这些行业中扫描个股。"
    }))
  }),

  execute: async (_toolCallId: string, rawParams: any) => {
    try {
      let outputText = "";
      let finalWeights: FactorWeight | undefined;

      // === Step 1: 动态权重计算（如果启用）===
      if (rawParams?.enable_dynamic_weights) {
        outputText += "📊 **动态权重模式**\n\n";

        const config = rawParams.dynamic_weights_config || {};
        const factors = config.factors || ['rsi', 'macd', 'roe', 'pe'];

        const endDate = config.analysis_period?.end_date || new Date().toISOString().split('T')[0];
        const startDate = config.analysis_period?.start_date ||
          new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        outputText += `Step 1: 因子有效性分析\n`;
        outputText += `  分析期: ${startDate} ~ ${endDate}\n`;
        outputText += `  因子: ${factors.join(', ')}\n\n`;

        try {
          const analysisResult = await analyzeFactors({
            factors,
            start_date: startDate,
            end_date: endDate
          });

          if (analysisResult.success) {
            finalWeights = calculateWeightsFromAnalysis(analysisResult);

            outputText += `Step 2: 动态权重计算\n`;
            outputText += `  算法: IR-based（信息比率归一化）\n\n`;
            outputText += `✅ 计算完成:\n`;
            outputText += `  • 技术面权重: ${(finalWeights.technical * 100).toFixed(1)}%\n`;
            outputText += `  • 基本面权重: ${(finalWeights.fundamental * 100).toFixed(1)}%\n`;
            outputText += `  • 资金面权重: ${(finalWeights.capital * 100).toFixed(1)}%\n\n`;

            const techDiff = finalWeights.technical - 0.5;
            const fundDiff = finalWeights.fundamental - 0.3;
            outputText += `📊 对比固定权重:\n`;
            outputText += `  • 技术面 ${techDiff > 0 ? '↑' : techDiff < 0 ? '↓' : '→'} ${(Math.abs(techDiff) * 100).toFixed(1)}%\n`;
            outputText += `  • 基本面 ${fundDiff > 0 ? '↑' : fundDiff < 0 ? '↓' : '→'} ${(Math.abs(fundDiff) * 100).toFixed(1)}%\n\n`;
          } else {
            outputText += `⚠️ 因子分析失败，使用固定权重\n\n`;
          }
        } catch (error) {
          outputText += `⚠️ 因子分析异常，使用固定权重\n\n`;
        }
      } else if (rawParams?.weights) {
        outputText += "📊 **自定义权重模式**\n\n";
        finalWeights = rawParams.weights;
        if (finalWeights) {
          outputText += `  • 技术面权重: ${(finalWeights.technical * 100).toFixed(1)}%\n`;
          outputText += `  • 基本面权重: ${(finalWeights.fundamental * 100).toFixed(1)}%\n`;
          outputText += `  • 资金面权重: ${(finalWeights.capital * 100).toFixed(1)}%\n\n`;
        }
      } else {
        outputText += "📊 **固定权重模式**\n\n";
        outputText += `  • 技术面权重: 50%\n`;
        outputText += `  • 基本面权重: 30%\n`;
        outputText += `  • 资金面权重: 20%\n\n`;
      }

      // === Step 2: 股票筛选 ===
      outputText += `🔍 **股票筛选**\n\n`;

      const scanParams: Record<string, unknown> = {};
      if (rawParams?.symbols && Array.isArray(rawParams.symbols)) {
        scanParams.symbols = rawParams.symbols;
      }

      // Bug #1 修复：将 conditions 拆分为 technical 和 fundamental
      if (rawParams?.conditions && Array.isArray(rawParams.conditions)) {
        const technicalConditions: string[] = [];
        const fundamentalConditions: string[] = [];

        // 根据条件类型分类
        for (const cond of rawParams.conditions) {
          if (typeof cond === 'string') {
            // 技术面条件：rsi_*, macd_*, bollinger_*, volume_*, adx_*
            if (cond.startsWith('rsi_') || cond.startsWith('macd_') ||
                cond.startsWith('bollinger_') || cond.startsWith('volume_') ||
                cond.startsWith('adx_')) {
              technicalConditions.push(cond);
            }
            // 基本面条件：pe_*, roe_*, gross_margin_*, debt_ratio_*, revenue_growth_*
            else if (cond.startsWith('pe_') || cond.startsWith('roe_') ||
                     cond.startsWith('gross_margin_') || cond.startsWith('debt_ratio_') ||
                     cond.startsWith('revenue_growth_')) {
              fundamentalConditions.push(cond);
            }
          }
        }

        if (technicalConditions.length > 0) {
          scanParams.technical = technicalConditions;
        }
        if (fundamentalConditions.length > 0) {
          scanParams.fundamental = fundamentalConditions;
        }
      }

      if (rawParams?.limit !== undefined) {
        scanParams.limit = rawParams.limit;
      }
      if (finalWeights) {
        scanParams.weights = finalWeights;
      }

      const opportunities = await scanOpportunities(scanParams);

      outputText += `扫描完成: ${opportunities.length} 只股票\n\n`;

      // === Step 2.5: 波段模式 — ZigZag 评分替代 PE 分位 ===
      const mode = rawParams?.mode || 'auto';
      if (mode === 'swing' || mode === 'auto') {
        outputText += await enrichWithSwingScore(opportunities, mode);
      }

      // === Step 3: 格式化并返回结果 ===
      const formattedText = formatOpportunities(opportunities);
      outputText += formattedText;

      // 使用统一响应处理（大结果集持久化）
      return handleToolResponse({
        toolName: 'opportunity_scan',
        data: { opportunities, weights: finalWeights, output: outputText },
        formatter: (data) => data.output,
        metadata: {
          symbol_count: rawParams?.symbols?.length || 'market',
          opportunity_count: opportunities.length,
          enable_dynamic_weights: rawParams?.enable_dynamic_weights || false,
        },
        threshold: 30 * 1024, // 30KB，约对应20-30只股票的详细信息
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  },
};
