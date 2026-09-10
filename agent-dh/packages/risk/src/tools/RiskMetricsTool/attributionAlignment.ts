/**
 * 基准/净值按交易日对齐（2026-09-11，REQ-342799 P3 修正，窗口 w-f4aa1f6a）
 *
 * 背景：原实现是 length-based 尾部对齐——取基准日收益末 N 个，与净值收益按"位置"配对。
 * 只要任一侧缺交易日（实测 agent_virtual：59 个交易日仅 55 条快照，缺 08-10/08-24/08-26/
 * 08-27/08-31），位置配对就会错位，使 超额/beta/alpha/IR 全部失真，且失真方向不可预知。
 *
 * 正确形态：在**净值序列自己的日期对**上取基准收益——净值缺日时两侧跨同一段区间，
 * 与后端 empyrical 按位置配对的预期一致；基准缺端点则如实降级标注，绝不静默沿用长度对齐。
 */
export interface DateAlignedResult {
  /** 参与对齐的净值日期（升序，= 后端净值序列的尾部窗口） */
  dates: string[];
  /** 基准日收益，与净值序列**逐位置对应**（长度 = dates.length - 1 - 缺失对数） */
  benchmarkReturns: number[];
  /** 对齐区间内基准区间收益（%） */
  benchmarkReturnPct: number | null;
  /** 端点是否完整：基准在净值每个日期上都有数据（与样本量无关） */
  complete: boolean;
  /** 样本是否足够：有效对数 >= 5（5 点以下不构成统计意义） */
  sufficient: boolean;
  /** 是否可用 = complete && sufficient（写入 attribution.alignment_ok） */
  ok: boolean;
  /** 有效对数 */
  pairs: number;
  /** 因基准缺该日而无法配对的净值日期 */
  missingDates: string[];
  /** 人类可读说明（写入 attribution.alignment） */
  note: string;
}

export function alignByTradingDate(
  navDates: string[],
  benchRows: Array<{ date?: string; trade_date?: string; close?: number }>,
  navPoints: number,
): DateAlignedResult {
  const navTail = (navPoints > 0 ? navDates.slice(-navPoints) : navDates).slice().sort();
  const benchMap = new Map<string, number>();
  for (const r of benchRows) {
    const d = String(r?.date ?? r?.trade_date ?? "").slice(0, 10);
    const c = Number(r?.close);
    if (d && Number.isFinite(c) && c > 0) benchMap.set(d, c);
  }
  const bRet: number[] = [];
  const missingDates: string[] = [];
  let pairs = 0;
  for (let i = 1; i < navTail.length; i++) {
    const d0 = navTail[i - 1];
    const d1 = navTail[i];
    const c0 = benchMap.get(d0);
    const c1 = benchMap.get(d1);
    if (c0 === undefined || c1 === undefined) {
      if (c0 === undefined) missingDates.push(d0);
      if (c1 === undefined) missingDates.push(d1);
      continue;
    }
    bRet.push(c1 / c0 - 1);
    pairs += 1;
  }
  const first = navTail.length ? benchMap.get(navTail[0]) : undefined;
  const last = navTail.length ? benchMap.get(navTail[navTail.length - 1]) : undefined;
  const pct = first !== undefined && last !== undefined && first > 0
    ? +((last / first - 1) * 100).toFixed(2)
    : null;
  const rangeLabel = navTail.length ? navTail[0] + "→" + navTail[navTail.length - 1] : "-";
  const complete = missingDates.length === 0;
  const sufficient = pairs >= 5;
  const ok = complete && sufficient;
  const notes: string[] = [];
  notes.push("date-aligned(净值交易日=" + navTail.length + ", 有效对数=" + pairs + ", " + rangeLabel + ")");
  if (missingDates.length) {
    const uniq = Array.from(new Set(missingDates));
    notes.push("基准缺日=" + uniq.slice(0, 8).join(",") + (uniq.length > 8 ? " 等" + uniq.length + "天" : ""));
  }
  notes.push(ok ? "口径可用"
    : (!complete ? "基准缺端点→已按可用对配对，beta/alpha/IR 解读须保守"
                 : "有效对数不足 5→样本不足，仅供参考"));
  return {
    dates: navTail,
    benchmarkReturns: bRet,
    benchmarkReturnPct: pct,
    complete,
    sufficient,
    ok,
    pairs,
    missingDates: Array.from(new Set(missingDates)),
    note: notes.join("；"),
  };
}

