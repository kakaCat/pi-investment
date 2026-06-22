/**
 * Stooq data source — HK historical klines (CSV)
 *
 * URL: https://stooq.com/q/d/l/?s=700.hk&i=d
 * CSV: Date,Open,High,Low,Close,Volume
 */

import { withRetry, safeFloat } from "../utils/http-client.js";

export interface StooqBar {
  date: string; open: number; high: number; low: number; close: number; volume: number;
}

export async function fetchHkHistory(
  hkCode: string,
  interval: "d" | "w" | "m" = "d",
  limit = 60,
): Promise<StooqBar[]> {
  // stooq strips leading zeros: 09988 → 9988
  const stooqCode = String(parseInt(hkCode, 10));
  const url = `https://stooq.com/q/d/l/?s=${stooqCode}.hk&i=${interval}`;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);

  const text = await withRetry(async () => {
    clearTimeout(timer);
    const c = new AbortController();
    const t = setTimeout(() => c.abort(), 12000);
    try {
      const resp = await fetch(url, {
        headers: { "User-Agent": "Mozilla/5.0" },
        signal: c.signal,
      });
      return await resp.text();
    } finally {
      clearTimeout(t);
    }
  });

  clearTimeout(timer);

  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];

  const bars: StooqBar[] = [];
  // Skip header, take last `limit` rows
  for (const line of lines.slice(1).slice(-limit)) {
    const p = line.trim().split(",");
    if (p.length < 5) continue;
    bars.push({
      date: p[0],
      open: safeFloat(p[1]),
      high: safeFloat(p[2]),
      low: safeFloat(p[3]),
      close: safeFloat(p[4]),
      volume: safeFloat(p[5] ?? "0", 0),
    });
  }
  return bars;
}
