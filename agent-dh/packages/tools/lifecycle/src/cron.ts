/**
 * 轻量 5 段 cron 解析器（分 时 日 月 周）
 *
 * 支持：*、a、,、a-b、*\/n
 * DOW: 0 和 7 都表示周日。
 * DOM/DOW 语义：两者都受限时取并集（标准 cron 行为）；任一受限则需该维度匹配。
 *
 * 替代 os-remind-bridge.sh + OS 信箱链路的原生调度核心（2026-09-01）。
 */

export interface ParsedCron {
  minute: Set<number>;
  hour: Set<number>;
  dom: Set<number>;
  month: Set<number>;
  dow: Set<number>;
  domRestricted: boolean;
  dowRestricted: boolean;
}

function parseField(
  field: string,
  min: number,
  max: number,
  fieldName: string,
  aliases?: Record<string, number>,
): { values: Set<number>; restricted: boolean } {
  const values = new Set<number>();
  let restricted = false;

  for (const part of field.split(',')) {
    const p = part.trim();
    if (!p) throw new Error(`cron ${fieldName}: 空段`);

    // */n 或 a-b/n
    const stepMatch = p.match(/^(.+)\/(\d+)$/);
    let base = p;
    let step = 1;
    if (stepMatch) {
      base = stepMatch[1];
      step = parseInt(stepMatch[2], 10);
      if (step <= 0) throw new Error(`cron ${fieldName}: 步长须>0`);
    }

    let lo: number, hi: number;
    if (base === '*') {
      lo = min; hi = max;
    } else if (base.includes('-')) {
      const [a, b] = base.split('-');
      lo = parseVal(a, aliases, fieldName);
      hi = parseVal(b, aliases, fieldName);
      if (lo > hi) throw new Error(`cron ${fieldName}: 范围倒置 ${base}`);
      restricted = true;
    } else {
      lo = hi = parseVal(base, aliases, fieldName);
      restricted = true;
    }

    if (lo < min || hi > max) {
      throw new Error(`cron ${fieldName}: 值越界 ${lo}-${hi}（允许 ${min}-${max}）`);
    }
    for (let v = lo; v <= hi; v += step) values.add(v);
  }

  return { values, restricted };
}

function parseVal(s: string, aliases: Record<string, number> | undefined, fieldName: string): number {
  const key = s.trim().toUpperCase();
  if (aliases && key in aliases) return aliases[key];
  const n = parseInt(s, 10);
  if (Number.isNaN(n)) throw new Error(`cron ${fieldName}: 无法解析 "${s}"`);
  return n;
}

const DOW_ALIASES: Record<string, number> = {
  SUN: 0, MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6,
};
const MONTH_ALIASES: Record<string, number> = {
  JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6,
  JUL: 7, AUG: 8, SEP: 9, OCT: 10, NOV: 11, DEC: 12,
};

export function parseCron(expr: string): ParsedCron {
  const fields = expr.trim().split(/\s+/);
  // 支持 5 段（分 时 日 月 周）和 6 段（秒 分 时 日 月 周，Agent OS 格式）。
  // 6 段时秒位必须为 0/ * ——调度器分钟粒度，非 0 秒的触发按该分钟处理。
  let minuteF: string, hourF: string, domF: string, monthF: string, dowF: string;
  if (fields.length === 5) {
    [minuteF, hourF, domF, monthF, dowF] = fields;
  } else if (fields.length === 6) {
    [, minuteF, hourF, domF, monthF, dowF] = fields;
  } else {
    throw new Error(`cron 表达式须为 5 或 6 段，得到 ${fields.length} 段: "${expr}"`);
  }

  const minute = parseField(minuteF, 0, 59, '分');
  const hour = parseField(hourF, 0, 23, '时');
  const dom = parseField(domF, 1, 31, '日');
  const month = parseField(monthF, 1, 12, '月', MONTH_ALIASES);
  const dowRaw = parseField(dowF, 0, 7, '周', DOW_ALIASES);

  // DOW 7 → 0（周日）
  const dow = new Set<number>();
  for (const v of dowRaw.values) dow.add(v === 7 ? 0 : v);

  return {
    minute: minute.values,
    hour: hour.values,
    dom: dom.values,
    month: month.values,
    dow,
    domRestricted: dom.restricted,
    dowRestricted: dowRaw.restricted,
  };
}

/** 判断某时刻（本地时间）是否匹配 cron */
export function matchesCron(cron: ParsedCron, date: Date): boolean {
  if (!cron.minute.has(date.getMinutes())) return false;
  if (!cron.hour.has(date.getHours())) return false;
  if (!cron.month.has(date.getMonth() + 1)) return false;

  const domMatch = cron.dom.has(date.getDate());
  const dowMatch = cron.dow.has(date.getDay());

  // 标准 cron DOM/DOW 并集语义：两者都受限时任一匹配即可
  if (cron.domRestricted && cron.dowRestricted) return domMatch || dowMatch;
  if (cron.domRestricted) return domMatch;
  if (cron.dowRestricted) return dowMatch;
  return true;
}

/** 从 from 之后找下一次触发时刻（逐分钟扫描，上限 366 天） */
export function nextRunAfter(cron: ParsedCron, from: Date): Date | null {
  // 对齐到下一分钟整
  const t = new Date(from.getTime());
  t.setSeconds(0, 0);
  t.setMinutes(t.getMinutes() + 1);

  const limit = new Date(from.getTime() + 366 * 24 * 3600 * 1000);
  while (t <= limit) {
    if (matchesCron(cron, t)) return t;
    t.setMinutes(t.getMinutes() + 1);
  }
  return null;
}
