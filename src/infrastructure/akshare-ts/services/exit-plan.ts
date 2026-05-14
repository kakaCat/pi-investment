/**
 * Exit plan service - calculates profit-taking targets and sell recommendations
 */

import { get_stock_realtime_price } from "../data/market.js";
import { r2 } from "../shared.js";
import { cleanSymbol } from "../../data-sources/sina.js";
import { today } from "../../data-sources/http-client.js";

export async function get_exit_plan(symbol: string, buy_price: number, shares = 100): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const priceJson = await get_stock_realtime_price(clean);
    const rt = JSON.parse(priceJson);
    if (rt.error) return priceJson;
    const curPrice: number = rt.price;
    const pe: number = rt.pe_dynamic ?? 0;

    let tC: number, tM: number, tA: number;
    if (pe > 0 && curPrice > 0) {
      const eps = curPrice / pe;
      const basePe = Math.min(pe, 28.5);
      tC = r2(eps * basePe * 1.2);
      tM = r2(eps * basePe * 1.5);
      tA = r2(eps * basePe * 2.0);
    } else {
      tC = r2(buy_price * 1.20);
      tM = r2(buy_price * 1.40);
      tA = r2(buy_price * 1.60);
    }

    const pnlPct = r2((curPrice - buy_price) / buy_price * 100);
    const pnlAmt = r2((curPrice - buy_price) * shares);
    const plan: string[] = [];
    if (curPrice >= tC) plan.push(`已达保守目标(${tC})，建议卖出30%`);
    if (curPrice >= tM) plan.push(`已达中等目标(${tM})，建议再卖40%`);
    if (curPrice >= tA) plan.push(`已达激进目标(${tA})，建议清仓剩余30%`);
    if (!plan.length) {
      const pctToTarget = r2((tC - curPrice) / curPrice * 100);
      plan.push(`距保守目标(${tC})还有${pctToTarget}%，继续持有`);
    }

    return JSON.stringify({
      symbol: clean, name: rt.name, buy_price, current_price: curPrice, shares,
      pnl_pct: pnlPct, pnl_amount: pnlAmt,
      targets: { conservative: tC, moderate: tM, aggressive: tA },
      sell_plan: plan, data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
