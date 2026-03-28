/**
 * Eastmoney data source
 *
 * Stock info:    emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax
 * Sector list:   datacenter-web.eastmoney.com/api/data/v1/get
 */

import { fetchJson, withRetry, safeFloat, fetchGbk } from "./http-client.js";

// ── Stock basic info ───────────────────────────────────────────────────────

interface EmCompanySurvey {
  jbzl?: Array<{
    SECURITY_NAME_ABBR?: string;
    EM2016?: string;
    REG_CAPITAL?: string;
    LISTING_DATE?: string;
  }>;
}

export async function fetchStockInfo(symbol: string): Promise<{ name: string; sector: string; regCapital: string; listedDate: string }> {
  const clean = symbol.replace(/^(sh|sz|bj)/i, "");
  const mkt = clean.startsWith("6") ? "SH" : (clean.match(/^[84]/) ? "BJ" : "SZ");
  const url = `https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code=${mkt}${clean}`;
  const data = await withRetry(() => fetchJson<EmCompanySurvey>(url, undefined, 12000));
  const jbzl = (data.jbzl ?? [])[0] ?? {};
  return {
    name: String(jbzl.SECURITY_NAME_ABBR ?? ""),
    sector: String(jbzl.EM2016 ?? ""),
    regCapital: String(jbzl.REG_CAPITAL ?? ""),
    listedDate: jbzl.LISTING_DATE ? String(jbzl.LISTING_DATE).substring(0, 10) : "",
  };
}

// ── Sector list ────────────────────────────────────────────────────────────

interface EmSectorResult {
  success?: boolean;
  result?: {
    data?: Array<{
      BOARD_NAME?: string;
      BOARD_CODE?: string;
      CHANGE_RATE?: number;
      REPORT_DATE?: string;
    }>;
  };
}

// ── Per-stock PE/PB/market-cap ─────────────────────────────────────────────

export interface PeData {
  pe_ttm: number | null;
  pb: number | null;
  market_cap_billion: number | null; // 亿元
}


/**
 * Fetch PE/PB from Sina (push2.eastmoney blocked on this machine)
 * Sina fields: 39=PE, 46=PB, 44=total_shares(万股)
 */
export async function fetchPeData(symbol: string): Promise<PeData> {
  const clean = symbol.replace(/^(sh|sz|bj)/i, "");
  const prefix = clean.startsWith("6") ? "sh" : (clean.match(/^[84]/) ? "bj" : "sz");
  const sinaCode = `${prefix}${clean}`;
  try {
    const text = await withRetry(() => fetchGbk(`https://hq.sinajs.cn/list=${sinaCode}`));
    const match = text.match(/"([^"]*)"/);
    if (!match) return { pe_ttm: null, pb: null, market_cap_billion: null };
    const fields = match[1].split(",");
    if (fields.length < 47) return { pe_ttm: null, pb: null, market_cap_billion: null };

    const pe = safeFloat(fields[39]);
    const pb = safeFloat(fields[46]);
    const price = safeFloat(fields[3]);
    const totalShares = safeFloat(fields[44]);
    const cap = (price > 0 && totalShares > 0) ? Math.round(price * totalShares / 1e4) / 100 : null;

    return {
      pe_ttm: pe > 0 ? pe : null,
      pb: pb > 0 ? pb : null,
      market_cap_billion: cap,
    };
  } catch {
    return { pe_ttm: null, pb: null, market_cap_billion: null };
  }
}

export async function fetchSectorList(): Promise<Array<{ name: string; code: string; changePct: number }>> {
  // Step 1: get latest date
  const first = await fetchJson<EmSectorResult>(
    "https://datacenter-web.eastmoney.com/api/data/v1/get",
    {
      reportName: "RPT_INDUSTRY_INDEX",
      columns: "BOARD_CODE,BOARD_NAME,CHANGE_RATE,REPORT_DATE",
      pageSize: "1",
      sortColumns: "REPORT_DATE",
      sortTypes: "-1",
    },
    12000,
  );
  const latestDate = first.result?.data?.[0]?.REPORT_DATE?.substring(0, 10);
  if (!latestDate) return [];

  // Step 2: get all boards for that date
  const all = await fetchJson<EmSectorResult>(
    "https://datacenter-web.eastmoney.com/api/data/v1/get",
    {
      reportName: "RPT_INDUSTRY_INDEX",
      columns: "BOARD_CODE,BOARD_NAME,CHANGE_RATE",
      pageSize: "500",
      sortColumns: "BOARD_NAME",
      sortTypes: "1",
      filter: `(REPORT_DATE="${latestDate} 00:00:00")`,
    },
    12000,
  );

  const items = all.result?.data ?? [];
  return items.map(it => ({
    name: String(it.BOARD_NAME ?? ""),
    code: String(it.BOARD_CODE ?? ""),
    changePct: safeFloat(it.CHANGE_RATE),
  }));
}
