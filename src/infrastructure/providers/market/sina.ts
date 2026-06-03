/**
 * Sina Finance data source
 *
 * A-share & HK realtime quotes:  hq.sinajs.cn
 * A-share historical klines:     money.finance.sina.com.cn/getKLineData
 */

import { fetchGbk, withRetry, safeFloat } from "../utils/http-client.js";

// ── Symbol helpers ─────────────────────────────────────────────────────────

export function cleanSymbol(s: string): string {
  return s.replace(/^(sh|sz|bj)/i, "").trim();
}

export function sinaSymbol(symbol: string): string {
  const s = cleanSymbol(symbol);
  if (s.startsWith("6")) return `sh${s}`;
  if (s.startsWith("0") || s.startsWith("3")) return `sz${s}`;
  if (s.startsWith("8") || s.startsWith("4")) return `bj${s}`;
  return `sh${s}`;
}

export function isHkSymbol(s: string): boolean {
  const code = s.toUpperCase().replace(/\.HK$/, "");
  return /^\d{1,5}$/.test(code);
}

export function hkCode(symbol: string): string {
  return symbol.toUpperCase().replace(/\.HK$/, "").padStart(5, "0");
}

// ── Parse helpers ──────────────────────────────────────────────────────────

function extractQuoted(line: string): string {
  const m = line.match(/"([^"]*)"/);
  return m ? m[1] : "";
}

export interface SinaAShare {
  name: string; open: string; prevClose: string; price: string;
  high: string; low: string; volume: string; amount: string;
  date: string; time: string;
}

export function parseSinaAShare(line: string): SinaAShare | null {
  const content = extractQuoted(line);
  const fields = content.split(",");
  if (fields.length < 32 || !fields[3]) return null;
  return {
    name: fields[0], open: fields[1], prevClose: fields[2], price: fields[3],
    high: fields[4], low: fields[5], volume: fields[8], amount: fields[9],
    date: fields[30], time: fields[31],
  };
}

export interface SinaHK {
  name: string; prevClose: string; open: string;
  high: string; low: string; price: string;
  changeAmount: string; changePct: string; volume: string; amount: string;
}

export function parseSinaHK(line: string): SinaHK | null {
  const content = extractQuoted(line);
  const fields = content.split(",");
  if (fields.length < 8 || !fields[6]) return null;
  return {
    name: fields[0], prevClose: fields[2], open: fields[3],
    high: fields[4], low: fields[5], price: fields[6],
    changeAmount: fields[7] ?? "0",
    changePct: fields[8] ?? "0",
    volume: fields[9] ?? "0",
    amount: fields[10] ?? "0",
  };
}

// ── Realtime quotes ────────────────────────────────────────────────────────

const SINA_HQ = "https://hq.sinajs.cn/list=";

export async function fetchSinaAShareRealtime(sinaSyms: string[]): Promise<string> {
  return withRetry(() => fetchGbk(`${SINA_HQ}${sinaSyms.join(",")}`));
}

export async function fetchSinaHKRealtime(hkCodes: string[]): Promise<string> {
  const syms = hkCodes.map(c => `hk${c}`);
  return withRetry(() => fetchGbk(`${SINA_HQ}${syms.join(",")}`));
}

export async function fetchSinaIndices(): Promise<string> {
  return withRetry(() =>
    fetchGbk(`${SINA_HQ}sh000001,sz399001,sz399006,sh000300,sz399905`)
  );
}

// ── Historical klines ──────────────────────────────────────────────────────

export interface KlineBar {
  day: string; open: string; high: string; low: string; close: string; volume: string;
}

export async function fetchSinaKlines(
  symbol: string,
  scale: 240 | 1200 | 4800 = 240,
  datalen = 60,
): Promise<KlineBar[]> {
  const sina = sinaSymbol(symbol);
  const url = `https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=${sina}&scale=${scale}&ma=no&datalen=${datalen}`;
  const text = await withRetry(() =>
    fetchGbk(url, 15000)
  );
  try {
    return (JSON.parse(text) ?? []) as KlineBar[];
  } catch {
    return [];
  }
}

// Convenience: parse klines to number arrays
export function klinesToNumbers(bars: KlineBar[]): {
  dates: string[]; open: number[]; high: number[]; low: number[]; close: number[]; volume: number[];
} {
  return {
    dates: bars.map(b => b.day),
    open: bars.map(b => safeFloat(b.open)),
    high: bars.map(b => safeFloat(b.high)),
    low: bars.map(b => safeFloat(b.low)),
    close: bars.map(b => safeFloat(b.close)),
    volume: bars.map(b => safeFloat(b.volume, 0)),
  };
}
