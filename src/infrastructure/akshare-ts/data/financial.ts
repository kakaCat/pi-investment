/**
 * Financial data layer - valuation, quality score, fund flow, holder changes
 */

import { callPythonBridge, findNumber, findString, normalizeHolderName, computeQuarterEnds, r2, JsonRecord, getQualityRating, toNumber } from "../shared.js";
import { today } from "../../data-sources/http-client.js";
import { cleanSymbol } from "../../data-sources/sina.js";

// ─── 估值数据 ──────────────────────────────────────────────────────────

export async function get_stock_valuation(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // Fallback to Python akshare (network restrictions on TS sources)
    return JSON.stringify(await callPythonBridge("get_stock_valuation", { symbol: clean }));
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

// ─── PE历史分位数 ──────────────────────────────────────────────────────────

export async function get_pe_percentile(symbol: string, years = 3): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // Use Python bridge for PE data (network restrictions on TS sources)
    return JSON.stringify(await callPythonBridge("get_pe_percentile", { symbol: clean, years }));
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

function extractStatementRows(payload: JsonRecord, sectionKey: string): JsonRecord[] {
  const section = payload[sectionKey];
  if (section && typeof section === "object" && !Array.isArray(section)) {
    const data = (section as JsonRecord).data;
    if (Array.isArray(data)) return data as JsonRecord[];
  }
  const direct = payload.data;
  return Array.isArray(direct) ? direct as JsonRecord[] : [];
}

export async function get_quality_score(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const [financials, incomePayload, cashPayload] = await Promise.all([
      callPythonBridge("get_financial_indicators", { symbol: clean }),
      callPythonBridge("get_income_statement", { symbol: clean, recent_n: 8 }),
      callPythonBridge("get_cash_flow", { symbol: clean, recent_n: 8 }),
    ]);

    if (financials.error) return JSON.stringify(financials);

    const finRows = Array.isArray(financials.data)
      ? financials.data as JsonRecord[]
      : Array.isArray(financials.quarters)
      ? financials.quarters as JsonRecord[]
      : [];
    if (!finRows.length) return JSON.stringify({ error: `无财务数据: ${clean}`, symbol: clean });

    const incomeRows = extractStatementRows(incomePayload, "income_statement");
    const cashRows = extractStatementRows(cashPayload, "cash_flow");
    const latest = finRows[0];
    const latestIncome = incomeRows[0] ?? {};
    const latestCash = cashRows[0] ?? {};

    const roe = findNumber(latest, ["roe", "净资产收益率(%)", "加权净资产收益率(%)"]);
    const grossMargin = findNumber(latest, ["gross_margin", "销售毛利率(%)", "毛利率"]);
    const debtRatio = findNumber(latest, ["debt_ratio", "资产负债率(%)"]);

    const roeSeries = finRows
      .slice(0, 4)
      .map(row => findNumber(row, ["roe", "净资产收益率(%)", "加权净资产收益率(%)"]))
      .filter(v => v !== 0);
    const latestRevenue = findNumber(latestIncome, ["营业总收入", "营业收入"]);
    const previousRevenue = incomeRows
      .slice(1)
      .map(row => findNumber(row, ["营业总收入", "营业收入"]))
      .find(v => v > 0) ?? 0;
    const revenueGrowth = previousRevenue > 0 ? r2((latestRevenue - previousRevenue) / previousRevenue * 100) : 0;

    const operatingCashFlow = findNumber(latestCash, [
      "经营活动产生的现金流量净额",
      "经营活动现金流量净额",
      "经营现金流量净额",
    ]);
    const netProfit = findNumber(latestIncome, [
      "净利润",
      "归属于母公司股东的净利润",
      "归母净利润",
      "净利润(含少数股东损益)",
    ]);
    const cashFlowCoverage = netProfit !== 0 ? r2(operatingCashFlow / Math.abs(netProfit) * 100) : 0;
    const recentCashFlowPositive = cashRows
      .slice(0, 3)
      .map(row => findNumber(row, [
        "经营活动产生的现金流量净额",
        "经营活动现金流量净额",
        "经营现金流量净额",
      ]))
      .filter(v => v !== 0);
    const positiveCashFlowCount = recentCashFlowPositive.filter(v => v > 0).length;

    let roeScore = roe >= 20 ? 23 : roe >= 15 ? 20 : roe >= 10 ? 15 : roe >= 5 ? 8 : roe > 0 ? 3 : 0;
    if (roeSeries.length >= 3) {
      if (roeSeries[0] >= roeSeries[1] && roeSeries[1] >= roeSeries[2]) roeScore += 2;
      else if (roeSeries[0] < roeSeries[1] && roeSeries[1] < roeSeries[2]) roeScore -= 2;
    }
    roeScore = Math.max(0, Math.min(25, roeScore));

    const grossMarginScore =
      grossMargin >= 50 ? 20 :
      grossMargin >= 35 ? 16 :
      grossMargin >= 20 ? 11 :
      grossMargin >= 10 ? 6 : 2;

    const debtScore =
      debtRatio <= 30 ? 15 :
      debtRatio <= 45 ? 12 :
      debtRatio <= 60 ? 8 :
      debtRatio <= 75 ? 4 : 0;

    let cashFlowScore =
      operatingCashFlow > 0 && cashFlowCoverage >= 120 ? 20 :
      operatingCashFlow > 0 && cashFlowCoverage >= 100 ? 17 :
      operatingCashFlow > 0 && cashFlowCoverage >= 70 ? 13 :
      operatingCashFlow > 0 ? 8 : 0;
    if (positiveCashFlowCount >= 2) cashFlowScore = Math.min(20, cashFlowScore + 2);

    const revenueGrowthScore =
      revenueGrowth >= 25 ? 20 :
      revenueGrowth >= 15 ? 16 :
      revenueGrowth >= 5 ? 11 :
      revenueGrowth >= 0 ? 7 :
      revenueGrowth >= -10 ? 3 : 0;

    const totalScore = Math.max(0, Math.min(100, roeScore + grossMarginScore + debtScore + cashFlowScore + revenueGrowthScore));
    const rating = getQualityRating(totalScore);

    return JSON.stringify({
      symbol: clean,
      score: totalScore,
      rating,
      dimensions: {
        roe: {
          value_pct: r2(roe),
          score: roeScore,
          weight: 25,
          trend: roeSeries.length >= 3
            ? (roeSeries[0] >= roeSeries[1] && roeSeries[1] >= roeSeries[2] ? "改善" : roeSeries[0] < roeSeries[1] && roeSeries[1] < roeSeries[2] ? "走弱" : "波动")
            : "数据不足",
        },
        gross_margin: { value_pct: r2(grossMargin), score: grossMarginScore, weight: 20 },
        debt_ratio: { value_pct: r2(debtRatio), score: debtScore, weight: 15 },
        cash_flow: {
          operating_cash_flow: r2(operatingCashFlow),
          net_profit: r2(netProfit),
          cash_conversion_pct: r2(cashFlowCoverage),
          score: cashFlowScore,
          weight: 20,
        },
        revenue_growth: {
          latest_revenue: r2(latestRevenue),
          previous_revenue: r2(previousRevenue),
          growth_pct: r2(revenueGrowth),
          score: revenueGrowthScore,
          weight: 20,
        },
      },
      summary: totalScore >= 80 ? "盈利质量与成长性较强" : totalScore >= 65 ? "基本面较稳健" : totalScore >= 50 ? "基本面中性" : "基本面偏弱需谨慎",
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

export async function get_stock_fund_flow(symbol: string, days = 5): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const payload = await callPythonBridge("get_stock_fund_flow", { symbol: clean });
    if (payload.error) return JSON.stringify(payload);

    const rows = Array.isArray(payload.data) ? payload.data as JsonRecord[] : [];
    const selected = rows.slice(-Math.max(1, Math.min(days, rows.length)));
    if (!selected.length) return JSON.stringify({ error: `无资金流向数据: ${clean}`, symbol: clean });

    const categories = {
      main_force: {
        label: "主力",
        amountKeys: ["主力净流入-净额", "主力净流入", "主力净额"],
        ratioKeys: ["主力净流入-净占比", "主力净流入净占比", "主力净占比"],
      },
      large_order: {
        label: "大单",
        amountKeys: ["大单净流入-净额", "大单净流入", "大单净额"],
        ratioKeys: ["大单净流入-净占比", "大单净流入净占比", "大单净占比"],
      },
      medium_order: {
        label: "中单",
        amountKeys: ["中单净流入-净额", "中单净流入", "中单净额"],
        ratioKeys: ["中单净流入-净占比", "中单净流入净占比", "中单净占比"],
      },
      small_order: {
        label: "小单",
        amountKeys: ["小单净流入-净额", "小单净流入", "小单净额"],
        ratioKeys: ["小单净流入-净占比", "小单净流入净占比", "小单净占比"],
      },
    } as const;

    const totals = Object.fromEntries(
      Object.entries(categories).map(([key, meta]) => {
        const net = selected.reduce((sum, row) => sum + findNumber(row, meta.amountKeys), 0);
        const ratioValues = selected
          .map(row => findNumber(row, meta.ratioKeys))
          .filter(v => v !== 0);
        return [key, {
          label: meta.label,
          net_inflow: r2(net),
          avg_ratio_pct: ratioValues.length ? r2(ratioValues.reduce((sum, v) => sum + v, 0) / ratioValues.length) : 0,
        }];
      }),
    ) as Record<string, { label: string; net_inflow: number; avg_ratio_pct: number }>;

    const trackedBase = Object.values(totals).reduce((sum, item) => sum + Math.abs(item.net_inflow), 0);
    for (const item of Object.values(totals)) {
      (item as JsonRecord).ratio_pct = trackedBase > 0 ? r2(item.net_inflow / trackedBase * 100) : 0;
      (item as JsonRecord).direction = item.net_inflow >= 0 ? "流入" : "流出";
    }

    const dominantCategory = Object.entries(totals)
      .sort(([, a], [, b]) => Math.abs(b.net_inflow) - Math.abs(a.net_inflow))[0];

    return JSON.stringify({
      symbol: clean,
      days: selected.length,
      categories: totals,
      dominant_force: dominantCategory ? {
        key: dominantCategory[0],
        label: dominantCategory[1].label,
        net_inflow: dominantCategory[1].net_inflow,
      } : null,
      daily_dates: selected.map(row => findString(row, ["日期", "date"])).filter(Boolean),
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}

async function fetchTopHolderSnapshot(symbol: string, reportDate: string): Promise<{
  report_date: string;
  holders: Array<{ holder_name: string; normalized_name: string; shares: number; ratio_pct: number }>;
} | null> {
  const payload = await callPythonBridge("get_top_holders", { symbol, date: reportDate });
  if (payload.error) return null;
  const rows = Array.isArray(payload.data) ? payload.data as JsonRecord[] : [];
  if (!rows.length) return null;

  const holders = rows.map(row => {
    const holderName = findString(row, ["股东名称", "股东名次", "股东", "name"]);
    return {
      holder_name: holderName,
      normalized_name: normalizeHolderName(holderName),
      shares: findNumber(row, ["持股数", "持股数量", "持股总数", "持股数量(股)", "期末持股-数量"]),
      ratio_pct: findNumber(row, ["占总股本持股比例", "持股比例", "持股比例(%)", "总股本占比"]),
    };
  }).filter(holder => holder.holder_name);

  return holders.length ? { report_date: reportDate, holders } : null;
}

export async function get_holder_changes(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    const quarterEnds = computeQuarterEnds(8);
    const snapshots: Array<Awaited<ReturnType<typeof fetchTopHolderSnapshot>>> = [];

    for (const quarterEnd of quarterEnds) {
      const snapshot = await fetchTopHolderSnapshot(clean, quarterEnd);
      if (snapshot) snapshots.push(snapshot);
      if (snapshots.length >= 2) break;
    }

    if (snapshots.length < 2 || !snapshots[0] || !snapshots[1]) {
      return JSON.stringify({ error: `无法获取最近两个季度的十大股东数据: ${clean}`, symbol: clean });
    }

    const [latest, previous] = snapshots as [
      { report_date: string; holders: Array<{ holder_name: string; normalized_name: string; shares: number; ratio_pct: number }> },
      { report_date: string; holders: Array<{ holder_name: string; normalized_name: string; shares: number; ratio_pct: number }> },
    ];

    const previousMap = new Map(previous.holders.map(holder => [holder.normalized_name, holder]));
    const latestMap = new Map(latest.holders.map(holder => [holder.normalized_name, holder]));

    const newHolders: JsonRecord[] = [];
    const reducedHolders: JsonRecord[] = [];
    const increasedHolders: JsonRecord[] = [];
    const exitedHolders: JsonRecord[] = [];

    for (const holder of latest.holders) {
      const prev = previousMap.get(holder.normalized_name);
      if (!prev) {
        newHolders.push({
          holder_name: holder.holder_name,
          current_shares: r2(holder.shares),
          current_ratio_pct: r2(holder.ratio_pct),
        });
        continue;
      }
      const shareChange = holder.shares - prev.shares;
      const ratioChange = holder.ratio_pct - prev.ratio_pct;
      const item = {
        holder_name: holder.holder_name,
        previous_shares: r2(prev.shares),
        current_shares: r2(holder.shares),
        share_change: r2(shareChange),
        previous_ratio_pct: r2(prev.ratio_pct),
        current_ratio_pct: r2(holder.ratio_pct),
        ratio_change_pct: r2(ratioChange),
      };
      if (shareChange < 0 || ratioChange < 0) reducedHolders.push(item);
      else if (shareChange > 0 || ratioChange > 0) increasedHolders.push(item);
    }

    for (const holder of previous.holders) {
      if (!latestMap.has(holder.normalized_name)) {
        exitedHolders.push({
          holder_name: holder.holder_name,
          previous_shares: r2(holder.shares),
          previous_ratio_pct: r2(holder.ratio_pct),
        });
      }
    }

    reducedHolders.sort((a, b) => Math.abs(toNumber(b.ratio_change_pct)) - Math.abs(toNumber(a.ratio_change_pct)));
    increasedHolders.sort((a, b) => Math.abs(toNumber(b.ratio_change_pct)) - Math.abs(toNumber(a.ratio_change_pct)));

    return JSON.stringify({
      symbol: clean,
      comparison_quarters: {
        latest: latest.report_date,
        previous: previous.report_date,
      },
      new_holders: newHolders,
      reduced_holders: reducedHolders,
      increased_holders: increasedHolders,
      exited_holders: exitedHolders,
      summary: {
        new_count: newHolders.length,
        reduced_count: reducedHolders.length,
        increased_count: increasedHolders.length,
        exited_count: exitedHolders.length,
      },
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
