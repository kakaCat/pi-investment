/**
 * Shared validation utilities for tools
 */

export function roundN(v: number, n = 2): number {
  const f = Math.pow(10, n);
  return Math.round(v * f) / f;
}

export function validatePositiveNumber(value: number | null | undefined, fieldName: string): string | null {
  if (value == null) {
    return `${fieldName} 不能为空`;
  }
  if (value <= 0) {
    return `${fieldName} 必须大于0，当前值: ${value}`;
  }
  return null;
}

export function validatePositiveInteger(value: number | null | undefined, fieldName: string): string | null {
  if (value == null) {
    return `${fieldName} 不能为空`;
  }
  if (value <= 0 || !Number.isInteger(value)) {
    return `${fieldName} 必须是大于0的整数，当前值: ${value}`;
  }
  return null;
}

export type Market = "ashare" | "hk" | "invalid";

/**
 * 检测股票代码所属市场。
 * - "ashare": 6位数字 A 股（可带 sh/sz/bj 前缀）
 * - "hk":     1-5位数字港股（可带 .HK 后缀）
 * - "invalid": 无法识别（美股、新加坡等不支持的市场）
 */
export function detectMarket(symbol: string): Market {
  const s = symbol.trim();
  // 明确的非支持市场
  if (/\.(US|SG|L|T)$/i.test(s)) return "invalid";
  // 港股：含 .HK 后缀，或纯1-5位数字
  if (/\.HK$/i.test(s)) return "hk";
  const noPrefix = s.replace(/^(sh|sz|bj)/i, "").trim();
  if (/^\d{6}$/.test(noPrefix)) return "ashare";
  if (/^\d{1,5}$/.test(s)) return "hk";
  return "invalid";
}

/**
 * 校验仅限A股的工具（财务报表、技术分析等数据源不支持港股）。
 * 返回 null 表示合法A股；返回错误 JSON 字符串表示不合法。
 */
export function requireAshare(symbol: string): string | null {
  const market = detectMarket(symbol);
  if (market === "ashare") return null;
  if (market === "hk") {
    return JSON.stringify({
      success: false,
      error: `本功能暂不支持港股代码 "${symbol}"。财务报表、技术分析、估值、选股等功能仅支持A股（6位数字）。港股可使用 get_stock_price / get_stock_info / get_stock_history 查询行情。`,
      unsupported_for_hk: true,
    });
  }
  return JSON.stringify({
    success: false,
    error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字，如 600519）和港股（1-5位数字，如 9988 或 9988.HK）。`,
    invalid_format: true,
  });
}
