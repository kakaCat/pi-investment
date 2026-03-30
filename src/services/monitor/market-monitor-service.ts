/**
 * MarketMonitorService - 实时盯盘服务
 */
import { getSession } from "../../core/agent/agent-loop.js";
import { PortfolioService } from "../portfolio/portfolio-service.js";
import { get_stock_realtime_price } from "../../infrastructure/akshare-ts/index.js";
import { quickFilter, type Quote } from "./market-filter.js";
import { paths } from "../../config/config.js";

const MONITOR_SYSTEM_PROMPT = `你是实时盯盘助手。

职责：
1. 分析市场和持仓，判断是否有交易信号
2. 根据市场状态决定下次检查时间

决策逻辑：
- 发现明确信号 → send_feishu_alert + schedule_next_check(30, "已发信号，等待执行")
- 接近关键位 → schedule_next_check(1, "接近支撑位，密切关注")
- 市场活跃但无信号 → schedule_next_check(5, "市场波动，保持关注")
- 市场平淡 → schedule_next_check(30, "市场平淡")

信号标准：
- 置信度 >= 0.7
- 有明确的技术面+基本面支撑
- 理由具体可执行`;

export class MarketMonitorService {
  private portfolioService: PortfolioService;

  constructor() {
    this.portfolioService = new PortfolioService(paths.piDir);
  }

  async tick(): Promise<void> {
    console.log('[Monitor] 开始盯盘检查...');

    const snapshot = await this.portfolioService.getWithPnL();
    const holdings = snapshot.holdings;

    if (holdings.length === 0) {
      console.log('[Monitor] 无持仓，跳过');
      return;
    }

    const quotes = await this.fetchQuotes(holdings.map(h => h.symbol));
    const filter = quickFilter(quotes);

    if (!filter.needsAgentAnalysis) {
      console.log('[Monitor] 市场平淡，30分钟后再检查');
      return;
    }

    const context = this.buildContext(holdings, filter);
    console.log(`[Monitor] 市场活跃度: ${filter.urgency}/3，调用 Agent 分析...`);

    const session = await getSession();
    await session.prompt(context);
  }

  private async fetchQuotes(symbols: string[]): Promise<Quote[]> {
    const quotes: Quote[] = [];
    for (const symbol of symbols) {
      try {
        const data = JSON.parse(await get_stock_realtime_price(symbol));
        if (data.price) {
          quotes.push({
            symbol,
            name: data.name || symbol,
            price: data.price,
            change_pct: data.change_pct || 0,
            volume: data.volume || 0,
            avg_volume: data.volume
          });
        }
      } catch (e) {
        console.warn(`[Monitor] 获取 ${symbol} 行情失败`);
      }
    }
    return quotes;
  }

  private buildContext(holdings: any[], filter: any): string {
    return `当前市场状态：
- 紧急度：${filter.urgency}/3
- 高波动股票：${filter.signals.high_volatility.length} 只
- 放量股票：${filter.signals.high_volume.length} 只

持仓情况（${holdings.length} 只）：
${holdings.map((h: any) => `- ${h.name}(${h.symbol}): ${h.quantity}股 @ ¥${h.cost.toFixed(2)}, 当前 ¥${h.current_price?.toFixed(2) || 'N/A'}, 盈亏 ${h.pnl_pct?.toFixed(2) || 'N/A'}%`).join('\n')}

请分析是否有交易信号，并决定下次检查时间。`;
  }
}
