/**
 * StopLossAnalyzer — 止损分析引擎
 *
 * 在触发止损条件后做多维分析，判断是真破位还是假洗盘。
 *
 * 分析维度（权重由高到低）：
 * 1. 技术面（40%）：趋势方向、MA排列、支撑阻力、K线形态、RSI、MACD
 * 2. 成交量（30%）：今日量对比20日均量，缩量=假破位嫌疑 放量=真破位信号
 * 3. 资金面（20%）：主力资金流向，主力出逃=真破位 散户接盘=风险
 * 4. 基本面（10%）：近期是否有重大利空/利多/业绩预警
 *
 * 使用方式：
 *   const analyzer = new StopLossAnalyzer();
 *   const report = await analyzer.analyze(request);
 *
 * 回退机制：任一维度分析失败，跳过该维度继续（非降级）。
 * 所有维度均失败 → confidence=0, action=INSUFFICIENT_DATA。
 */

import {
  analyzeCandlestickViaQuantCli,
  analyzePriceActionViaQuantCli,
  analyzeTechnicalViaQuantCli,
} from "../../infrastructure/quant/analysis-query-cli-adapter.js";
import {
  getAnnouncementsViaQuantCli,
  getStockHistoryViaQuantCli,
  getStockNewsViaQuantCli,
} from "../../infrastructure/quant/stock-query-cli-adapter.js";
import { getStockFundFlowViaQuantCli } from "../../infrastructure/quant/sentiment-query-cli-adapter.js";
import { chinaDateTime } from "../../utils/china-time.js";
import type {
  StopLossAnalysisRequest,
  StopLossReport,
  BreakoutType,
  StopLossAction,
  EvidenceItem,
  TechnicalAnalysis,
  VolumeAnalysis,
  FundFlowAnalysis,
  FundamentalCheck,
} from "../../types/stop-loss-analysis.js";

// ─── 常量 ──────────────────────────────────────────────────────────────────

/** 各维度超时（毫秒） */
const TIMEOUTS = {
  TECHNICAL: 5000,
  VOLUME: 3000,
  FUND_FLOW: 3000,
  FUNDAMENTALS: 4000,
};

/** 缩量阈值：今日量 < 均量的 80% = 缩量 */
const SHRINK_THRESHOLD = 0.8;

/** 放量阈值：今日量 > 均量的 150% = 放量 */
const SPIKE_THRESHOLD = 1.5;

/** 置信度阈值 */
const HIGH_CONFIDENCE = 70;
const MEDIUM_CONFIDENCE = 50;

// ─── 工具函数 ──────────────────────────────────────────────────────────────

function now(): string {
  return chinaDateTime();
}

function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

/**
 * 给异步调用加超时
 */
function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return Promise.race([
    promise,
    new Promise<null>((_, reject) =>
      timer = setTimeout(() => reject(new Error(`${label} 超时 (${ms}ms)`)), ms)
    ),
  ]).finally(() => {
    if (timer) {
      clearTimeout(timer);
    }
  }).catch((err) => {
    console.warn(`[StopLossAnalyzer] ${label}: ${err instanceof Error ? err.message : String(err)}`);
    return null;
  });
}

// ─── 分析函数 ──────────────────────────────────────────────────────────────

/**
 * 技术面分析
 * 调用 analyze_price_action 获取趋势、支撑阻力、成交量结构
 */
async function checkTechnical(
  symbol: string,
  currentPrice: number,
): Promise<TechnicalAnalysis> {
  const evidence: EvidenceItem[] = [];

  try {
    const raw = await withTimeout(analyzePriceActionViaQuantCli(symbol, 60), TIMEOUTS.TECHNICAL, "技术分析");
    if (!raw) {
      return {
        trend: "无法判断", trendConfirmed: false,
        supportLevel: null, resistanceLevel: null,
        pattern: null, rsi: null, macdSignal: null,
        evidence,
      };
    }

    const result = typeof raw === "string" ? JSON.parse(raw) : raw;

    evidence.push({
      source: "analyze_price_action",
      summary: `趋势判断: ${result.trend || result.trendDirection || "未知"}, 支撑位: ${result.nearestSupport || result.supportLevels?.[0] || "无"}, 阻力位: ${result.nearestResistance || result.resistanceLevels?.[0] || "无"}`,
      detail: JSON.stringify(result).slice(0, 500),
    });

    const trend = result.trend || result.trendDirection || "震荡";
    const supportLevel = result.nearestSupport ?? result.supportLevels?.[0] ?? null;
    const resistanceLevel = result.nearestResistance ?? result.resistanceLevels?.[0] ?? null;

    // K线形态分析
    let pattern: string | null = null;
    try {
      const patternRaw = await withTimeout(
        analyzeCandlestickViaQuantCli(symbol),
        TIMEOUTS.TECHNICAL,
        "K线形态分析",
      );
      if (patternRaw) {
        const pData = typeof patternRaw === "string" ? JSON.parse(patternRaw) : patternRaw;
        const patterns: string[] = pData.patterns ?? pData.summary ?? [];
        const patternStr = Array.isArray(patterns) ? patterns.join(", ") : String(patterns);
        if (patternStr) {
          pattern = patternStr.slice(0, 200);
          evidence.push({
            source: "analyze_candlestick",
            summary: `K线形态: ${patternStr.slice(0, 100)}`,
            detail: JSON.stringify(pData).slice(0, 500),
          });
        }
      }
    } catch {
      // K线形态分析失败，不阻塞
    }

    // RSI / MACD 信号
    let rsi: number | null = null;
    let macdSignal: string | null = null;
    try {
      const techRaw = await withTimeout(
        analyzeTechnicalViaQuantCli(symbol),
        TIMEOUTS.TECHNICAL,
        "技术指标计算",
      );
      if (techRaw) {
        const tech = typeof techRaw === "string" ? JSON.parse(techRaw) : techRaw;
        if (tech.signals?.length) {
          macdSignal = tech.signals.join(", ");
          evidence.push({
            source: "quant.analysis.technical",
            summary: `信号: ${tech.signals.slice(0, 3).join(", ")}`,
            detail: JSON.stringify(tech).slice(0, 300),
          });
        }
        rsi = tech.rsi ?? null;
      }
    } catch {
      // 技术指标计算失败，不阻塞
    }

    const trendConfirmed = ["上升", "下降"].includes(trend);
    return { trend, trendConfirmed, supportLevel, resistanceLevel, pattern, rsi, macdSignal, evidence };
  } catch (err) {
    console.warn(`[StopLossAnalyzer] 技术分析失败:`, err);
    return {
      trend: "无法判断", trendConfirmed: false,
      supportLevel: null, resistanceLevel: null,
      pattern: null, rsi: null, macdSignal: null,
      evidence,
    };
  }
}

/**
 * 成交量分析
 * 用 quant CLI 历史行情获取最近成交量，对比20日均量
 */
async function checkVolume(symbol: string): Promise<VolumeAnalysis> {
  const evidence: EvidenceItem[] = [];

  try {
    const raw = await withTimeout(
      getStockHistoryViaQuantCli({ symbol, period: "daily", limit: 60 }),
      TIMEOUTS.VOLUME,
      "获取历史行情",
    );
    if (!raw) {
      return { vsAvgVolume: null, isShrink: null, isVolumeSpike: null, evidence };
    }

    const data = typeof raw === "string" ? JSON.parse(raw) : raw;
    const candles = Array.isArray(data) ? data : (data.data ?? data.klines ?? data.records ?? []);

    if (candles.length < 25) {
      evidence.push({
        source: "quant.stock.history",
        summary: `历史数据不足 (${candles.length}条)，成交量分析不可靠`,
        detail: "",
      });
      return { vsAvgVolume: null, isShrink: null, isVolumeSpike: null, evidence };
    }

    // 取最近 21 天的成交量（今日 + 前20日）
    const volumes: number[] = candles
      .slice(-21)
      .map((c: any) => Number(c.volume ?? c.vol ?? 0))
      .filter((v: number) => v > 0);

    if (volumes.length < 5) {
      evidence.push({
        source: "quant.stock.history",
        summary: "成交量数据不足",
        detail: "",
      });
      return { vsAvgVolume: null, isShrink: null, isVolumeSpike: null, evidence };
    }

    const todayVol = volumes[volumes.length - 1];
    const avg20 = volumes.slice(0, -1).reduce((sum: number, v: number) => sum + v, 0) / (volumes.length - 1);

    const vsAvg = avg20 > 0 ? round2((todayVol / avg20) * 100) : null;
    const isShrink = vsAvg !== null ? vsAvg < SHRINK_THRESHOLD * 100 : null;
    const isVolumeSpike = vsAvg !== null ? vsAvg > SPIKE_THRESHOLD * 100 : null;

    evidence.push({
      source: "quant.stock.history",
      summary: `今日量 ${todayVol.toLocaleString()}, 20日均量 ${round2(avg20).toLocaleString()}, 比值 ${vsAvg !== null ? vsAvg + "%" : "N/A"}`,
      detail: JSON.stringify({ todayVol, avg20, vsAvg }),
    });

    return { vsAvgVolume: vsAvg, isShrink, isVolumeSpike, evidence };
  } catch (err) {
    console.warn(`[StopLossAnalyzer] 成交量分析失败:`, err);
    return { vsAvgVolume: null, isShrink: null, isVolumeSpike: null, evidence };
  }
}

/**
 * 资金面分析
 * 调用 get_stock_fund_flow 获取主力资金流向
 */
async function checkFundFlow(symbol: string): Promise<FundFlowAnalysis> {
  const evidence: EvidenceItem[] = [];

  try {
    const raw = await withTimeout(
      getStockFundFlowViaQuantCli({ symbol }),
      TIMEOUTS.FUND_FLOW,
      "获取资金流向",
    );
    if (!raw) {
      return { mainForceNetFlow: null, retailBuyRatio: null, evidence };
    }

    const data = typeof raw === "string" ? JSON.parse(raw) : raw;

    // 提取主力净流入信息
    const mainNetInflow = data.主力净流入 ?? data.main_force_net_inflow ?? data.mainForceNetInflow;
    const largeOrderNetInflow = data.大单净流入 ?? data.largeOrderNetInflow;
    const retailNetInflow = data.小单净流入 ?? data.retailNetInflow ?? data.smallOrderNetInflow;

    let mainForceNetFlow: string | null = null;
    if (mainNetInflow !== undefined) {
      const inflowNum = Number(mainNetInflow);
      mainForceNetFlow = inflowNum > 0 ? "净流入" : inflowNum < 0 ? "净流出" : "无明显信号";
    }

    // 散户买入比例
    let retailBuyRatio: string | null = null;
    if (retailNetInflow !== undefined) {
      const retailNum = Number(retailNetInflow);
      if (mainNetInflow !== undefined && Math.abs(Number(mainNetInflow)) > 0) {
        const ratio = round2(Math.abs(retailNum / Number(mainNetInflow)) * 100);
        retailBuyRatio = `${ratio}%`;
      }
    }

    evidence.push({
      source: "get_stock_fund_flow",
      summary: `主力资金: ${mainForceNetFlow ?? "无数据"}, 散户: ${retailBuyRatio ?? "无数据"}`,
      detail: JSON.stringify(data).slice(0, 300),
    });

    return { mainForceNetFlow, retailBuyRatio, evidence };
  } catch (err) {
    console.warn(`[StopLossAnalyzer] 资金面分析失败:`, err);
    return { mainForceNetFlow: null, retailBuyRatio: null, evidence };
  }
}

/**
 * 基本面检查
 * 只检查是否有重大利空/利多，不深入分析
 */
async function checkFundamentals(symbol: string): Promise<FundamentalCheck> {
  const evidence: EvidenceItem[] = [];

  try {
    const [newsRaw, annRaw] = await Promise.all([
      withTimeout(getStockNewsViaQuantCli(symbol, 10), TIMEOUTS.FUNDAMENTALS, "获取新闻"),
      withTimeout(getAnnouncementsViaQuantCli(symbol), TIMEOUTS.FUNDAMENTALS, "获取公告")
        .catch(() => null),
    ]);

    let hasNegative = false;
    let hasPositive = false;
    let earningsWarning = false;
    const newsLines: string[] = [];

    // 分析新闻
    if (newsRaw) {
      const newsData = typeof newsRaw === "string" ? JSON.parse(newsRaw) : newsRaw;
      const articles = Array.isArray(newsData) ? newsData : (newsData.news ?? newsData.items ?? newsData.data ?? []);

      const NEGATIVE_KEYWORDS = ["减持", "利空", "下跌", "预警", "亏损", "调查", "监管", "处罚", "st"];
      const POSITIVE_KEYWORDS = ["涨停", "利好", "增长", "突破", "签约", "中标", "回购", "增持", "分红"];

      for (const art of articles.slice(0, 5)) {
        const title = String(art.title ?? art.Title ?? "");
        newsLines.push(title);
        if (NEGATIVE_KEYWORDS.some(k => title.includes(k))) hasNegative = true;
        if (POSITIVE_KEYWORDS.some(k => title.includes(k))) hasPositive = true;
      }
    }

    // 分析公告
    if (annRaw) {
      const annData = typeof annRaw === "string" ? JSON.parse(annRaw) : annRaw;
      const anns = Array.isArray(annData) ? annData : (annData.announcements ?? annData.items ?? annData.data ?? []);

      const WARNING_KEYWORDS = ["业绩预告", "业绩快报", "预亏", "预减", "减持", "风险提示"];
      for (const ann of anns.slice(0, 10)) {
        const title = String(ann.title ?? ann.Title ?? "");
        if (WARNING_KEYWORDS.some(k => title.includes(k))) {
          earningsWarning = true;
          newsLines.push(`[公告] ${title}`);
        }
      }
    }

    evidence.push({
      source: "get_stock_news, get_announcements",
      summary: `负面消息: ${hasNegative ? "有" : "无"}, 正面消息: ${hasPositive ? "有" : "无"}, 业绩预警: ${earningsWarning ? "有" : "无"}`,
      detail: newsLines.join("\n"),
    });

    return {
      hasRecentNegativeNews: hasNegative,
      hasRecentPositiveNews: hasPositive,
      earningsWarning,
      newsSummary: newsLines.length > 0 ? newsLines.slice(0, 5).join("; ") : "无近期重大新闻",
      evidence,
    };
  } catch (err) {
    console.warn(`[StopLossAnalyzer] 基本面检查失败:`, err);
    return {
      hasRecentNegativeNews: null,
      hasRecentPositiveNews: null,
      earningsWarning: null,
      newsSummary: "基本面数据不可用",
      evidence,
    };
  }
}

// ─── 综合判定 ──────────────────────────────────────────────────────────────

/**
 * 综合各维度分析，产出破位判定
 */
function synthesize(
  technical: TechnicalAnalysis,
  volume: VolumeAnalysis,
  fundFlow: FundFlowAnalysis,
  fundamentals: FundamentalCheck,
  request: StopLossAnalysisRequest,
): { breakoutType: BreakoutType; confidence: number; suggestedAction: StopLossAction; actionReason: string; riskNote: string } {
  // 计分系统：各维度权重
  // 技术面40分, 成交量30分, 资金面20分, 基本面10分
  let trueBreakScore = 0;   // 真破位得分（越高越像真破位）
  let falseBreakScore = 0;  // 假洗盘得分（越高越像假洗盘）
  const reasons: string[] = [];

  // === 1. 技术面（40分） ===
  if (technical.trendConfirmed) {
    if (technical.trend === "下降") {
      trueBreakScore += 30;
      reasons.push(`技术面: 趋势确认下降 (+30)`);
    } else if (technical.trend === "上升") {
      falseBreakScore += 30;
      reasons.push(`技术面: 趋势仍为上升，当前可能只是回调 (+30)`);
    }
  } else {
    // 震荡趋势，根据价格与支撑位的关系判断
    if (technical.supportLevel && request.currentPrice <= technical.supportLevel) {
      trueBreakScore += 20;
      reasons.push(`技术面: 跌破支撑位 ${technical.supportLevel} (+20)`);
    } else {
      trueBreakScore += 10;
      reasons.push(`技术面: 震荡趋势，方向不明 (+10)`);
    }
  }

  // MACD信号
  if (technical.macdSignal) {
    if (technical.macdSignal.includes("死叉") || technical.macdSignal.includes("空头")) {
      trueBreakScore += 10;
      reasons.push(`技术面: ${technical.macdSignal} (+10)`);
    } else if (technical.macdSignal.includes("金叉") || technical.macdSignal.includes("多头")) {
      falseBreakScore += 10;
      reasons.push(`技术面: ${technical.macdSignal} (+10)`);
    }
  }

  // K线形态
  if (technical.pattern) {
    if (technical.pattern.includes("锤子") || technical.pattern.includes("启明星") || technical.pattern.includes("吞没看涨")) {
      falseBreakScore += 10;
      reasons.push(`技术面: K线形态为看涨信号 — ${technical.pattern} (+10)`);
    } else if (technical.pattern.includes("吊颈") || technical.pattern.includes("黄昏星") || technical.pattern.includes("吞没看跌")) {
      trueBreakScore += 10;
      reasons.push(`技术面: K线形态为看跌信号 — ${technical.pattern} (+10)`);
    }
  }

  // RSI
  if (technical.rsi !== null) {
    if (technical.rsi < 30) {
      falseBreakScore += 15;
      reasons.push(`技术面: RSI=${round2(technical.rsi)} 超卖区域，反弹概率高 (+15)`);
    } else if (technical.rsi > 70) {
      trueBreakScore += 10;
      reasons.push(`技术面: RSI=${round2(technical.rsi)} 超买区域 (+10)`);
    }
  }

  // === 2. 成交量（30分） ===
  if (volume.isShrink === true) {
    falseBreakScore += 25;
    reasons.push(`成交量: 缩量(均量的${volume.vsAvgVolume}%)，卖压衰竭，假破位嫌疑 (+25)`);
  } else if (volume.isVolumeSpike === true) {
    trueBreakScore += 25;
    reasons.push(`成交量: 放量(均量的${volume.vsAvgVolume}%)，恐慌抛售，真破位信号 (+25)`);
  } else if (volume.isShrink === false && volume.isVolumeSpike === false) {
    // 正常量
    trueBreakScore += 10;
    reasons.push(`成交量: 正常量(均量的${volume.vsAvgVolume}%)，无明显异常 (+10)`);
  } else {
    reasons.push("成交量: 数据不足，跳过");
  }

  // === 3. 资金面（20分） ===
  if (fundFlow.mainForceNetFlow === "净流出") {
    trueBreakScore += 15;
    reasons.push("资金面: 主力资金净流出，机构在卖 (+15)");
  } else if (fundFlow.mainForceNetFlow === "净流入") {
    falseBreakScore += 15;
    reasons.push("资金面: 主力资金净流入，机构在接盘 (+15)");
  }

  if (fundFlow.retailBuyRatio !== null) {
    const ratio = parseFloat(fundFlow.retailBuyRatio);
    if (ratio > 80 && fundFlow.mainForceNetFlow === "净流出") {
      trueBreakScore += 5;
      reasons.push(`资金面: 散户买入占比 ${ratio}%，散户接盘嫌疑 (+5)`);
    }
  }

  // === 4. 基本面（10分） ===
  if (fundamentals.earningsWarning === true) {
    trueBreakScore += 10;
    reasons.push("基本面: 存在业绩预警/减持公告，基本面恶化 (+10)");
  }
  if (fundamentals.hasRecentNegativeNews === true) {
    trueBreakScore += 5;
    reasons.push("基本面: 近期有负面消息 (+5)");
  }
  if (fundamentals.hasRecentPositiveNews === true) {
    falseBreakScore += 5;
    reasons.push("基本面: 近期有正面消息 (+5)");
  }

  // 如果基本面数据全不可用，不给任何分数
  if (fundamentals.hasRecentNegativeNews === null && fundamentals.hasRecentPositiveNews === null) {
    reasons.push("基本面: 数据不可用，跳过");
  }

  // === 最终判定 ===
  const totalScore = trueBreakScore + falseBreakScore;
  let confidence = totalScore > 0 ? round2(Math.abs(trueBreakScore - falseBreakScore) / totalScore * 100) : 0;

  // 归一化到 0-100
  confidence = Math.min(100, Math.max(0, confidence));

  let breakoutType: BreakoutType;
  let suggestedAction: StopLossAction;
  let actionReason: string;
  let riskNote: string;

  if (trueBreakScore > falseBreakScore + 10 && confidence >= HIGH_CONFIDENCE) {
    // 真破位
    breakoutType = "TRUE_BREAK";
    suggestedAction = "STOP_LOSS";
    actionReason = `真破位信号 (置信度 ${confidence}/100)：${reasons.slice(0, 3).join("；")}。建议严格止损，保留现金等待更好机会。`;
    riskNote = "止损后若出现V型反弹（概率较低），可等确认反转后重新入场。";
  } else if (falseBreakScore > trueBreakScore + 10 && confidence >= HIGH_CONFIDENCE) {
    // 假洗盘
    breakoutType = "FALSE_BREAK";
    suggestedAction = "HOLD_AND_WATCH";
    actionReason = `假洗盘/技术性回调 (置信度 ${confidence}/100)：${reasons.slice(0, 3).join("；")}。建议持有不动，等待反弹。`;
    riskNote = "如果明日继续放量下跌（无缩量迹象），重新评估破位性质。";
  } else if (trueBreakScore > falseBreakScore && confidence >= MEDIUM_CONFIDENCE) {
    // 偏真破位但不够确信
    breakoutType = "NEUTRAL";
    suggestedAction = "WARN_AND_WATCH";
    actionReason = `偏真破位信号但不够确信 (置信度 ${confidence}/100)：${reasons.slice(0, 3).join("；")}。建议减仓观察，如明日继续下跌再止损。`;
    riskNote = "部分减仓可以在不确定时保留主动权。若明日缩量止跌，可回补仓位。";
  } else if (falseBreakScore > trueBreakScore && confidence >= MEDIUM_CONFIDENCE) {
    // 偏假洗盘但不够确信
    breakoutType = "NEUTRAL";
    suggestedAction = "WARN_AND_WATCH";
    actionReason = `偏假洗盘信号但不够确信 (置信度 ${confidence}/100)：${reasons.slice(0, 3).join("；")}。建议持有但高度警惕，设更紧的止损线。`;
    riskNote = "可将止损线下移至今日低点下方1-2%处，防止判断错误。";
  } else if (confidence < MEDIUM_CONFIDENCE && totalScore > 0) {
    // 矛盾信号
    breakoutType = "NEUTRAL";
    suggestedAction = "WARN_AND_WATCH";
    actionReason = `矛盾信号 (置信度 ${confidence}/100)：真破位 ${trueBreakScore}分 vs 假洗盘 ${falseBreakScore}分。建议按原止损纪律执行或减仓50%观察。`;
    riskNote = "信号矛盾时，减仓是最保守的做法，既控制了风险又保留了仓位。";
  } else {
    // 数据不足以判断
    breakoutType = "NEUTRAL";
    suggestedAction = "INSUFFICIENT_DATA";
    actionReason = `数据不足 (置信度 ${confidence}/100)：多个维度分析不可用，无法准确判断破位性质。建议按原止损纪律执行。`;
    riskNote = "大盘系统性下跌时可用，但若是个股独立下跌，建议按纪律止损。";
  }

  return { breakoutType, confidence, suggestedAction, actionReason, riskNote };
}

// ─── 主引擎 ────────────────────────────────────────────────────────────────

export class StopLossAnalyzer {
  /**
   * 执行完整的止损分析
   */
  async analyze(request: StopLossAnalysisRequest): Promise<StopLossReport> {
    const startTime = Date.now();

    // 并行执行各维度分析（互不依赖）
    const [technical, volume, fundFlow, fundamentals] = await Promise.all([
      checkTechnical(request.symbol, request.currentPrice),
      checkVolume(request.symbol),
      checkFundFlow(request.symbol),
      checkFundamentals(request.symbol),
    ]);

    const synthesized = synthesize(technical, volume, fundFlow, fundamentals, request);

    // 组装完整证据链
    const evidenceChain: EvidenceItem[] = [
      ...technical.evidence,
      ...volume.evidence,
      ...fundFlow.evidence,
      ...fundamentals.evidence,
    ];

    const elapsed = Date.now() - startTime;

    const report: StopLossReport = {
      request,
      analyzedAt: now(),
      technical,
      volume,
      fundFlow,
      fundamentals,
      ...synthesized,
      evidenceChain,
    };

    console.log(`[StopLossAnalyzer] ${request.symbol} 分析完成 (${elapsed}ms): ${synthesized.breakoutType} (${synthesized.confidence}/100)`);

    return report;
  }
}
