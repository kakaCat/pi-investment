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
   * 追加执行记录（自动去重：同日期+同操作类型视为重复，替换旧记录）
   */
  appendExecution(symbol: string, name: string, entry: TradeLogEntry): string {
    const path = this.getLogPath(symbol, name);

    return FileLockService.withLockSync(path, () => {
      if (!existsSync(path)) {
        throw new Error(`交易日志不存在: ${symbol}-${name}`);
      }

      const existing = this.parseMarkdown(readFileSync(path, "utf-8"));

      // 去重检查：同日期+同操作类型视为重复，用新记录替换
      const dupIndex = existing.execution_records.findIndex(
        r => r.date === entry.date && r.operation === entry.operation
      );
      if (dupIndex !== -1) {
        existing.execution_records[dupIndex] = entry;
      } else {
        existing.execution_records.push(entry);
      }

      existing.metadata.updated_at = new Date().toISOString();

      const content = this.generateMarkdown(existing);
      writeFileSync(path, content, "utf-8");
      return path;
    });
  }

  /**
   * 追加日度追踪记录（自动去重：同日期视为重复，用新记录替换）
   */
  appendTracking(symbol: string, name: string, tracking: TradeLogTracking): string {
    const path = this.getLogPath(symbol, name);

    return FileLockService.withLockSync(path, () => {
      if (!existsSync(path)) {
        throw new Error(`交易日志不存在: ${symbol}-${name}`);
      }

      const existing = this.parseMarkdown(readFileSync(path, "utf-8"));

      // 去重检查：同日期视为重复，用新记录替换
      const dupIndex = existing.tracking_records.findIndex(
        r => r.date === tracking.date
      );
      if (dupIndex !== -1) {
        existing.tracking_records[dupIndex] = tracking;
      } else {
        existing.tracking_records.push(tracking);
      }

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
   * 解析 Markdown 内容 — 完整版
   * 支持格式变体：
   * - 执行记录表（6列）：日期 | 操作 | 股数 | 价格 | 金额 | 备注
   * - 日度追踪表（5~6列）：日期 | 收盘价 | 涨跌幅 | 浮盈% | 持仓 | 备注(可选)
   * - 追踪表特殊行：日期 | 📊 盘后分析 | 持仓 | 收盘价 | ~市值 | 备注（多行）
   * - 兼容表头分隔符出现在数据行之后（招商银行格式异常）
   */
  private parseMarkdown(content: string): TradeLogData {
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

    // 提取持仓总览
    const holdings_summary = this.parseHoldingsSummary(lines);

    // 提取各个章节的原始 Markdown 文本
    const entry_logic = this.extractSection(content, "## 🏗️ 建仓逻辑", "---");
    const operation_plan = this.extractSection(content, "## 🎯 操作计划", "---");

    // 解析执行记录表格和日度追踪表格
    const execution_records = this.parseExecutionTable(lines);
    const tracking_records = this.parseTrackingTable(lines);
    const follow_up_items = this.parseFollowUpItems(lines);

    return {
      metadata,
      holdings_summary,
      entry_logic,
      operation_plan,
      execution_records,
      tracking_records,
      follow_up_items,
    };
  }

  /**
   * 从持仓总览表格解析持仓数据
   */
  private parseHoldingsSummary(lines: string[]) {
    const result = { total_shares: 0, avg_cost: 0, total_investment: 0, current_price: undefined as number | undefined, float_pnl_pct: undefined as number | undefined };

    // 找到 「## 📋 持仓总览」 之后到下一个 「---」 之间的行
    let inSection = false;
    for (const line of lines) {
      if (line.includes("## 📋 持仓总览") || line.includes("## 📋")) {
        inSection = true;
        continue;
      }
      if (inSection && line.trim() === "---") break;
      if (!inSection) continue;
      if (!line.startsWith("|") || line.includes("|---")) continue;

      const cells = line.split("|").map(c => c.trim()).filter(c => c);
      if (cells.length < 2) continue;

      // cells[0]=项目 cells[1]=数值
      const label = cells[0].replace(/\*\*/g, "").trim();
      const value = cells[1].replace(/\*\*/g, "").trim();

      // 解析总持仓股数: "1,200 股"、"400 股"、"2,100 股"
      if (label.includes("总持仓") || label.includes("总建仓")) {
        const num = parseFloat(value.replace(/[^0-9.\-]/g, ""));
        if (!isNaN(num)) result.total_shares = num;
      }
      // 解析加权成本: "¥126.67"、"¥78.00"
      else if (label.includes("成本") || label.includes("均价")) {
        const num = parseFloat(value.replace(/[¥$]/g, "").replace(/,/g, ""));
        if (!isNaN(num)) result.avg_cost = num;
      }
      // 解析总投入: "¥152,004"
      else if (label.includes("总投入")) {
        const num = parseFloat(value.replace(/[¥$]/g, "").replace(/,/g, ""));
        if (!isNaN(num)) result.total_investment = num;
      }
      // 解析当前价
      else if (label.includes("当前价")) {
        const num = parseFloat(value.replace(/[¥$]/g, "").replace(/,/g, ""));
        if (!isNaN(num)) result.current_price = num;
      }
      // 解析当前浮盈
      else if (label.includes("浮盈") || label.includes("浮亏")) {
        const pctMatch = value.match(/([+-]?\d+\.?\d*)%/);
        if (pctMatch) {
          result.float_pnl_pct = parseFloat(pctMatch[1]);
        }
      }
    }

    return result;
  }

  /**
   * 解析表格数据行
   * 跳过表头行、分隔符行、纯空表格行（如 "（暂无）"）
   *
   * 支持的格式变体：
   * 1. 标准：表头 → 分隔符 → 数据行（正常生成）
   * 2. 异常：表头 → 数据行 → 分隔符（招商银行，生成时先写数据后写分隔符）
   * 3. 异常：表头缺失分隔符（单个表头无后续）
   */
  private parseTableDataRows(lines: string[], sectionHeaderMarker: string): string[][] {
    const rows: string[][] = [];
    let inSection = false;

    for (const line of lines) {
      // 进入目标章节
      if (line.includes(sectionHeaderMarker)) {
        inSection = true;
        continue;
      }

      if (!inSection) continue;

      // 遇到下一个章节退出
      if (line.startsWith("## ") && !line.includes(sectionHeaderMarker)) break;

      if (!line.startsWith("|")) continue;

      // 跳过分隔符行（|---| 或 |--- |---| 样式）
      if (/^\|[-:\s|]+\|?$/.test(line)) continue;

      // 拆分单元格
      const cells = line.split("|").map(c => c.trim()).filter(c => c);

      // 跳过空表格占位行（如 "（暂无）"、"（待补充）"、"-"）
      if (cells.length > 0 && /^[（(]/.test(cells[0])) continue;

      // 跳过表头行（兼容异常格式：表头行不是标准分隔符，但 cells[0] 是中文标头关键词）
      if (cells.length >= 2) {
        const firstCell = cells[0].replace(/\*\*/g, "").trim();
        const secondCell = cells[1].replace(/\*\*/g, "").trim();
        // 检测表头: "日期"、"项目" 等标头关键词出现在首列
        if (/^(日期|项目|收盘价|维度|价格区间|位置|档次)/.test(firstCell) &&
            /^(操作|数值|涨跌幅|判断|操作|说明|价格|目标价)/.test(secondCell)) {
          continue;
        }
      }

      rows.push(cells);
    }

    return rows;
  }

  /**
   * 解析执行记录表格
   * 格式：日期 | 操作 | 股数 | 价格 | 金额 | 备注
   *
   * 支持的格式变体：
   * - 日期格式：YYYY-MM-DD、"约2025年3月"、"2026-05-11"（含**粗体包裹）
   * - 股数格式："1,500"、"+500"、"400"
   * - 价格格式："¥6.78"、"¥10.97 涨停"、"6.78"
   * - 金额格式："¥10,170"、"+¥7,210"、"-"
   * - 过期过滤：跳过日期为"—"、"—"、"——" 的汇总行或分隔行
   */
  private parseExecutionTable(lines: string[]): TradeLogEntry[] {
    const dataRows = this.parseTableDataRows(lines, "## 📝 执行记录");
    const records: TradeLogEntry[] = [];

    for (const rawCells of dataRows) {
      // 去除所有单元格内的 ** 粗体标记
      const cells = rawCells.map(c => c.replace(/\*\*/g, "").trim());

      // 需要至少5列：日期、操作、股数、价格、金额；第6列备注可选
      if (cells.length < 5) continue;

      // 跳过非真实交易行：日期为 "—" / "——" / "-"（汇总行、分隔行）
      const rawDate = cells[0];
      if (/^[—\-–]+$/.test(rawDate)) continue;

      const date = rawDate;
      const operation = cells[1];

      // 跳过占位行：操作列包含 "剩余持仓"、"合计" 等非交易操作
      if (/^(剩余持仓|合计|小计)/.test(operation)) continue;

      // 解析股数：可能的格式 "1,500"、"+500"、"400"、"-360"
      const qtyStr = cells[2].replace(/[^0-9.\-]/g, "");
      const quantity = parseFloat(qtyStr);
      if (isNaN(quantity)) continue;

      // 解析价格：可能的格式 "¥6.78"、"¥10.97 涨停"、"6.78"
      const priceStr = cells[3].replace(/[¥$]/g, "").replace(/,/g, "").trim();
      const priceMatch = priceStr.match(/(\d+\.?\d*)/);
      const price = priceMatch ? parseFloat(priceMatch[1]) : 0;

      // 解析金额：可能的格式 "¥10,170"、"+¥7,210"、"-"
      const amountStr = cells[4].replace(/[¥$]/g, "").replace(/,/g, "").trim();
      const amountMatch = amountStr.match(/([+-]?\d+\.?\d*)/);
      const amount = amountMatch ? parseFloat(amountMatch[1]) : 0;

      const notes = cells.length >= 6 ? cells.slice(5).join(" | ") : "";

      records.push({ date, operation, quantity, price, amount, notes });
    }

    return records;
  }

  /**
   * 解析日度追踪表格
   * 标准格式：日期 | 收盘价 | 涨跌幅 | 浮盈% | 持仓 | 备注(可选)
   * 特殊格式（盘后分析行）：日期 | 📊 盘后分析 | 持仓 | 收盘价 | ~市值 | 备注
   */
  private parseTrackingTable(lines: string[]): TradeLogTracking[] {
    const dataRows = this.parseTableDataRows(lines, "## 📈 日度追踪");
    const records: TradeLogTracking[] = [];

    for (const rawCells of dataRows) {
      if (rawCells.length < 3) continue;

      // 去除所有单元格内的 ** 粗体标记
      const cells = rawCells.map(c => c.replace(/\*\*/g, "").trim());

      // 跳过表头行和占位行（如日期为 "日期" 或 "（暂无）"）
      const rawDate = cells[0];
      if (/^[（(]/.test(rawDate)) continue;
      if (/(暂无|待补充)/.test(rawDate)) continue;
      if (/^[—\-–]+$/.test(rawDate)) continue;
      // 如果是表头关键词（中芯国际的追踪表头 "日期" 未被白名单捕获时的手动兜底）
      if (rawDate === "日期" && cells.length >= 2 && (cells[1] === "收盘价" || cells[1].includes("收盘价"))) continue;

      const date = rawDate;

      // 检查是否是盘后分析特殊行
      const secondCell = cells[1];

      if (secondCell.includes("盘后分析") || secondCell.includes("量化巡检")) {
        // 特殊格式：日期 | 📊 盘后分析 | 持仓 | 收盘价 | ~市值 | 备注
        const notesText = cells.slice(Math.min(4, cells.length - 1)).join(" | ");

        let position = 0;
        let closePrice = 0;
        let changePct = 0;
        let floatPnlPct = 0;

        // cells[2] = 持仓（可能 "1,200" 或 "1,200 股"）
        if (cells.length >= 3) {
          const posNum = parseFloat(cells[2].replace(/[^0-9.\-]/g, ""));
          if (!isNaN(posNum)) position = posNum;
        }
        // cells[3] = 收盘价（可能 "¥117.90" 或 "¥117.90"）
        if (cells.length >= 4) {
          const priceNum = parseFloat(cells[3].replace(/[¥$]/g, "").replace(/,/g, ""));
          if (!isNaN(priceNum)) closePrice = priceNum;
        }

        // 尝试从备注中提取浮盈和涨跌幅（盘后分析行不直接包含这些字段，但备注可能有）
        const pnlMatch = notesText.match(/浮[盈亏]\s*([+-]?\d+\.?\d*)%?/);
        if (pnlMatch) floatPnlPct = parseFloat(pnlMatch[1]);

        records.push({
          date,
          close_price: closePrice,
          change_pct: changePct,
          float_pnl_pct: floatPnlPct || 0,
          position,
          notes: notesText,
        });
      } else {
        // 标准格式：日期 | 收盘价 | 涨跌幅 | 浮盈% | 持仓 | 备注(可选)
        let closePrice = 0;
        let changePct = 0;
        let floatPnlPct = 0;
        let position = 0;
        let notesText = "";

        // 收盘价
        const priceStr = secondCell.replace(/[¥$]/g, "").replace(/,/g, "").trim();
        const priceMatch = priceStr.match(/([+-]?\d+\.?\d*)/);
        if (priceMatch) closePrice = parseFloat(priceMatch[1]);

        // 涨跌幅
        if (cells.length >= 3) {
          const pctMatch = cells[2].match(/([+-]?\d+\.?\d*)%/);
          if (pctMatch) changePct = parseFloat(pctMatch[1]);
        }

        // 浮盈%
        if (cells.length >= 4) {
          const pctMatch = cells[3].match(/([+-]?\d+\.?\d*)%/);
          if (pctMatch) floatPnlPct = parseFloat(pctMatch[1]);
        }

        // 持仓：格式 "400 股"、"1,200 股"、"400 股"、"-"
        if (cells.length >= 5) {
          const posNum = parseFloat(cells[4].replace(/[^0-9.\-]/g, ""));
          if (!isNaN(posNum)) position = posNum;
        }

        // 备注（第6列）
        if (cells.length >= 6) {
          notesText = cells.slice(5).join(" | ");
        }

        records.push({
          date,
          close_price: closePrice,
          change_pct: changePct,
          float_pnl_pct: floatPnlPct,
          position,
          notes: notesText,
        });
      }
    }

    return records;
  }

  /**
   * 解析后续跟踪要点
   * 格式：- [ ] 要点文字
   */
  private parseFollowUpItems(lines: string[]): string[] {
    const items: string[] = [];
    let inSection = false;

    for (const line of lines) {
      if (line.includes("## 🔄 后续跟踪要点")) {
        inSection = true;
        continue;
      }
      if (!inSection) continue;
      if (line.startsWith("## ") && !line.includes("后续跟踪")) break;

      // 匹配 "- [ ] xxx" 格式
      const match = line.match(/^-\s*\[\s*[ xX]?\s*\]\s*(.+)/);
      if (match) {
        const text = match[1].trim();
        if (text !== "暂无") {
          items.push(text);
        }
      }
    }

    return items;
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
