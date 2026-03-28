/**
 * StopLossAlertService - 持仓止损预警
 *
 * 盘中定时检查所有持仓，计算相对均价的跌幅。
 * 超过阈值时在终端打印红色警报，提示用户检查止损。
 *
 * 触发时机：CronService 定时触发（CRON.json stop-loss-alert 任务）
 *
 * 止损阈值（优先级从高到低）：
 *   1. 持仓 notes 字段中的 "止损X%" 标注，e.g. "止损8%"
 *   2. 全局默认值 DEFAULT_STOP_LOSS_PCT（默认 -8%）
 */
import { join } from "path";
import { readFileSync, existsSync } from "fs";
import { get_stock_realtime_price, get_hk_stock_price } from "../../infrastructure/akshare-ts/index.js";

// ─── 常量 ──────────────────────────────────────────────────────────────────

const DEFAULT_STOP_LOSS_PCT = -8;  // 默认止损线：-8%

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

export interface AlertResult {
  triggered: boolean;           // 是否有触发警报的持仓
  alerts: StopLossAlert[];      // 触发止损的持仓列表
  summary: string;              // 供终端输出的格式化文本
}

interface StopLossAlert {
  symbol: string;
  name: string;
  current_price: number;
  avg_cost: number;
  pnl_pct: number;            // 当前跌幅（负数）
  threshold_pct: number;      // 止损阈值（负数）
  distance_to_threshold: number; // 距止损线还有多少百分比
}

// ─── 止损阈值解析 ──────────────────────────────────────────────────────────

/**
 * 从持仓备注中解析止损阈值。
 * 支持格式："止损8%"、"止损-8%"、"stop loss 10%"
 * 返回负数，如 -8。找不到则返回 DEFAULT_STOP_LOSS_PCT。
 */
function parseThreshold(notes: string): number {
  if (!notes) return DEFAULT_STOP_LOSS_PCT;
  // 匹配 "止损8%" / "止损-8%" / "止损 10%"
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

// ─── 主服务 ────────────────────────────────────────────────────────────────

export class StopLossAlertService {
  private portfolioFile: string;

  constructor(piDir: string) {
    this.portfolioFile = join(piDir, "portfolio.json");
  }

  /**
   * 读取持仓文件，并行拉取实时价格，检查是否触发止损。
   */
  async run(): Promise<AlertResult> {
    const holdings = this.loadHoldings();
    if (holdings.length === 0) {
      return { triggered: false, alerts: [], summary: "[止损预警] 暂无持仓，跳过检查" };
    }

    // 并行获取所有持仓的实时价格
    const priceResults = await Promise.allSettled(
      holdings.map(h => fetchCurrentPrice(h.symbol, h.market))
    );

    const alerts: StopLossAlert[] = [];
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

      if (pnlPct <= threshold) {
        alerts.push({
          symbol: h.symbol,
          name: h.name,
          current_price: currentPrice,
          avg_cost: h.avg_cost,
          pnl_pct: pnlPct,
          threshold_pct: threshold,
          distance_to_threshold: 0,
        });
      } else if (pnlPct <= threshold + 2) {
        // 距止损线 2% 以内：预警（非触发）
        alerts.push({
          symbol: h.symbol,
          name: h.name,
          current_price: currentPrice,
          avg_cost: h.avg_cost,
          pnl_pct: pnlPct,
          threshold_pct: threshold,
          distance_to_threshold: pnlPct - threshold,
        });
      }
    }

    const summary = this.formatSummary(alerts, warnings);
    return { triggered: alerts.some(a => a.distance_to_threshold === 0), alerts, summary };
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

  private formatSummary(alerts: StopLossAlert[], warnings: string[]): string {
    const now = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const lines: string[] = [`\n${"═".repeat(55)}`, `[止损预警] ${now} 检查完毕`];

    if (alerts.length === 0 && warnings.length === 0) {
      lines.push("  ✅ 所有持仓均在止损线以上，无需操作");
    }

    for (const a of alerts) {
      const pct = a.pnl_pct.toFixed(2);
      const thresh = a.threshold_pct.toFixed(0);
      if (a.distance_to_threshold === 0) {
        // 已触发止损
        lines.push(
          `  🔴 【止损触发】${a.name}（${a.symbol}）`,
          `       当前价 ${a.current_price.toFixed(2)}  均价 ${a.avg_cost.toFixed(2)}  跌幅 ${pct}%  止损线 ${thresh}%`,
          `       → 建议立即检查是否止损出场`
        );
      } else {
        // 接近止损线
        lines.push(
          `  🟡 【接近止损】${a.name}（${a.symbol}）`,
          `       当前跌幅 ${pct}%，距止损线 ${a.distance_to_threshold.toFixed(1)}%（止损线 ${thresh}%）`,
          `       → 请留意走势`
        );
      }
    }

    if (warnings.length > 0) {
      lines.push(...warnings);
    }

    lines.push("═".repeat(55));
    return lines.join("\n");
  }
}
