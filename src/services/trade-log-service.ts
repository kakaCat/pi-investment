import { readFileSync, writeFileSync, existsSync, readdirSync } from "fs";
import { join } from "path";
import { FileLockService } from "./file-lock.service.js";

// 交易日志数据结构
export interface TradeLogEntry {
  date: string;
  operation: string;
  quantity: number;
  price: number;
  amount: number;
  notes: string;
}

export interface TradeLogTracking {
  date: string;
  close_price: number;
  change_pct: number;
  float_pnl_pct: number;
  position: number;
  notes?: string;
}

export interface TradeLogMetadata {
  symbol: string;
  name: string;
  industry?: string;
  market: "A" | "HK";
  created_at: string;
  updated_at: string;
}

export interface TradeLogData {
  metadata: TradeLogMetadata;
  holdings_summary: {
    total_shares: number;
    avg_cost: number;
    total_investment: number;
    current_price?: number;
    float_pnl_pct?: number;
  };
  entry_logic: string; // 建仓逻辑（Markdown）
  operation_plan: string; // 操作计划（Markdown）
  execution_records: TradeLogEntry[]; // 执行记录
  tracking_records: TradeLogTracking[]; // 日度追踪
  follow_up_items: string[]; // 后续跟踪要点
}

/**
 * 交易日志服务
 * 管理 .pi-invest/trade-log/ 目录下的股票交易日志（Markdown 格式）
 */
export class TradeLogService {
  private dirPath: string;

  constructor(piDir: string) {
    this.dirPath = join(piDir, "trade-log");
  }

  /**
   * 获取日志文件路径
   */
  private getLogPath(symbol: string, name: string): string {
    return join(this.dirPath, `${symbol}-${name}.md`);
  }

  /**
   * 列出所有交易日志
   */
  list(): Array<{ symbol: string; name: string; path: string }> {
    if (!existsSync(this.dirPath)) {
      return [];
    }

    const files = readdirSync(this.dirPath).filter(
      (f) => f.endsWith(".md") && f !== "README.md"
    );

    return files.map((file) => {
      const match = file.match(/^(.+?)-(.+)\.md$/);
      if (match) {
        return {
          symbol: match[1],
          name: match[2],
          path: join(this.dirPath, file),
        };
      }
      return null;
    }).filter((item): item is { symbol: string; name: string; path: string } => item !== null);
  }

  /**
   * 检查日志是否存在
   */
  exists(symbol: string, name: string): boolean {
    return existsSync(this.getLogPath(symbol, name));
  }

  /**
   * 读取日志内容（原始 Markdown）
   */
  read(symbol: string, name: string): string | null {
    const path = this.getLogPath(symbol, name);
    if (!existsSync(path)) {
      return null;
    }
    return readFileSync(path, "utf-8");
  }

  /**
   * 创建新的交易日志
   */
  create(data: TradeLogData): string {
    const path = this.getLogPath(data.metadata.symbol, data.metadata.name);

    return FileLockService.withLockSync(path, () => {
      if (existsSync(path)) {
        throw new Error(`交易日志已存在: ${data.metadata.symbol}-${data.metadata.name}`);
      }

      const content = this.generateMarkdown(data);
      writeFileSync(path, content, "utf-8");
      return path;
    });
  }

  /**
   * 更新交易日志
   */
  update(symbol: string, name: string, updates: Partial<TradeLogData>): string {
    const path = this.getLogPath(symbol, name);

    return FileLockService.withLockSync(path, () => {
      if (!existsSync(path)) {
        throw new Error(`交易日志不存在: ${symbol}-${name}`);
      }

      // 读取现有内容并解析
      const existing = this.parseMarkdown(readFileSync(path, "utf-8"));

      // 合并更新
      const merged: TradeLogData = {
        metadata: { ...existing.metadata, ...updates.metadata, updated_at: new Date().toISOString() },
        holdings_summary: { ...existing.holdings_summary, ...updates.holdings_summary },
        entry_logic: updates.entry_logic ?? existing.entry_logic,
        operation_plan: updates.operation_plan ?? existing.operation_plan,
        execution_records: updates.execution_records ?? existing.execution_records,
        tracking_records: updates.tracking_records ?? existing.tracking_records,
        follow_up_items: updates.follow_up_items ?? existing.follow_up_items,
      };

      const content = this.generateMarkdown(merged);
      writeFileSync(path, content, "utf-8");
      return path;
    });
  }

  /**
   * 追加执行记录
   */
  appendExecution(symbol: string, name: string, entry: TradeLogEntry): string {
    const path = this.getLogPath(symbol, name);

    return FileLockService.withLockSync(path, () => {
      if (!existsSync(path)) {
        throw new Error(`交易日志不存在: ${symbol}-${name}`);
      }

      const existing = this.parseMarkdown(readFileSync(path, "utf-8"));
      existing.execution_records.push(entry);
      existing.metadata.updated_at = new Date().toISOString();

      const content = this.generateMarkdown(existing);
      writeFileSync(path, content, "utf-8");
      return path;
    });
  }

  /**
   * 追加日度追踪记录
   */
  appendTracking(symbol: string, name: string, tracking: TradeLogTracking): string {
    const path = this.getLogPath(symbol, name);

    return FileLockService.withLockSync(path, () => {
      if (!existsSync(path)) {
        throw new Error(`交易日志不存在: ${symbol}-${name}`);
      }

      const existing = this.parseMarkdown(readFileSync(path, "utf-8"));
      existing.tracking_records.push(tracking);
      existing.metadata.updated_at = new Date().toISOString();

      const content = this.generateMarkdown(existing);
      writeFileSync(path, content, "utf-8");
      return path;
    });
  }

  /**
   * 生成 Markdown 内容
   */
  private generateMarkdown(data: TradeLogData): string {
    const { metadata, holdings_summary, entry_logic, operation_plan, execution_records, tracking_records, follow_up_items } = data;

    let md = `# ${metadata.name}（${metadata.symbol}）交易日志\n\n`;

    if (metadata.industry) {
      md += `> 所属行业：${metadata.industry}\n`;
    }
    md += `> 市场：${metadata.market === "A" ? "A股" : "港股"}\n`;
    md += `> 创建日期：${metadata.created_at.split("T")[0]}\n`;
    md += `> 最后更新：${metadata.updated_at.split("T")[0]}\n\n`;
    md += `---\n\n`;

    // 持仓总览
    md += `## 📋 持仓总览\n\n`;
    md += `| 项目 | 数值 |\n`;
    md += `|------|------|\n`;
    md += `| 总持仓股数 | **${holdings_summary.total_shares} 股** |\n`;
    md += `| 加权成本 | **¥${holdings_summary.avg_cost.toFixed(2)}** |\n`;
    md += `| 总投入 | **¥${holdings_summary.total_investment.toFixed(2)}** |\n`;
    if (holdings_summary.current_price) {
      md += `| 当前价 | **¥${holdings_summary.current_price.toFixed(2)}** |\n`;
    }
    if (holdings_summary.float_pnl_pct !== undefined) {
      const sign = holdings_summary.float_pnl_pct >= 0 ? "+" : "";
      md += `| 当前浮盈 | ${sign}${holdings_summary.float_pnl_pct.toFixed(2)}% |\n`;
    }
    md += `\n---\n\n`;

    // 建仓逻辑
    md += `## 🏗️ 建仓逻辑\n\n`;
    md += entry_logic;
    md += `\n\n---\n\n`;

    // 操作计划
    md += `## 🎯 操作计划\n\n`;
    md += operation_plan;
    md += `\n\n---\n\n`;

    // 执行记录
    md += `## 📝 执行记录\n\n`;
    if (execution_records.length === 0) {
      md += `| 日期 | 操作 | 股数 | 价格 | 金额 | 备注 |\n`;
      md += `|------|------|------|------|------|------|\n`;
      md += `| （暂无） | - | - | - | - | - |\n`;
    } else {
      md += `| 日期 | 操作 | 股数 | 价格 | 金额 | 备注 |\n`;
      md += `|------|------|------|------|------|------|\n`;
      execution_records.forEach((entry) => {
        md += `| ${entry.date} | ${entry.operation} | ${entry.quantity} | ¥${entry.price.toFixed(2)} | ¥${entry.amount.toFixed(2)} | ${entry.notes} |\n`;
      });
    }
    md += `\n---\n\n`;

    // 日度追踪
    md += `## 📈 日度追踪\n\n`;
    if (tracking_records.length === 0) {
      md += `| 日期 | 收盘价 | 涨跌幅 | 浮盈% | 持仓 | 备注 |\n`;
      md += `|------|--------|--------|-------|------|------|\n`;
      md += `| （暂无） | - | - | - | - | - |\n`;
    } else {
      md += `| 日期 | 收盘价 | 涨跌幅 | 浮盈% | 持仓 | 备注 |\n`;
      md += `|------|--------|--------|-------|------|------|\n`;
      tracking_records.forEach((track) => {
        const changeSign = track.change_pct >= 0 ? "+" : "";
        const pnlSign = track.float_pnl_pct >= 0 ? "+" : "";
        md += `| ${track.date} | ¥${track.close_price.toFixed(2)} | ${changeSign}${track.change_pct.toFixed(2)}% | ${pnlSign}${track.float_pnl_pct.toFixed(2)}% | ${track.position} 股 | ${track.notes || "-"} |\n`;
      });
    }
    md += `\n---\n\n`;

    // 后续跟踪要点
    md += `## 🔄 后续跟踪要点\n\n`;
    if (follow_up_items.length === 0) {
      md += `- [ ] 暂无\n`;
    } else {
      follow_up_items.forEach((item) => {
        md += `- [ ] ${item}\n`;
      });
    }
    md += `\n---\n\n`;

    md += `*最后更新：${metadata.updated_at.split("T")[0]}*\n`;

    return md;
  }

  /**
   * 解析 Markdown 内容（简化版，仅提取关键数据）
   */
  private parseMarkdown(content: string): TradeLogData {
    // 简化实现：从现有 Markdown 提取基本信息
    // 完整实现需要更复杂的解析逻辑

    const lines = content.split("\n");
    const symbolMatch = content.match(/# (.+?)（(.+?)）交易日志/);
    const symbol = symbolMatch ? symbolMatch[2] : "";
    const name = symbolMatch ? symbolMatch[1] : "";

    // 提取元数据
    const industryMatch = content.match(/> 所属行业：(.+)/);
    const marketMatch = content.match(/> 市场：(.+)/);
    const createdMatch = content.match(/> 创建日期：(.+)/);
    const updatedMatch = content.match(/> 最后更新：(.+)/);

    const metadata: TradeLogMetadata = {
      symbol,
      name,
      industry: industryMatch ? industryMatch[1].trim() : undefined,
      market: marketMatch && marketMatch[1].includes("港股") ? "HK" : "A",
      created_at: createdMatch ? createdMatch[1].trim() : new Date().toISOString(),
      updated_at: updatedMatch ? updatedMatch[1].trim() : new Date().toISOString(),
    };

    // 提取持仓总览（简化）
    const holdings_summary = {
      total_shares: 0,
      avg_cost: 0,
      total_investment: 0,
    };

    // 提取各个章节（简化实现，返回原始内容）
    const entry_logic = this.extractSection(content, "## 🏗️ 建仓逻辑", "---");
    const operation_plan = this.extractSection(content, "## 🎯 操作计划", "---");

    return {
      metadata,
      holdings_summary,
      entry_logic,
      operation_plan,
      execution_records: [],
      tracking_records: [],
      follow_up_items: [],
    };
  }

  /**
   * 提取 Markdown 章节内容
   */
  private extractSection(content: string, startMarker: string, endMarker: string): string {
    const startIdx = content.indexOf(startMarker);
    if (startIdx === -1) return "";

    const contentAfterStart = content.substring(startIdx + startMarker.length);
    const endIdx = contentAfterStart.indexOf(endMarker);

    if (endIdx === -1) return contentAfterStart.trim();
    return contentAfterStart.substring(0, endIdx).trim();
  }
}
