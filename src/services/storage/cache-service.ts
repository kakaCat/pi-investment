/**
 * 股票静态数据记忆服务
 *
 * 只存储不会变的数据（永久记忆）：
 * - 股票基本信息（名称、行业、上市日期）
 * - 历史K线（已收盘日期）
 * - 财务报表（按季度）
 *
 * 动态数据（实时价格、今日成交量）不缓存
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";

type MemoryType = "info" | "history" | "financial";

export class MemoryService {
  private memCache = new Map<string, unknown>();
  private memoryDir: string;

  constructor(baseDir = ".pi-invest/memory/cache") {
    this.memoryDir = join(process.cwd(), baseDir);
    mkdirSync(this.memoryDir, { recursive: true });
  }

  /**
   * 获取记忆（内存 → 文件）
   */
  get<T>(type: MemoryType, key: string): T | null {
    const memKey = `${type}:${key}`;

    // 1. 内存
    if (this.memCache.has(memKey)) {
      return this.memCache.get(memKey) as T;
    }

    // 2. 文件
    const filePath = this.getFilePath(type, key);
    if (existsSync(filePath)) {
      try {
        const data = JSON.parse(readFileSync(filePath, "utf-8")) as T;
        this.memCache.set(memKey, data);
        return data;
      } catch {
        return null;
      }
    }

    return null;
  }

  /**
   * 保存记忆（内存 + 文件）
   */
  set<T>(type: MemoryType, key: string, data: T): void {
    const memKey = `${type}:${key}`;
    this.memCache.set(memKey, data);

    // 同步写文件
    try {
      const dir = join(this.memoryDir, type);
      mkdirSync(dir, { recursive: true });
      writeFileSync(this.getFilePath(type, key), JSON.stringify(data, null, 2), "utf-8");
    } catch {
      // 忽略写入失败
    }
  }

  private getFilePath(type: MemoryType, key: string): string {
    const safeKey = key.replace(/[^a-zA-Z0-9_-]/g, "_");
    return join(this.memoryDir, type, `${safeKey}.json`);
  }
}

export const memoryService = new MemoryService();
