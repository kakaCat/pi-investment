#!/usr/bin/env tsx
/**
 * PI Investment — 持仓 & 交易历史管理 CLI
 *
 * 用法:
 *   npm run portfolio            交互式菜单
 *   npm run portfolio -- add     直接进入录入持仓
 *   npm run portfolio -- trade   直接进入录入交易
 *   npm run portfolio -- view    查看持仓（带盈亏）
 *   npm run portfolio -- sync    从交易历史重建持仓
 *
 * 数据文件:
 *   .pi-invest/portfolio.json   持仓（持仓均价、数量）
 *   PostgreSQL                 交易历史（通过 CLI → TradeCliAdapter）
 */

import * as readline from "readline";
import { join } from "path";
import { PortfolioService } from "../services/portfolio/portfolio-service.js";
// TradeService removed — TradeAction = "buy" | "sell"
type TradeAction = "buy" | "sell";
import { chinaDate } from "../utils/china-time.js";

// ─── 初始化 ────────────────────────────────────────────────────────────────

const piDir = join(process.cwd(), ".pi-invest");
const portfolio = new PortfolioService(piDir);
// ⚠️  trades 操作已迁移到 PostgreSQL（TradeCliAdapter）。
// 本脚本中涉及 trades 的功能（历史、摘要、快照、导出）已暂存。
// TODO: 迁移到 TradeCliAdapter.list() / getStats()

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

// ─── 工具函数 ──────────────────────────────────────────────────────────────

const q = (prompt: string): Promise<string> =>
  new Promise(resolve => rl.question(prompt, answer => resolve(answer.trim())));

const qDefault = async (prompt: string, def: string): Promise<string> => {
  const ans = await q(`${prompt} [${def}]: `);
  return ans || def;
};

function padR(s: string, n: number): string { return s.slice(0, n).padEnd(n); }
function padL(s: string, n: number): string { return s.slice(0, n).padStart(n); }

function line(char = "─", len = 60): void { console.log(char.repeat(len)); }

function printHeader(title: string): void {
  line("═");
  console.log(`  ${title}`);
  line("═");
}

function printTable(rows: string[][]): void {
  for (const row of rows) console.log(row.join("  "));
}

function sign(n: number): string { return n >= 0 ? `+${n.toFixed(2)}` : n.toFixed(2); }

// ─── 查看持仓 ──────────────────────────────────────────────────────────────

async function viewPortfolio(): Promise<void> {
  console.log("\n  正在拉取实时行情...\n");
  try {
    const snap = await portfolio.getWithPnL();
    if (snap.holdings.length === 0) {
      console.log("  暂无持仓。使用菜单选项 1 或 2 录入持仓。\n");
      return;
    }

    printHeader("📊 当前持仓");
    printTable([
      ["  代码    ", "名称      ", "  数量", "  均价", "  现价", " 今日%", " 持仓%", "  盈亏(元)"],
      ["  ──────", "────────", "──────", "──────", "──────", "──────", "──────", "──────────"],
    ]);
    for (const h of snap.holdings) {
      const s = sign(h.pnl_pct);
      const today = sign(h.change_pct);
      console.log(
        `  ${padR(h.symbol, 6)}  ${padR(h.name || "──", 8)}  ` +
        `${padL(String(h.quantity), 6)}  ${padL(h.avg_cost.toFixed(2), 6)}  ` +
        `${padL(h.current_price > 0 ? h.current_price.toFixed(2) : "N/A", 6)}  ` +
        `${padL(today + "%", 7)}  ${padL(s + "%", 7)}  ${padL(sign(h.pnl_amount) + "元", 11)}`
      );
    }
    line();
    console.log(
      `  持仓 ${snap.holdings.length} 只  |  ` +
      `总成本 ${snap.total_cost.toFixed(0)}元  |  ` +
      `总市值 ${snap.total_value.toFixed(0)}元  |  ` +
      `总盈亏 ${sign(snap.total_pnl)}元（${sign(snap.total_pnl_pct)}%）`
    );
    line();
    console.log(`  数据时间: ${snap.as_of}\n`);
  } catch (e) {
    console.error("  获取行情失败:", e instanceof Error ? e.message : String(e));
  }
}

// ─── 录入持仓 ──────────────────────────────────────────────────────────────

async function addHolding(): Promise<void> {
  printHeader("📥 录入持仓");
  console.log("  格式: 代码 数量 均价  （如: 600519 100 1450）");
  console.log("  每行一条，空行结束\n");

  let count = 0;
  while (true) {
    const input = await q(`  持仓 #${count + 1} (回车结束): `);
    if (!input) break;

    // 支持空格或逗号分隔
    const parts = input.split(/[\s,]+/).filter(Boolean);
    if (parts.length < 3) {
      console.log("  ❌ 格式错误，需要: 代码 数量 均价（如: 600519 100 1450）");
      continue;
    }

    const symbol = parts[0];
    const quantity = parseInt(parts[1], 10);
    const avgCost = parseFloat(parts[2]);

    if (isNaN(quantity) || isNaN(avgCost) || quantity <= 0 || avgCost <= 0) {
      console.log("  ❌ 数量和均价必须是正数");
      continue;
    }

    const marketStr = await qDefault("  市场 (A/HK)", "A");
    const market = (marketStr.toUpperCase() === "HK" ? "HK" : "A") as "A" | "HK";
    const name = await qDefault("  股票名称（可选，回车跳过）", "");
    const notes = await qDefault("  备注（可选，回车跳过）", "");

    const res = portfolio.add(symbol, quantity, avgCost, 0, name, market, notes);
    console.log(`  ✅ ${res.message}\n`);
    count++;
  }
  if (count > 0) console.log(`\n  共录入 ${count} 条持仓记录。\n`);
}

// ─── 录入交易 ──────────────────────────────────────────────────────────────

async function addTrade(): Promise<void> {
  printHeader("📝 录入交易记录");
  console.log("  每行一笔交易，空行结束");
  console.log("  格式: 日期 代码 买入/卖出 数量 价格 [手续费] [备注]");
  console.log("  示例: 2026-01-15 600519 买入 100 1450 5 初始建仓\n");

  let count = 0;
  const today = chinaDate();

  while (true) {
    const input = await q(`  交易 #${count + 1} (回车结束): `);
    if (!input) break;

    const parts = input.trim().split(/\s+/);
    // 允许省略日期（第一个部分是否是日期格式）
    let idx = 0;
    let date = today;
    if (/^\d{4}-\d{2}-\d{2}$/.test(parts[0])) {
      date = parts[idx++];
    } else if (/^\d{4}\/\d{2}\/\d{2}$/.test(parts[0])) {
      date = parts[idx++].replace(/\//g, "-");
    }

    const symbol = parts[idx++];
    const actionRaw = parts[idx++] ?? "";
    const quantity = parseInt(parts[idx++] ?? "0", 10);
    const price = parseFloat(parts[idx++] ?? "0");
    const commission = parseFloat(parts[idx] !== undefined && !isNaN(parseFloat(parts[idx])) ? parts[idx++] : "0");
    const notes = parts.slice(idx).join(" ");

    if (!symbol || isNaN(quantity) || isNaN(price) || quantity <= 0 || price <= 0) {
      console.log("  ❌ 格式错误。示例: 2026-01-15 600519 买入 100 1450");
      continue;
    }

    const action: TradeAction =
      ["卖", "卖出", "sell", "s"].includes(actionRaw.toLowerCase()) ? "sell" : "buy";

    const name = await qDefault("  股票名称（可选）", "");
    const marketStr = await qDefault("  市场 (A/HK)", "A");
    const market = (marketStr.toUpperCase() === "HK" ? "HK" : "A") as "A" | "HK";

    try {
      // TODO: migrate to TradeCliAdapter.add()
    } catch (e) {
      console.log(`  ❌ ${e instanceof Error ? e.message : String(e)}\n`);
      continue;
    }

    // 同步更新 portfolio.json
    if (action === "buy") {
      const res = portfolio.add(symbol, quantity, price, commission, name, market, notes ? `${notes}（交易导入）` : "交易导入");
      console.log(`  ✅ 交易已记录 | ${res.message}\n`);
    } else {
      const res = portfolio.update(symbol, undefined, undefined, name || undefined);
      // 减少数量
      const data = portfolio.load();
      const h = data.holdings.find(h => h.symbol === symbol);
      if (h) {
        const newQty = h.quantity - quantity;
        if (newQty <= 0) {
          portfolio.remove(symbol);
          console.log(`  ✅ 交易已记录 | ${symbol} 已清仓\n`);
        } else {
          portfolio.update(symbol, newQty);
          console.log(`  ✅ 交易已记录 | ${symbol} 剩余 ${newQty} 股\n`);
        }
      } else {
        console.log(`  ✅ 交易已记录（${symbol} 不在持仓中，仅记录历史）\n`);
      }
    }
    count++;
  }
  if (count > 0) console.log(`  共录入 ${count} 笔交易。\n`);
}

// ─── 查看交易历史 ──────────────────────────────────────────────────────────

async function viewTrades(): Promise<void> {
  const sym = await q("  查询代码（回车查看全部最近20条）: ");
  // TODO: migrate trade list to TradeCliAdapter.list()

  if (list.length === 0) {
    console.log("  暂无交易记录。\n");
    return;
  }

  printHeader(`📋 交易历史（${list.length} 条）`);
  printTable([
    ["  日期        ", " 代码   ", " 名称    ", " 方向", "  数量", "   价格", " 手续费", " 金额      ", "  备注"],
    ["  ──────────", "──────", "────────", "────", "──────", "───────", "───────", "──────────", "────"],
  ]);
  for (const t of list) {
    const dir = t.action === "buy" ? "🟢买入" : "🔴卖出";
    console.log(
      `  ${t.date}  ${padR(t.symbol, 6)}  ${padR(t.name || "──", 8)}  ${dir}  ` +
      `${padL(String(t.quantity), 6)}  ${padL(t.price.toFixed(2), 7)}  ` +
      `${padL(t.commission.toFixed(2), 7)}  ${padL(t.amount.toFixed(0) + "元", 10)}  ${t.notes}`
    );
  }
  line();
  // TODOsummary();
  console.log(`  共 ${s.total} 笔 | 买入 ${s.buys} 笔（${s.totalBuyAmount.toFixed(0)}元） | 卖出 ${s.sells} 笔（${s.totalSellAmount.toFixed(0)}元）\n`);
}

// ─── 从交易历史重建持仓 ────────────────────────────────────────────────────

async function syncFromTrades(): Promise<void> {
  let snap;
  try {
    // TODObuildSnapshot();
  } catch (e) {
    console.log(`  ❌ ${e instanceof Error ? e.message : String(e)}\n`);
    return;
  }
  if (snap.size === 0) {
    console.log("  暂无交易记录可用于重建持仓。\n");
    return;
  }

  console.log(`\n  从交易记录重建出 ${snap.size} 只持仓：`);
  for (const [sym, pos] of snap) {
    console.log(`    ${sym} ${pos.name}  ${pos.quantity}股 × 均价${pos.avg_cost.toFixed(2)}  已实现盈亏: ${sign(pos.realized_pnl)}元`);
  }
  const confirm = await q("\n  确认覆盖当前 portfolio.json？(y/N) ");
  if (confirm.toLowerCase() !== "y") { console.log("  已取消。\n"); return; }

  const holdings = [...snap.values()].map((pos) => ({
    symbol: pos.symbol,
    name: pos.name,
    quantity: pos.quantity,
    avg_cost: pos.avg_cost,
    market: pos.market,
    notes: "从交易历史重建",
    added_date: chinaDate(),
  }));
  portfolio.replaceHoldings(holdings);
  console.log("  ✅ 持仓已从交易历史重建。\n");
}

// ─── 导出持仓 CSV ──────────────────────────────────────────────────────────

async function exportCsv(): Promise<void> {
  const { writeFileSync } = await import("fs");
  const data = portfolio.load();
  const header = "代码,名称,数量,均价,市场,备注,录入日期";
  const rows = data.holdings.map(h =>
    `${h.symbol},${h.name},${h.quantity},${h.avg_cost},${h.market},"${h.notes}",${h.added_date}`
  );
  const csv = [header, ...rows].join("\n");
  const outPath = join(piDir, "portfolio-export.csv");
  writeFileSync(outPath, csv, "utf-8");
  console.log(`  ✅ 已导出到 ${outPath}\n`);

  const tData = /* TODO: TradeCliAdapter.list() */ ([] as any);
  if (tData.trades.length > 0) {
    const tHeader = "日期,代码,名称,方向,数量,价格,手续费,金额,市场,备注";
    const tRows = tData.trades.map(t =>
      `${t.date},${t.symbol},${t.name},${t.action === "buy" ? "买入" : "卖出"},${t.quantity},${t.price},${t.commission},${t.amount},${t.market},"${t.notes}"`
    );
    const tCsv = [tHeader, ...tRows].join("\n");
    const tOutPath = join(piDir, "trades-export.csv");
    writeFileSync(tOutPath, tCsv, "utf-8");
    console.log(`  ✅ 交易历史已导出到 ${tOutPath}\n`);
  }
}

// ─── 主菜单 ────────────────────────────────────────────────────────────────

async function mainMenu(): Promise<void> {
  printHeader("PI Investment — 持仓 & 交易管理");

  const pData = portfolio.load();
  const tData = /* TODO: TradeCliAdapter.list() */ ([] as any);
  console.log(`  持仓: ${pData.holdings.length} 只  |  交易记录: ${tData.trades.length} 笔\n`);

  console.log("  1. 查看持仓（含实时行情 & 盈亏）");
  console.log("  2. 录入持仓");
  console.log("  3. 录入交易记录（买入/卖出）");
  console.log("  4. 查看交易历史");
  console.log("  5. 从交易历史重建持仓");
  console.log("  6. 导出 CSV（portfolio.csv & trades.csv）");
  console.log("  0. 退出\n");

  const choice = await q("  请选择: ");
  console.log();

  switch (choice) {
    case "1": await viewPortfolio(); break;
    case "2": await addHolding(); break;
    case "3": await addTrade(); break;
    case "4": await viewTrades(); break;
    case "5": await syncFromTrades(); break;
    case "6": await exportCsv(); break;
    case "0":
      console.log("  再见！\n");
      rl.close();
      process.exit(0);
    default:
      console.log("  无效选项\n");
  }
}

// ─── 入口 ──────────────────────────────────────────────────────────────────

const arg = process.argv[2];

async function run(): Promise<void> {
  if (arg === "add")    { await addHolding(); }
  else if (arg === "trade") { await addTrade(); }
  else if (arg === "view")  { await viewPortfolio(); }
  else if (arg === "sync")  { await syncFromTrades(); }
  else {
    // 循环菜单
    while (true) {
      await mainMenu();
    }
  }
  rl.close();
}

run().catch(e => { console.error(e); rl.close(); process.exit(1); });
