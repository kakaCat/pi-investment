/**
 * DailyReviewService - 每日持仓复盘
 *
 * 不走 Agent Loop，直接调用量化 CLI 获取数据，生成结构化复盘报告。
 * 报告同时：
 *   1. 打印到终端（当用户启动 app 时可见）
 *   2. 存入每日记忆文件 .pi-invest/memory/daily/YYYY-MM-DD.jsonl
 *   3. 存入复盘报告 .pi-invest/reviews/YYYY-MM-DD.md
 *
 * 触发时机：
 *   - 启动时自动检测（A股收盘后 15:30+，工作日）
 *   - CronService 定时触发（CRON.json daily-review 任务）
 */
import { callQuantSysDaemon } from "../../infrastructure/quant/quantsys-daemon-adapter.js";
import { writeFileSync, readFileSync, existsSync, mkdirSync, appendFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { chinaDate, chinaHourMinute, chinaTime, chinaWeekday } from "../../utils/china-time.js";

// ─── 工具函数 ─────────────────────────────────────────────────────────────

function today(): string {
  return chinaDate();
}

function isWeekday(): boolean {
  const d = chinaWeekday();
  return d >= 1 && d <= 5;
}

function isAfterMarketClose(): boolean {
  const { hour: h, minute: m } = chinaHourMinute();
  return h > 15 || (h === 15 && m >= 30);
}

function safeJson(raw: string): Record<string, unknown> {
  try { return JSON.parse(raw); } catch { return { error: raw }; }
}

function fmt(v: unknown, dec = 2): string {
  if (v === null || v === undefined || v === "") return "N/A";
  const n = Number(v);
  return isNaN(n) ? String(v) : n.toFixed(dec);
}

function pctSign(v: unknown): string {
  const n = Number(v);
  if (isNaN(n)) return "N/A";
  return n >= 0 ? `+${n.toFixed(2)}%` : `${n.toFixed(2)}%`;
}

// ─── 持仓结构 ──────────────────────────────────────────────────────────────

interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  cost: number;
  market: "A" | "HK";
}

export function formatReviewNewsSection(news: Record<string, unknown>): string {
  const items = Array.isArray(news.data)
    ? news.data
    : Array.isArray(news.news)
      ? news.news
      : [];

  if (items.length === 0) return "- 无最新公告/新闻";

  return (items as Array<{ title?: string; date?: string }>)
    .slice(0, 3)
    .map((n) => `  - ${n.title ?? "无标题"}（${n.date ?? ""}）`)
    .join("\n");
}

export function formatMarketOverviewSection(data: Record<string, unknown>): string {
  if (data.error) return "- 大盘数据不可用";

  const rawIndices = data.indices;
  const entries = Array.isArray(rawIndices)
    ? rawIndices
    : Object.entries((rawIndices as Record<string, Record<string, unknown>>) ?? {}).map(([name, value]) => ({
        name,
        current: value?.current ?? value?.price,
        change_pct: value?.change_pct ?? value?.change_rate,
      }));

  if (entries.length === 0) return "- 大盘数据不可用";

  return entries.slice(0, 4).map((i) =>
    `- ${String(i.name ?? "")}：${fmt((i as Record<string, unknown>).current)} （${pctSign((i as Record<string, unknown>).change_pct)}）`
  ).join("\n");
}

// ─── 单股复盘 ──────────────────────────────────────────────────────────────

async function reviewHolding(h: Holding): Promise<string> {
  // 并行获取：价格 + 技术指标 + 新闻
  const pricePromise = callQuantSysDaemon("get_stock_realtime_price", { symbol: h.symbol });
  const techPromise = h.market === "HK"
    ? Promise.resolve(JSON.stringify({ unsupported: true }))
    : callQuantSysDaemon("calculate_technical_indicators", { symbol: h.symbol });
  const newsPromise = h.market === "HK"
    ? Promise.resolve(JSON.stringify({ unsupported: true }))
    : Promise.resolve(JSON.stringify({ unsupported: true })); // 每日复盘暂不拉取新闻，避免放大启动成本。

  const [priceRaw, techRaw, newsRaw] = await Promise.all([pricePromise, techPromise, newsPromise]);

  const price = safeJson(priceRaw);
  const tech  = safeJson(techRaw);
  const news  = safeJson(newsRaw);

  // ── 价格与盈亏 ─────────────────────────────────────────────────────────
  const curPrice   = Number(price.current_price ?? price.price ?? 0);
  const changeRate = Number(price.change_pct ?? price.change_rate ?? price.pct_chg ?? 0);
  const pnlPct     = h.cost > 0 ? ((curPrice - h.cost) / h.cost) * 100 : 0;
  const pnlAmt     = (curPrice - h.cost) * h.quantity;
  const pnlSign    = pnlPct >= 0 ? "+" : "";

  const priceSection = `- 当前价：${fmt(curPrice)} 元  今日：${pctSign(changeRate)}
- 持仓：${h.quantity}股 × 成本 ${fmt(h.cost)}  盈亏：${pnlSign}${pnlPct.toFixed(2)}%（${pnlSign}${pnlAmt.toFixed(0)} 元）`;

  // ── 技术信号 ───────────────────────────────────────────────────────────
  let techSection = h.market === "HK" ? "- 港股复盘暂不提供技术指标" : "- 技术数据不可用";
  if (!tech.error && !tech.unsupported) {
    const ma20  = fmt(tech.ma20);
    const ma60  = fmt(tech.ma60);
    const rsi   = fmt(tech.rsi);
    const macdH = Number(tech.macd_histogram ?? 0);
    const trend = Number(tech.ma20 ?? 0) > Number(tech.ma60 ?? 0) ? "多头" : "空头";
    const macdSignal = macdH > 0 ? "金叉区域" : "死叉区域";
    const rsiVal = Number(tech.rsi ?? 50);
    const rsiLabel = rsiVal > 70 ? "⚠️ 超买" : rsiVal < 30 ? "⚠️ 超卖" : "正常";
    techSection = `- 趋势：MA20(${ma20}) vs MA60(${ma60}) → **${trend}**
- MACD：${macdSignal}（柱：${fmt(macdH, 4)}）
- RSI：${rsi}（${rsiLabel}）`;
  }

  // ── 新闻摘要 ───────────────────────────────────────────────────────────
  const newsSection = h.market === "HK"
    ? "- 港股复盘暂不拉取 A 股新闻源"
    : formatReviewNewsSection(news);

  // ── 操作建议 ───────────────────────────────────────────────────────────
  let advice = "持有";
  const macdOk = Number(tech.macd_histogram ?? 0) > 0;
  const rsiV   = Number(tech.rsi ?? 50);
  if (pnlPct < -8) advice = "⚠️ 考虑止损（亏损超8%）";
  else if (h.market === "HK") advice = "结合港股流动性与基本面手动复核";
  else if (rsiV > 75) advice = "注意超买，可减仓";
  else if (rsiV < 30 && macdOk) advice = "超卖+MACD金叉，可逢低补仓";
  else if (pnlPct > 30 && !macdOk) advice = "盈利丰厚+MACD弱，可部分止盈";

  return `### ${h.name}（${h.symbol}）
${priceSection}
${techSection}
**新闻**：
${newsSection}
💡 **操作建议**：${advice}`;
}

// ─── 大盘概览 ──────────────────────────────────────────────────────────────

async function marketOverview(): Promise<string> {
  const raw = await callQuantSysDaemon("get_market_overview");
  const data = safeJson(raw);
  return formatMarketOverviewSection(data);
}

// ─── 核心复盘流程 ─────────────────────────────────────────────────────────

export class DailyReviewService {
  private reviewsDir: string;
  private dailyMemDir: string;

  constructor(private piDir: string) {
    this.reviewsDir = join(piDir, "reviews");
    this.dailyMemDir = join(piDir, "memory", "daily");
    mkdirSync(this.reviewsDir, { recursive: true });
    mkdirSync(this.dailyMemDir, { recursive: true });
  }

  private loadPortfolio(): Record<string, unknown> {
    const portfolioPath = join(this.piDir, "portfolio.json");
    if (!existsSync(portfolioPath)) return { holdings: [] };
    return safeJson(readFileSync(portfolioPath, "utf-8"));
  }

  /** 今日复盘是否已完成 */
  isReviewDone(): boolean {
    return existsSync(join(this.reviewsDir, `${today()}.md`));
  }

  /** 是否应该自动触发复盘（工作日 15:30 后且今日未做） */
  shouldAutoRun(): boolean {
    return isWeekday() && isAfterMarketClose() && !this.isReviewDone();
  }

  /** 执行复盘，返回 markdown 报告 */
  async run(): Promise<string> {
    const date = today();
    console.log(`\n[复盘] 开始执行每日持仓复盘（${date}）...\n`);

    // 1. 获取持仓
    const portfolio = this.loadPortfolio();
    const holdings: Holding[] = [];

    if (!portfolio.error && Array.isArray(portfolio.holdings)) {
      for (const h of portfolio.holdings as Array<Record<string, unknown>>) {
        const symbol = String(h.symbol ?? h.code ?? "");
        if (!symbol) continue;
        holdings.push({
          symbol,
          name: String(h.name ?? symbol),
          quantity: Number(h.quantity ?? h.shares ?? 0),
          cost: Number(h.avg_cost ?? h.cost ?? 0),
          market: String(h.market ?? "A").toUpperCase() === "HK" ? "HK" : "A",
        });
      }
    }

    if (holdings.length === 0) {
      const msg = `# 每日复盘 ${date}\n\n> 持仓为空，无需复盘。\n`;
      this.save(date, msg);
      return msg;
    }

    // 2. 并行获取大盘 + 所有持仓数据
    const [marketSection, ...holdingSections] = await Promise.all([
      marketOverview(),
      ...holdings.map(h => reviewHolding(h)),
    ]);

    // 3. 组装报告
    const time = chinaTime(new Date(), false);
    const report = [
      `# 每日复盘 ${date} ${time}`,
      "",
      `## 📊 大盘情况`,
      marketSection,
      "",
      `## 🔴🟢 持仓复盘（${holdings.length}只）`,
      "",
      holdingSections.join("\n\n---\n\n"),
      "",
      "---",
      "> ⚠️ 以上复盘仅供参考，不构成投资建议。",
    ].join("\n");

    this.save(date, report);
    return report;
  }

  /** 读取指定日期复盘（默认今日），返回 markdown 字符串或 null */
  readReview(date?: string): string | null {
    const d = date ?? today();
    const f = join(this.reviewsDir, `${d}.md`);
    if (!existsSync(f)) return null;
    return readFileSync(f, "utf-8");
  }

  /** 列出最近 N 天有复盘记录的日期（倒序） */
  listReviews(limit = 7): Array<{ date: string; size: number }> {
    try {
      const files = readdirSync(this.reviewsDir)
        .filter((f) => f.endsWith(".md"))
        .sort()
        .reverse()
        .slice(0, limit);
      return files.map((f) => ({
        date: f.replace(".md", ""),
        size: statSync(join(this.reviewsDir, f)).size,
      }));
    } catch {
      return [];
    }
  }

  /** 读取今日每日记忆 JSONL，判断是否有复盘条目 */
  todayMemoryHasReview(): boolean {
    const memFile = join(this.dailyMemDir, `${today()}.jsonl`);
    if (!existsSync(memFile)) return false;
    return readFileSync(memFile, "utf-8").includes('"category":"daily_review"');
  }

  /** 保存复盘报告到文件和每日记忆 */
  private save(date: string, report: string): void {
    // 复盘报告文件
    const reviewFile = join(this.reviewsDir, `${date}.md`);
    writeFileSync(reviewFile, report, "utf-8");

    // 写入每日记忆（一条 jsonl 记录）
    const memFile = join(this.dailyMemDir, `${date}.jsonl`);
    const entry = JSON.stringify({
      timestamp: new Date().toISOString(),
      category: "daily_review",
      content: `每日复盘完成（${date}）。报告已保存至 ${reviewFile}。\n\n${report.slice(0, 800)}...`,
    });
    appendFileSync(memFile, entry + "\n", "utf-8");

    console.log(`[复盘] 报告已保存：${reviewFile}\n`);
  }
}
