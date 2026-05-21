/**
 * Market Sentiment Analysis Tool
 *
 * Analyzes market sentiment indicators: panic/fear index, margin trading activity,
 * northbound capital flows, market news sentiment, and hot stock trends.
 * Provides a composite sentiment score (0-100) to quantify market fear/greed levels,
 * helping avoid panic selling during extreme fear or greedy chasing at market tops.
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import {
  getHotStocksViaQuantCli,
  getMacroDataViaQuantCli,
  getMarketMarginViaQuantCli,
  getMarketOverviewViaQuantCli,
  getNorthFlowViaQuantCli,
} from "../quant/market-query-cli-adapter.js";

/**
 * Calculate a composite sentiment score from individual indicators.
 * Score: 0 = extreme fear, 50 = neutral, 100 = extreme greed
 */
function calcSentimentScore(indicators: SentimentIndicators): number {
  let totalWeight = 0;
  let weightedScore = 0;

  // 1. Northbound flow (foreign capital sentiment)
  // Sustained strong inflow = greed; sustained outflow = fear
  if (indicators.northFlowScore !== undefined) {
    const weight = 0.30;
    weightedScore += indicators.northFlowScore * weight;
    totalWeight += weight;
  }

  // 2. Margin trading sentiment (retail leverage appetite)
  // Rising margin balance = greed; falling = fear/risk-off
  if (indicators.marginScore !== undefined) {
    const weight = 0.20;
    weightedScore += indicators.marginScore * weight;
    totalWeight += weight;
  }

  // 3. Market breadth / hot stocks sentiment
  // Too many stocks hitting limits = extreme sentiment; too few = apathy
  if (indicators.marketBreadthScore !== undefined) {
    const weight = 0.20;
    weightedScore += indicators.marketBreadthScore * weight;
    totalWeight += weight;
  }

  // 4. Market performance trend (recent index change)
  // Strong rally = greed; sharp decline = fear
  if (indicators.trendScore !== undefined) {
    const weight = 0.15;
    weightedScore += indicators.trendScore * weight;
    totalWeight += weight;
  }

  // 5. News / macro sentiment
  if (indicators.newsScore !== undefined) {
    const weight = 0.15;
    weightedScore += indicators.newsScore * weight;
    totalWeight += weight;
  }

  if (totalWeight === 0) return 50; // neutral fallback

  return Math.round(Math.min(100, Math.max(0, weightedScore / totalWeight)));
}

interface SentimentIndicators {
  northFlowScore?: number;
  marginScore?: number;
  marketBreadthScore?: number;
  trendScore?: number;
  newsScore?: number;
}

function getSentimentLabel(score: number): string {
  if (score >= 80) return "极度贪婪";
  if (score >= 65) return "贪婪";
  if (score >= 55) return "偏贪婪";
  if (score >= 45) return "中性";
  if (score >= 35) return "偏恐惧";
  if (score >= 20) return "恐惧";
  return "极度恐惧";
}

function getSentimentAdvice(label: string): string {
  switch (label) {
    case "极度贪婪":
      return "⚠️ 市场情绪极度亢奋，短期回调风险极高。建议减仓锁定利润，避免追高。";
    case "贪婪":
      return "⚡ 市场情绪偏热，部分板块可能已透支。建议控制仓位，分批止盈。";
    case "偏贪婪":
      return "📈 市场情绪积极，但需警惕过热信号。持有为主，谨慎加仓。";
    case "中性":
      return "➖ 市场情绪中性，无明显极端信号。维持现有策略，按计划执行。";
    case "偏恐惧":
      return "📉 市场情绪偏冷，部分优质资产可能被错杀。关注超跌机会，分批建仓。";
    case "恐惧":
      return "🔦 市场恐慌蔓延，但往往孕育机会。检查持仓基本面，考虑逢低吸纳优质股。";
    case "极度恐惧":
      return "🛡️ 市场极度恐慌，历史经验表明这是中长期布局良机。保持冷静，做好资金管理。";
    default:
      return "";
  }
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export const testMarketSentimentTool: ToolDefinition = {
  name: "test_market_sentiment",
  label: "分析市场情绪",
  description:
    "Analyze market sentiment indicators (fear/greed index, margin trading, northbound capital flow). " +
    "Provides a composite sentiment score (0-100) to quantify market fear/greed levels, helping users " +
    "avoid panic selling during extreme fear or chasing bubbles during extreme greed. " +
    "Returns sentiment score, individual indicator breakdown, and actionable advice. " +
    "Use this before making major buy/sell decisions to understand market emotion context.",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    try {
      // ── Fetch all sentiment data in parallel ──
      const [northFlowResult, marginResult, macroResult, marketOverviewResult, hotStocksResult] = await Promise.all([
        getNorthFlowViaQuantCli().catch(() => null),
        getMarketMarginViaQuantCli().catch(() => null),
        getMacroDataViaQuantCli().catch(() => null),
        getMarketOverviewViaQuantCli().catch(() => null),
        getHotStocksViaQuantCli().catch(() => null),
      ]);

      const northFlowData = northFlowResult ? JSON.parse(northFlowResult) : null;
      const marginData = marginResult ? JSON.parse(marginResult) : null;
      const macroData = macroResult ? JSON.parse(macroResult) : null;
      const marketOverviewData = marketOverviewResult ? JSON.parse(marketOverviewResult) : null;
      const hotStocksData = hotStocksResult ? JSON.parse(hotStocksResult) : null;

      // ── Build sentiment indicators ──
      const indicators: SentimentIndicators = {};
      const details: Record<string, any> = {};

      // ── 1. Northbound flow analysis ──
      if (northFlowData && !northFlowData.error) {
        const flows = northFlowData.data || northFlowData.flows || [];
        if (Array.isArray(flows) && flows.length > 0) {
          // Calculate recent trend: sum last N days
          const recentFlows = flows.slice(-10);
          const totalInflow = recentFlows.reduce((sum: number, f: any) => {
            return sum + (Number(f.net_inflow || f.netInflow || f.value || 0) / 1e8);
          }, 0);
          // Average daily inflow in 亿
          const avgInflow = flows.length > 0
            ? recentFlows.reduce((sum: number, f: any) => sum + (Number(f.net_inflow || f.netInflow || f.value || 0) / 1e8), 0) / recentFlows.length
            : 0;

          // Normalize: -50亿/day avg = extreme fear (score 0), +50亿/day avg = extreme greed (score 100)
          const rawScore = ((avgInflow + 50) / 100) * 100;
          indicators.northFlowScore = Math.round(Math.min(100, Math.max(0, rawScore)));

          // Count consecutive inflow/outflow days
          let consecutiveInflow = 0;
          let consecutiveOutflow = 0;
          for (const f of recentFlows.slice().reverse()) {
            const inflow = Number(f.net_inflow || f.netInflow || f.value || 0);
            if (inflow > 0) {
              consecutiveInflow++;
              consecutiveOutflow = 0;
            } else {
              consecutiveOutflow++;
              consecutiveInflow = 0;
            }
          }

          details.northFlow = {
            totalInflow10d: totalInflow,
            avgDailyInflow: avgInflow,
            consecutiveInflowDays: consecutiveInflow,
            consecutiveOutflowDays: consecutiveOutflow,
            trend: totalInflow > 0 ? "外资净流入" : "外资净流出",
          };
        } else {
          details.northFlow = { error: "无有效北向资金数据" };
        }
      } else {
        details.northFlow = { error: northFlowData?.error || "获取北向资金数据失败" };
      }

      // ── 2. Margin trading analysis ──
      if (marginData && !marginData.error) {
        const marginRecords = marginData.data || marginData.margins || [];
        if (Array.isArray(marginRecords) && marginRecords.length >= 2) {
          const latest = marginRecords[marginRecords.length - 1];
          const prev = marginRecords[marginRecords.length - 2];

          const latestBalance = Number(latest.total_margin || latest.margin_balance || latest.total || 0);
          const prevBalance = Number(prev.total_margin || prev.margin_balance || prev.total || 0);
          const changePct = prevBalance > 0 ? ((latestBalance - prevBalance) / prevBalance) * 100 : 0;

          // Total margin > 1.8万亿 = high leverage risk
          const highLeverageRisk = latestBalance > 18000; // in 亿

          // Score based on direction: rising margin = greed, falling = fear
          // Normalize: -5% change = fear (0), +5% change = greed (100)
          const rawScore = ((changePct + 5) / 10) * 100;
          indicators.marginScore = Math.round(Math.min(100, Math.max(0, rawScore)));

          details.margin = {
            latestBalance: `${latestBalance.toFixed(0)}亿`,
            changePct: changePct,
            changeLabel: changePct > 0 ? "融资余额上升" : "融资余额下降",
            highLeverageRisk,
          };
        } else {
          details.margin = { error: "融资融券数据不足" };
        }
      } else {
        details.margin = { error: marginData?.error || "获取融资融券数据失败" };
      }

      // ── 3. Market breadth analysis (from hot stocks & market overview) ──
      let hotStockCount = 0;
      if (hotStocksData && !hotStocksData.error) {
        const stocks = hotStocksData.data || hotStocksData.stocks || [];
        hotStockCount = Array.isArray(stocks) ? stocks.length : 0;

        // Average change of hot stocks
        const avgChange = Array.isArray(stocks) && stocks.length > 0
          ? stocks.reduce((sum: number, s: any) => sum + (Number(s.change_pct || s.pct_chg || s.change || 0)), 0) / stocks.length
          : 0;

        // Too many hot stocks with extreme changes = extreme sentiment
        const extremeCount = Array.isArray(stocks)
          ? stocks.filter((s: any) => {
              const chg = Number(s.change_pct || s.pct_chg || s.change || 0);
              return Math.abs(chg) > 5;
            }).length
          : 0;

        // Score: more hot stocks with extreme moves = more extreme sentiment
        // Normalize: 0 extreme = neutral, 10+ extreme = extreme (score 0 or 100 depending on direction)
        const extremeRatio = Array.isArray(stocks) && stocks.length > 0 ? extremeCount / stocks.length : 0;
        const direction = avgChange > 0 ? 1 : -1;
        const breadthScore = 50 + direction * (extremeRatio * 50);
        indicators.marketBreadthScore = Math.round(Math.min(100, Math.max(0, breadthScore)));

        details.hotStocks = {
          count: hotStockCount,
          avgChange,
          extremeCount,
          sentiment: avgChange > 3 ? "热点过热" : avgChange < -3 ? "热点恐慌" : "正常",
        };
      } else {
        details.hotStocks = { error: "获取热门股票数据失败" };
      }

      // ── 4. Market trend analysis ──
      if (marketOverviewData && !marketOverviewData.error) {
        const indices = marketOverviewData.data || marketOverviewData.indices || [];
        if (Array.isArray(indices) && indices.length > 0) {
          const avgChange = indices.reduce((sum: number, idx: any) => {
            return sum + (Number(idx.change_pct || idx.pct_chg || idx.change || 0));
          }, 0) / indices.length;

          // Score based on index change: -3% = fear (0), +3% = greed (100)
          const rawScore = ((avgChange + 3) / 6) * 100;
          indicators.trendScore = Math.round(Math.min(100, Math.max(0, rawScore)));

          // Count advancing vs declining indices
          const advancing = indices.filter((idx: any) => (Number(idx.change_pct || idx.pct_chg || idx.change || 0)) > 0).length;
          const declining = indices.filter((idx: any) => (Number(idx.change_pct || idx.pct_chg || idx.change || 0)) < 0).length;

          details.marketTrend = {
            avgChange,
            advancingIndices: advancing,
            decliningIndices: declining,
            trend: avgChange > 0.5 ? "强势上涨" : avgChange < -0.5 ? "明显下跌" : "震荡整理",
          };
        } else {
          details.marketTrend = { error: "无有效指数数据" };
        }
      } else {
        details.marketTrend = { error: marketOverviewData?.error || "获取大盘数据失败" };
      }

      // ── 5. Macro sentiment (PMI as proxy for economic sentiment) ──
      if (macroData && !macroData.error) {
        const pmiData = macroData.pmi || macroData.data?.pmi || null;
        if (pmiData && Array.isArray(pmiData) && pmiData.length > 0) {
          const latestPmi = pmiData[pmiData.length - 1];
          const pmiValue = Number(latestPmi.value || latestPmi.pmi || latestPmi.close || 0);

          // PMI: 50 = neutral, >52 = expansion (greed), <48 = contraction (fear)
          // Score: 40 = fear (pmi=48), 60 = greed (pmi=52), map linearly
          const rawScore = ((pmiValue - 48) / 4) * 50 + 50;
          indicators.newsScore = Math.round(Math.min(100, Math.max(0, rawScore)));

          details.macro = {
            latestPmi: pmiValue,
            pmiLabel: pmiValue > 50 ? "扩张" : pmiValue < 50 ? "收缩" : "荣枯线",
          };
        } else {
          details.macro = { error: "PMI数据不足" };
        }
      } else {
        details.macro = { error: macroData?.error || "获取宏观数据失败" };
      }

      // ── Composite score ──
      const compositeScore = calcSentimentScore(indicators);
      const sentimentLabel = getSentimentLabel(compositeScore);
      const advice = getSentimentAdvice(sentimentLabel);

      // ── Build output ──
      let output = "# 📊 市场情绪分析\n\n";

      // Overall gauge
      output += `## 综合情绪指数: ${compositeScore}/100\n`;
      output += `情绪等级: **${sentimentLabel}**\n\n`;

      // Gauge visual
      const gaugeLen = 20;
      const gaugePos = Math.round((compositeScore / 100) * gaugeLen);
      const gauge = "█".repeat(gaugePos) + "░".repeat(gaugeLen - gaugePos);
      output += `[${gauge}] 恐惧 ${"─".repeat(6)} 贪婪\n\n`;

      // Individual breakdown
      output += "## 细分指标\n\n";

      if (details.northFlow && !details.northFlow.error) {
        const nf = details.northFlow;
        output += `### 北向资金 (权重30%)\n`;
        output += `- 近10日累计净流入: ${nf.totalInflow10d.toFixed(2)}亿\n`;
        output += `- 日均净流入: ${nf.avgDailyInflow.toFixed(2)}亿\n`;
        if (nf.consecutiveInflowDays > 0) {
          output += `- 连续净流入天数: ${nf.consecutiveInflowDays}天 ✅\n`;
        }
        if (nf.consecutiveOutflowDays > 0) {
          output += `- 连续净流出天数: ${nf.consecutiveOutflowDays}天 ❌\n`;
        }
        output += `- 趋势: ${nf.trend}\n`;
        output += `- 子评分: ${indicators.northFlowScore ?? "N/A"}/100\n\n`;
      } else {
        output += `### 北向资金 (权重30%)\n- ${details.northFlow?.error || "数据暂不可用"}\n\n`;
      }

      if (details.margin && !details.margin.error) {
        const m = details.margin;
        output += `### 融资融券 (权重20%)\n`;
        output += `- 最新融资余额: ${m.latestBalance}\n`;
        output += `- 变化: ${formatPercent(m.changePct)}\n`;
        output += `- 信号: ${m.changeLabel}\n`;
        if (m.highLeverageRisk) {
          output += `- ⚠️ 融资余额超1.8万亿，市场杠杆偏高，回调风险加大\n`;
        }
        output += `- 子评分: ${indicators.marginScore ?? "N/A"}/100\n\n`;
      } else {
        output += `### 融资融券 (权重20%)\n- ${details.margin?.error || "数据暂不可用"}\n\n`;
      }

      if (details.hotStocks && !details.hotStocks.error) {
        const hs = details.hotStocks;
        output += `### 热点情绪 (权重20%)\n`;
        output += `- 热门股票数: ${hs.count}\n`;
        output += `- 平均涨跌幅: ${formatPercent(hs.avgChange)}\n`;
        output += `- 极端异动数: ${hs.extremeCount}\n`;
        output += `- 判断: ${hs.sentiment}\n`;
        output += `- 子评分: ${indicators.marketBreadthScore ?? "N/A"}/100\n\n`;
      } else {
        output += `### 热点情绪 (权重20%)\n- ${details.hotStocks?.error || "数据暂不可用"}\n\n`;
      }

      if (details.marketTrend && !details.marketTrend.error) {
        const mt = details.marketTrend;
        output += `### 大盘趋势 (权重15%)\n`;
        output += `- 主要指数平均涨跌: ${formatPercent(mt.avgChange)}\n`;
        output += `- 上涨指数数: ${mt.advancingIndices} / 下跌: ${mt.decliningIndices}\n`;
        output += `- 形态: ${mt.trend}\n`;
        output += `- 子评分: ${indicators.trendScore ?? "N/A"}/100\n\n`;
      } else {
        output += `### 大盘趋势 (权重15%)\n- ${details.marketTrend?.error || "数据暂不可用"}\n\n`;
      }

      if (details.macro && !details.macro.error) {
        const mc = details.macro;
        output += `### 宏观情绪 (权重15%)\n`;
        output += `- 最新制造业PMI: ${mc.latestPmi}\n`;
        output += `- 经济状态: ${mc.pmiLabel}\n`;
        output += `- 子评分: ${indicators.newsScore ?? "N/A"}/100\n\n`;
      } else {
        output += `### 宏观情绪 (权重15%)\n- ${details.macro?.error || "数据暂不可用"}\n\n`;
      }

      output += "---\n\n";
      output += `## 💡 操作建议\n${advice}\n\n`;

      output += "---\n\n";
      output += "**数据说明**: 综合情绪指数综合了北向资金(30%)、融资融券(20%)、热点情绪(20%)、大盘趋势(15%)、宏观情绪(15%)五个维度，分数越高代表市场越贪婪。\n";

      return {
        content: [{
          type: "text" as const,
          text: output,
        }],
        details: {
          compositeScore,
          sentimentLabel,
          advice,
          indicators,
          details,
        },
      };
    } catch (e) {
      return {
        content: [{
          type: "text" as const,
          text: `市场情绪分析失败: ${e instanceof Error ? e.message : String(e)}`,
        }],
        details: undefined,
      };
    }
  },
};
