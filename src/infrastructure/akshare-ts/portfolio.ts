/**
 * Portfolio management functions
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { today, nowStr } from "../data-sources/http-client.js";
import type { PortfolioData } from "./shared.js";

const portfolioPath = join(process.cwd(), ".pi-invest", "portfolio.json");

function loadPortfolio(): PortfolioData {
  if (!existsSync(portfolioPath)) return { holdings: [], last_updated: "" };
  return JSON.parse(readFileSync(portfolioPath, "utf-8")) as PortfolioData;
}

function savePortfolio(data: PortfolioData): void {
  mkdirSync(join(process.cwd(), ".pi-invest"), { recursive: true });
  writeFileSync(portfolioPath, JSON.stringify(data, null, 2), "utf-8");
}

export function manage_portfolio(
  action: string,
  symbol?: string,
  quantity?: number,
  avg_cost?: number,
  notes = "",
): string {
  try {
    const data = loadPortfolio();
    if (action === "get") return JSON.stringify(data);

    if (action === "add" && symbol) {
      const existing = data.holdings.find(h => h.symbol === symbol);
      if (existing) {
        if (quantity !== undefined) existing.quantity = quantity;
        if (avg_cost !== undefined) existing.avg_cost = avg_cost;
        existing.notes = notes;
      } else {
        data.holdings.push({ symbol, quantity: quantity ?? 0, avg_cost: avg_cost ?? 0, notes, added_date: today() });
      }
      data.last_updated = nowStr();
      savePortfolio(data);
      return JSON.stringify({ success: true, message: `已添加/更新 ${symbol}` });
    }

    if (action === "remove" && symbol) {
      data.holdings = data.holdings.filter(h => h.symbol !== symbol);
      data.last_updated = nowStr();
      savePortfolio(data);
      return JSON.stringify({ success: true, message: `已删除 ${symbol}` });
    }

    return JSON.stringify({ error: `未知操作: ${action}` });
  } catch (e) {
    return JSON.stringify({ error: String(e) });
  }
}
