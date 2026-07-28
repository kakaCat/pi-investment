/**
 * Portfolio Daily Brief Tool - 虚拟仓每日对账单
 *
 * 一个入口回答"我昨天做得对不对"：
 *   昨日操作 → 今日验证结果 → 持仓健康度 → 基准标尺 → 一句话结论
 * 复盘入口越短，复盘才会真的发生。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { getAccount, getAccountTrades } from "../../adapters/quant/quant-v2-client.js";
import { computePortfolioView, type PortfolioView } from "./portfolio-status-tool.js";

const V2_API_BASE = process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";

interface DailyBriefInput {
  account?: string;
}

export interface DailyBrief {
  success: true;
  account: string;
  date: string;
  one_liner: string;
  no_trade_hint: string;
  summary: string;
}

export interface DailyBriefParams {
  account: string;
  today: string; // YYYY-MM-DD
  view: PortfolioView;
  decisions: any[];
  trades: any[];
}

function dateOf(s: any): string {
  return String(s ?? "").slice(0, 10);
}

function yesterdayOf(today: string): string {
  // 纯日期运算，避免本地时区经 toISOString 转 UTC 导致日期回退
  const [y, m, d] = today.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() - 1);
  return dt.toISOString().slice(0, 10);
}

/** 纯函数：把账户视图 + 决策 + 成交组装为对账单（便于单测） */
export function buildDailyBrief(params: DailyBriefParams): DailyBrief {
  const { account, today, view, decisions, trades } = params;
  const yesterday = yesterdayOf(today);

  const yesterdayTrades = trades.filter(t => dateOf(t.trade_date ?? t.timestamp) === yesterday);
  const yesterdayDecisions = decisions.filter(d => dateOf(d.created_at) === yesterday);

  // 一、昨日操作
  const opLines = yesterdayTrades.length > 0
    ? yesterdayTrades.map(t =>
        `  - ${t.action} ${t.symbol} ${t.shares ?? "?"}股 @${t.price ?? t.filled_price ?? "?"}（${t.reason ?? "无理由记录"}）`)
    : ["  - 昨日无成交"];

  // 二、今日验证：昨日买入的票今天表现
  const verifyLines: string[] = [];
  for (const t of yesterdayTrades.filter(t => String(t.action).toUpperCase() === "BUY")) {
    const h = view.holdings.find(h => h.symbol === t.symbol);
    if (h) {
      const mark = h.pnl_pct >= 0 ? "✓" : "✗";
      verifyLines.push(`  - ${t.symbol}: 买入价 ${t.price ?? t.filled_price} → 现价 ${h.current_price}（${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%）${mark}`);
    } else {
      verifyLines.push(`  - ${t.symbol}: 已不在持仓中（可能已卖出或成交失败，请用 trade_monitor 核对）`);
    }
  }
  if (verifyLines.length === 0) verifyLines.push("  - 无昨日买入需要验证");

  // 三、持仓健康度
  const healthLines = [
    `  - 持仓 ${view.holdings_count} 只，市值 ¥${view.total_market_value.toFixed(2)}，总盈亏 ${view.total_pnl_pct.toFixed(2)}%`,
  ];
  for (const h of view.holdings) {
    const warn = h.pnl_pct <= -5 ? "⚠️ 触及止损线" : h.pnl_pct >= 10 ? "🎯 触及止盈线" : "";
    healthLines.push(`  - ${h.symbol}: ${h.pnl_pct >= 0 ? "+" : ""}${h.pnl_pct.toFixed(2)}%（持有${h.days_held ?? "?"}天）${warn}`);
  }
  if (view.price_stale) healthLines.push("  ⚠️ 行情获取失败，价格为陈旧数据，以上盈亏不可信");

  // 四、基准标尺
  const benchLines: string[] = [];
  if (view.benchmark) {
    const b = view.benchmark;
    benchLines.push(
      `  - 近30日：账户 ${(b.account_return_1m * 100).toFixed(2)}% vs ${b.benchmark_name ?? "沪深300"} ${(b.benchmark_return_1m * 100).toFixed(2)}%（超额 ${(b.excess_return_1m * 100).toFixed(2)}%）`
    );
  }

  // 一句话结论
  const verdicts: string[] = [];
  const yesterdayBuys = yesterdayTrades.filter(t => String(t.action).toUpperCase() === "BUY");
  if (yesterdayBuys.length > 0) {
    const bought = yesterdayBuys.map(t => view.holdings.find(h => h.symbol === t.symbol)).filter(Boolean) as NonNullable<typeof view.holdings[number]>[];
    if (bought.length > 0 && bought.every(h => h.pnl_pct >= 0)) {
      verdicts.push("昨日买入方向正确，目前浮盈");
    } else if (bought.some(h => h.pnl_pct < 0)) {
      verdicts.push("昨日买入有浮亏，检查买入逻辑是否仍成立");
    }
  }
  if (view.benchmark && view.benchmark.excess_return_1m < 0) {
    verdicts.push(`近30日跑输沪深300 ${(Math.abs(view.benchmark.excess_return_1m) * 100).toFixed(2)}%，需要检讨仓位或选股`);
  } else if (view.benchmark && view.benchmark.excess_return_1m > 0) {
    verdicts.push(`近30日跑赢沪深300 ${(view.benchmark.excess_return_1m * 100).toFixed(2)}%，策略有效`);
  }
  if (view.holdings_count === 0 && yesterdayTrades.length === 0) {
    verdicts.push("空仓等待中——确认这是主动选择而不是错过信号");
  }
  const oneLiner = verdicts.length > 0 ? verdicts.join("；") : "无重大发现，继续观察";

  const noTradeHint = "今日选择不交易也是合法决策——用 decision_record 记录一条'不交易'决策并写明理由，明日对账单会同样验证它";

  const summary = [
    `📋 每日对账单（${account}，${today}）`,
    "",
    "一、昨日操作",
    ...opLines,
    `  （昨日决策记录 ${yesterdayDecisions.length} 条）`,
    "",
    "二、今日验证",
    ...verifyLines,
    "",
    "三、持仓健康度",
    ...healthLines,
    ...(benchLines.length > 0 ? ["", "四、基准标尺", ...benchLines] : []),
    "",
    `一句话结论：${oneLiner}`,
    "",
    `💡 ${noTradeHint}`,
  ].join("\n");

  return { success: true, account, date: today, one_liner: oneLiner, no_trade_hint: noTradeHint, summary };
}

async function fetchRecentDecisions(limit = 50): Promise<any[]> {
  const resp = await fetch(`${V2_API_BASE}/api/decisions/history?limit=${limit}`);
  const result = (await resp.json()) as any;
  if (!result.success) throw new Error(result.error || "查询决策历史失败");
  return result.data || [];
}

export const portfolioDailyBriefTool: ToolDefinition = {
  name: "portfolio_daily_brief",
  label: "每日对账单",
  description:
    "生成虚拟仓每日对账单：昨日操作 → 今日验证 → 持仓健康度 → 基准标尺 → 一句话结论。" +
    "复盘专用入口，一次调用替代 decision_history + portfolio_status + trade_monitor 的组合。" +
    "不交易也是合法决策——简报会提示用 decision_record 记录'不交易'理由。",

  parameters: Type.Object({
    account: Type.Optional(Type.String({
      description: "账户名，默认 agent_virtual",
      default: "agent_virtual",
    })),
  }),

  execute: async (toolCallId: string, input: DailyBriefInput) => {
    return wrapToolExecution(
      async () => {
        const account = input.account ?? "agent_virtual";
        const [accountData, trades, decisions] = await Promise.all([
          getAccount(account),
          getAccountTrades(account, 50),
          fetchRecentDecisions(50),
        ]);
        const view = computePortfolioView(accountData);
        const today = new Date().toISOString().slice(0, 10);
        return buildDailyBrief({ account, today, view, decisions, trades });
      },
      { toolName: "portfolio_daily_brief" }
    );
  }
};
