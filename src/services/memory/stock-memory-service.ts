/**
 * 股票静态信息记忆服务
 *
 * 管理 .pi-invest/bootstrap/STOCK_MEMORY.md
 * 在 agent 启动时加载，避免重复查询静态信息
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";

interface StockStaticInfo {
  symbol: string;
  name: string;
  sector: string;
  listed_date: string;
}

export class StockMemoryService {
  private memoryPath: string;
  private stocks = new Map<string, StockStaticInfo>();

  constructor() {
    this.memoryPath = join(process.cwd(), ".pi-invest/bootstrap/STOCK_MEMORY.md");
    this.load();
  }

  /**
   * 加载记忆文件
   */
  private load(): void {
    if (!existsSync(this.memoryPath)) return;

    try {
      const content = readFileSync(this.memoryPath, "utf-8");
      const lines = content.split("\n");

      let currentSymbol = "";
      for (const line of lines) {
        // ### 600519 贵州茅台
        if (line.startsWith("### ")) {
          const match = line.match(/### (\S+)\s+(.*)/);
          if (match) currentSymbol = match[1];
        }
        // - 行业: 白酒
        else if (line.startsWith("- ") && currentSymbol) {
          const existing = this.stocks.get(currentSymbol) || { symbol: currentSymbol, name: "", sector: "", listed_date: "" };

          if (line.includes("名称:")) {
            existing.name = line.split(":")[1]?.trim() || "";
          } else if (line.includes("行业:")) {
            existing.sector = line.split(":")[1]?.trim() || "";
          } else if (line.includes("上市日期:")) {
            existing.listed_date = line.split(":")[1]?.trim() || "";
          }

          this.stocks.set(currentSymbol, existing);
        }
      }
    } catch {
      // 忽略加载失败
    }
  }

  /**
   * 获取股票静态信息
   */
  get(symbol: string): StockStaticInfo | null {
    return this.stocks.get(symbol) || null;
  }

  /**
   * 添加/更新股票信息
   */
  add(info: StockStaticInfo): void {
    this.stocks.set(info.symbol, info);
    this.save();
  }

  /**
   * 保存到文件
   */
  private save(): void {
    const lines = [
      "# 股票静态信息记忆",
      "",
      "以下是已查询过的股票静态信息，无需再次调用 `get_stock_info` 工具：",
      "",
      "## 已知股票",
      "",
    ];

    const sorted = Array.from(this.stocks.values()).sort((a, b) => a.symbol.localeCompare(b.symbol));

    for (const stock of sorted) {
      lines.push(`### ${stock.symbol} ${stock.name}`);
      lines.push(`- 名称: ${stock.name}`);
      lines.push(`- 行业: ${stock.sector}`);
      lines.push(`- 上市日期: ${stock.listed_date}`);
      lines.push("");
    }

    lines.push("---");
    lines.push("");
    lines.push("**使用说明**：");
    lines.push("- 当用户问到某个股票时，先检查此文件是否已有记录");
    lines.push("- 如果有记录，直接使用这里的信息（名称、行业、上市日期）");
    lines.push("- 如果没有记录，调用工具获取后，更新此文件");
    lines.push("- 动态数据（价格、成交量）仍需实时获取");

    writeFileSync(this.memoryPath, lines.join("\n"), "utf-8");
  }
}

export const stockMemoryService = new StockMemoryService();
