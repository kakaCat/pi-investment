/**
 * StopLossAlertService — 持仓止损预警
 *
 * 盘中定时检查所有持仓，计算相对均价的跌幅。
 * 触发止损条件时，**不直接发警报**，而是启动止损分析引擎做多维判断。
 * 产出分析报告后再通知用户，让决策有据可循。
 *
 * 工作流：
 *   原始价格到达止损线 → StopLossAnalyzer 分析（技术/量/资金/基本面）
 *   → 产出破位判定报告 → 用户收到的是分析报告，不是机械数字
 *
 * 触发时机：CronService 定时触发（CRON.json stop-loss-alert 任务）
 *
 * 去重机制：同一股票 30 分钟内不重复分析
 */
import { join } from "path";
import { readFileSync, existsSync } from "fs";
import { get_stock_realtime_price, get_hk_stock_price } from "../../infrastructure/akshare-ts/index.js";
import { StopLossAnalyzer } from "./stop-loss-analyzer-service.js";
import type { StopLossReport } from "../../types/stop-loss-analysis.js";

// ─── 常量 ──────────────────────────────────────────────────────────────────

const DEFAULT_STOP_LOSS_PCT = -8;  // 默认止损线：-8%
const DEDUP_INTERVAL_MS = 30 * 60 * 1000;  // 同一股票 30 分钟内不重复分析

// ─── 类型 ──────────────────────────────────────────────────────────────────

interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  market: "A" | "HK";
  notes: string;
}

interface PortfolioFile {
  holdings: Holding[];
}

/**
 * 分析后的结果
 */
interface AnalyzedAlert {
  symbol: string;
  name: string;
  currentPrice: number;
  avgCost: number;
  pnlPct: number;
  rawThreshold: number;          // 机械止损线
  report: StopLossReport;        // 分析报告
}

export interface AlertResult {
  triggered: boolean;            // 是否有需要提醒的
  alerts: AnalyzedAlert[];       // 分析后的警报列表
  skippedDedup: number;          // 去重跳过的数量
  summary: string;               // 格式化文本
}

// ─── 止损阈值解析 ──────────────────────────────────────────────────────────

/**
 * 从持仓备注中解析止损阈值。
 * 支持格式："止损8%"、"止损-8%"、"stop loss 10%"
 * 返回负数，如 -8。找不到则返回 DEFAULT_STOP_LOSS_PCT。
 */
function parseThreshold(notes: string): number {
  if (!notes) return DEFAULT_STOP_LOSS_PCT;
  const m = notes.match(/止损\s*-?(\d+(?:\.\d+)?)\s*%/);
  if (m) return -Math.abs(parseFloat(m[1]));
  return DEFAULT_STOP_LOSS_PCT;
}

// ─── 实时价格获取 ──────────────────────────────────────────────────────────

async function fetchCurrentPrice(symbol: string, market: "A" | "HK"): Promise<number | null> {
  try {
    const raw = market === "HK"
      ? await get_hk_stock_price(symbol)
      : await get_stock_realtime_price(symbol);
    const data = typeof raw === "string" ? JSON.parse(raw) : raw;
    const price = data?.current ?? data?.price ?? data?.close;
    return price != null && !isNaN(Number(price)) ? Number(price) : null;
  } catch {
    return null;
  }
}

/**
 * 格式化分析报告
 */
function formatReport(a: AnalyzedAlert): string {
  const r = a.report;
  const lines: string[] = [];

  lines.push(`\n${"═".repeat(55)}`);
  lines.push(`📊 止损分析报告: ${a.name} (${a.symbol})`);
  lines.push(`${"═".repeat(55)}`);

  // 价格信息
  lines.push(`\n📈 价格信息`);
  lines.push(`  当前价: ¥${a.currentPrice.toFixed(2)}`);
  lines.push(`  成本价: ¥${a.avgCost.toFixed(2)}`);
  lines.push(`  浮动盈亏: ${a.pnlPct >= 0 ? "+" : ""}${a.pnlPct.toFixed(2)}%`);
  lines.push(`  机械止损线: ¥${(-a.rawThreshold * a.avgCost / 100 + a.avgCost).toFixed(2)}`);

  // 破位判定
  const icons: Record<string, string> = {
    TRUE_BREAK: "🔴 真破位",
    FALSE_BREAK: "🟢 假洗盘",
    NEUTRAL: "🟡 中性",
  };
  lines.push(`\n🏷️  破位判定: ${icons[r.breakoutType] || r.breakoutType}`);
  lines.push(`  置信度: ${r.confidence}/100`);

  // 技术面
  lines.push(`\n🔧 技术面分析`);
  lines.push(`  趋势: ${r.technical.trend}${r.technical.trendConfirmed ? " (已确认)" : ""}`);
  if (r.technical.supportLevel) lines.push(`  关键支撑: ¥${r.technical.supportLevel}`);
  if (r.technical.resistanceLevel) lines.push(`  关键阻力: ¥${r.technical.resistanceLevel}`);
  if (r.technical.pattern) lines.push(`  K线形态: ${r.technical.pattern}`);
  if (r.technical.rsi !== null) lines.push(`  RSI-14: ${r.technical.rsi.toFixed(1)}`);
  if (r.technical.macdSignal) lines.push(`  MACD信号: ${r.technical.macdSignal}`);

  // 成交量
  lines.push(`\n📊 成交量分析`);
  if (r.volume.vsAvgVolume !== null) {
    lines.push(`  今日量 vs 20日均量: ${r.volume.vsAvgVolume}%`);
    if (r.volume.isShrink) lines.push(`  判定: 缩量 (假破位嫌疑)`);
    else if (r.volume.isVolumeSpike) lines.push(`  判定: 放量 (真破位信号)`);
    else lines.push(`  判定: 正常量`);
  } else {
    lines.push(`  数据不足`);
  }

  // 资金面
  if (r.fundFlow.mainForceNetFlow) {
    lines.push(`\n💰 资金面分析`);
    lines.push(`  主力资金: ${r.fundFlow.mainForceNetFlow}`);
    if (r.fundFlow.retailBuyRatio) lines.push(`  散户买入比: ${r.fundFlow.retailBuyRatio}`);
  }

  // 基本面
  if (r.fundamentals.newsSummary) {
    lines.push(`\n📰 基本面检查`);
    lines.push(`  ${r.fundamentals.newsSummary.slice(0, 120)}`);
  }

  // 建议
  const actionLabels: Record<string, string> = {
    STOP_LOSS: "⚠️ 建议立即止损",
    HOLD_AND_WATCH: "✅ 建议持有观察",
    WARN_AND_WATCH: "👀 建议高度警惕",
    INSUFFICIENT_DATA: "❓ 数据不足",
  };
  lines.push(`\n💡 ${actionLabels[r.suggestedAction] || r.suggestedAction}`);
  lines.push(`  原因: ${r.actionReason}`);

  if (r.riskNote) {
    lines.push(`\n⚠️  风险提示: ${r.riskNote}`);
  }

  // 证据链
  if (r.evidenceChain.length > 0) {
    lines.push(`\n📋 数据来源`);
    for (const e of r.evidenceChain.slice(0, 5)) {
      lines.push(`  [${e.source}] ${e.summary.slice(0, 100)}`);
    }
    if (r.evidenceChain.length > 5) {
      lines.push(`  ... 还有 ${r.evidenceChain.length - 5} 条证据`);
    }
  }

  lines.push(`\n${"═".repeat(55)}\n`);

  return lines.join("\n");
}

// ─── 主服务 ────────────────────────────────────────────────────────────────

export class StopLossAlertService {
  private portfolioFile: string;
  private analyzer: StopLossAnalyzer;

  /** 去重：记录每个股票的最后分析时间 */
  private lastAnalysisTime: Map<string, number> = new Map();

  constructor(piDir: string) {
    this.portfolioFile = join(piDir, "portfolio.json");
    this.analyzer = new StopLossAnalyzer();
  }

  /**
   * 检查是否需要跳过（去重）
   */
  private shouldSkip(symbol: string): boolean {
    const last = this.lastAnalysisTime.get(symbol);
    if (!last) return false;
    return Date.now() - last < DEDUP_INTERVAL_MS;
  }

  /**
   * 读取持仓文件，并行拉取实时价格，对触发止损的做分析。
   */
  async run(): Promise<AlertResult> {
    const holdings = this.loadHoldings();
    if (holdings.length === 0) {
      return { triggered: false, alerts: [], skippedDedup: 0, summary: "[止损预警] 暂无持仓，跳过检查" };
    }

    // 并行获取所有持仓的实时价格
    const priceResults = await Promise.allSettled(
      holdings.map(h => fetchCurrentPrice(h.symbol, h.market))
    );

    const alertPromises: Promise<AnalyzedAlert | null>[] = [];
    let skippedDedup = 0;
    const warnings: string[] = [];

    for (let i = 0; i < holdings.length; i++) {
      const h = holdings[i];
      const priceResult = priceResults[i];

      if (priceResult.status === "rejected" || priceResult.value === null) {
        warnings.push(`  ⚠️  ${h.name}（${h.symbol}）价格获取失败，跳过检查`);
        continue;
      }

      const currentPrice = priceResult.value;
      const pnlPct = ((currentPrice - h.avg_cost) / h.avg_cost) * 100;
      const threshold = parseThreshold(h.notes);

      // 只对达到止损线或接近止损线的持仓启动分析
      const isTriggered = pnlPct <= threshold;
      const isWarning = !isTriggered && pnlPct <= threshold + 2;

      if (!isTriggered && !isWarning) continue;

      // 去重检查
      if (this.shouldSkip(h.symbol)) {
        skippedDedup++;
        warnings.push(`  ⏭  ${h.name}（${h.symbol}）30分钟内已分析过，跳过`);
        continue;
      }

      // 标记去重时间
      this.lastAnalysisTime.set(h.symbol, Date.now());

      // 启动分析
      const promise = this.analyzeStock(h, currentPrice, threshold, isTriggered)
        .catch(err => {
          console.warn(`[StopLossAlert] ${h.symbol} 分析失败:`, err);
          return null;
        });
      alertPromises.push(promise);
    }

    // 等待所有分析完成
    const results = await Promise.all(alertPromises);
    const alerts = results.filter((r): r is AnalyzedAlert => r !== null);

    const summary = this.formatSummary(alerts, warnings, skippedDedup);
    return { triggered: alerts.length > 0, alerts, skippedDedup, summary };
  }

  /**
   * 对单只股票执行分析
   */
  private async analyzeStock(
    h: Holding,
    currentPrice: number,
    threshold: number,
    isTriggered: boolean,
  ): Promise<AnalyzedAlert | null> {
    const stopLossPrice = h.avg_cost * (1 + Math.abs(threshold) / 100);

    console.log(`[StopLossAlert] ${h.symbol} ${isTriggered ? "触发" : "接近"}止损，启动分析...`);

    try {
      const report = await this.analyzer.analyze({
        symbol: h.symbol,
        name: h.name,
        currentPrice,
        costPrice: h.avg_cost,
        stopLossPrice,
        market: h.market,
      });

      return {
        symbol: h.symbol,
        name: h.name,
        currentPrice,
        avgCost: h.avg_cost,
        pnlPct: ((currentPrice - h.avg_cost) / h.avg_cost) * 100,
        rawThreshold: threshold,
        report,
      };
    } catch (err) {
      console.warn(`[StopLossAlert] ${h.symbol} 分析异常，降级为纯数字止损:`, err);
      // 分析失败降级：仍返回一个报告吗？不，返回 null，
      // 让 formatSummary 知道数据不可用
      return null;
    }
  }

  private loadHoldings(): Holding[] {
    if (!existsSync(this.portfolioFile)) return [];
    try {
      const data: PortfolioFile = JSON.parse(readFileSync(this.portfolioFile, "utf-8"));
      return data.holdings ?? [];
    } catch {
      return [];
    }
  }

  private formatSummary(
    alerts: AnalyzedAlert[],
    warnings: string[],
    skippedDedup: number,
  ): string {
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const lines: string[] = [`\n${"═".repeat(55)}`, `[止损预警] ${now} 检查完毕 (去重跳过 ${skippedDedup} 次)`];

    if (alerts.length === 0 && warnings.length === 0) {
      lines.push("  ✅ 所有持仓均在止损线以上，无需操作");
      return lines.join("\n");
    }

    lines.push(`  本次分析 ${alerts.length} 只股票\n`);

    // 输出每只股票的分析报告
    for (const a of alerts) {
      lines.push(formatReport(a));
    }

    // 预警信息
    if (warnings.length > 0) {
      lines.push("\n📌 其他信息\n");
      lines.push(...warnings);
    }

    return lines.join("\n");
  }
}
