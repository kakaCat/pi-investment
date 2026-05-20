/**
 * Shared utilities, types, and services for akshare-ts
 */

import { join } from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import { fileURLToPath } from "url";
import { StockDBService, KlineCacheAdapter } from "../../services/data/stock-db-index.js";
import { callPythonDaemon } from "../tools/python-bridge.js";

const execFileAsync = promisify(execFile);
const __dirname = fileURLToPath(new URL(".", import.meta.url));
const pythonScript = join(__dirname, "..", "..", "..", "python", "akshare_bridge.py");

/**
 * callPython - Direct Python bridge for functions not yet in TS
 */
export async function callPython(func: string, args: Record<string, unknown> = {}): Promise<string> {
  try {
    const argsJson = JSON.stringify(args);
    const { stdout } = await execFileAsync(
      "python3",
      [pythonScript, func, argsJson],
      { timeout: 60000 }
    );
    return stdout.trim();
  } catch (error: unknown) {
    if (error instanceof Error) {
      const spawnError = error as any;
      const stderr = spawnError.stderr ? String(spawnError.stderr).trim() : "";
      const msg = stderr || error.message;
      return JSON.stringify({ error: `Python调用失败: ${msg}` });
    }
    return JSON.stringify({ error: "Python调用失败（未知错误）" });
  }
}

export type JsonRecord = Record<string, unknown>;

export async function callPythonBridge(func: string, args: Record<string, unknown> = {}): Promise<JsonRecord> {
  const result = await callPythonDaemon(func, args);
  return JSON.parse(result) as JsonRecord;
}

export function r2(v: number | null): number {
  return roundN(v, 2) ?? 0;
}

export function r4(v: number | null): number {
  return roundN(v, 4) ?? 0;
}

function roundN(v: number | null, decimals: number): number | null {
  if (v === null || !Number.isFinite(v)) return null;
  const factor = Math.pow(10, decimals);
  return Math.round(v * factor) / factor;
}

export function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const raw = value.trim();
    const unit = raw.includes("亿") ? 1e8 : raw.includes("万") ? 1e4 : 1;
    const cleaned = raw.replace(/,/g, "").replace(/%/g, "").replace(/[^\d.-]/g, "");
    const num = Number.parseFloat(cleaned);
    return Number.isFinite(num) ? num * unit : 0;
  }
  return 0;
}

export function findNumber(record: JsonRecord, keys: readonly string[]): number {
  for (const key of keys) {
    if (key in record && record[key] != null && `${record[key]}` !== "") {
      return toNumber(record[key]);
    }
  }
  return 0;
}

export function findString(record: JsonRecord, keys: readonly string[]): string {
  for (const key of keys) {
    if (key in record && record[key] != null && `${record[key]}`.trim() !== "") {
      return String(record[key]).trim();
    }
  }
  return "";
}

export function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

export function normalizeHolderName(name: string): string {
  return name.replace(/\s+/g, "").replace(/[（(].*?[）)]/g, "").trim();
}

export function computeQuarterEnds(limit = 8): string[] {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth() + 1;
  const day = today.getDate();

  const quarterEnds = [
    { month: 3, day: 31, suffix: "0331" },
    { month: 6, day: 30, suffix: "0630" },
    { month: 9, day: 30, suffix: "0930" },
    { month: 12, day: 31, suffix: "1231" },
  ];

  const result: string[] = [];
  let currentYear = year;
  while (result.length < limit) {
    for (let i = quarterEnds.length - 1; i >= 0 && result.length < limit; i--) {
      const end = quarterEnds[i];
      if (
        currentYear === year &&
        (month < end.month || (month === end.month && day <= end.day))
      ) {
        continue;
      }
      result.push(`${currentYear}${end.suffix}`);
    }
    currentYear -= 1;
  }
  return result;
}

export function getQualityRating(score: number): "优秀" | "良好" | "一般" | "较差" {
  if (score >= 80) return "优秀";
  if (score >= 65) return "良好";
  if (score >= 50) return "一般";
  return "较差";
}

const piDir = ".pi-invest";
let _stockDB: StockDBService | null = null;
let _klineCache: KlineCacheAdapter | null = null;

// ─── Session 数据目录（工具结果写入此目录，供 agent 按需 read）───
let _sessionDataDir: string | null = null;

/** 设置当前 session 的数据输出目录（每次会话初始化时调用） */
export function setSessionDataDir(dir: string): void {
  _sessionDataDir = dir;
}

/** 获取当前 session 的数据输出目录，fallback 到 /tmp */
export function getSessionDataDir(): string {
  return _sessionDataDir || "/tmp";
}

export function getStockDB(): StockDBService {
  if (!_stockDB) _stockDB = StockDBService.getInstance(piDir);
  return _stockDB;
}

export function getKlineCache(): KlineCacheAdapter {
  if (!_klineCache) _klineCache = new KlineCacheAdapter(getStockDB());
  return _klineCache;
}

export interface PortfolioData {
  holdings: Array<{
    symbol: string;
    quantity: number;
    avg_cost: number;
    notes: string;
    added_date: string;
    name?: string;
  }>;
  last_updated: string;
}

export type TsFn = (args: Record<string, unknown>) => Promise<string> | string;
