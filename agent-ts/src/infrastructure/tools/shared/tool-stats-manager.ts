/**
 * 工具使用统计持久化模块
 *
 * 功能：
 * - 记录每个工具的调用次数、成功率、平均耗时
 * - 持久化到 JSON 文件
 * - 定期生成统计报告
 * - 支持按时间范围查询
 */

import fs from 'fs';
import path from 'path';

/**
 * 工具统计数据结构
 */
export interface ToolStats {
  toolName: string;
  totalCalls: number;
  successCalls: number;
  failureCalls: number;
  totalDuration: number;
  avgDuration: number;
  lastCallAt: string;
  lastError?: string;
  successRate: number;
}

/**
 * 统计记录（单次调用）
 */
interface StatsRecord {
  toolName: string;
  timestamp: string;
  success: boolean;
  duration: number;
  error?: string;
}

/**
 * 工具使用统计管理器
 */
export class ToolStatsManager {
  private statsFile: string;
  private records: StatsRecord[] = [];
  private autoSaveInterval: NodeJS.Timeout | null = null;
  private isDirty = false;

  constructor(statsDir: string = '.pi-invest/tool-stats') {
    // 确保统计目录存在
    const baseDir = path.resolve(process.cwd(), statsDir);
    if (!fs.existsSync(baseDir)) {
      fs.mkdirSync(baseDir, { recursive: true });
    }

    this.statsFile = path.join(baseDir, 'tool-usage.json');
    this.loadStats();
    this.startAutoSave();
  }

  /**
   * 记录工具调用
   */
  recordCall(toolName: string, success: boolean, duration: number, error?: string): void {
    const record: StatsRecord = {
      toolName,
      timestamp: new Date().toISOString(),
      success,
      duration,
      error: error ? String(error) : undefined,
    };

    this.records.push(record);
    this.isDirty = true;

    // 限制内存中的记录数量（保留最近 10000 条）
    if (this.records.length > 10000) {
      this.records = this.records.slice(-10000);
    }
  }

  /**
   * 获取工具统计摘要
   */
  getStats(toolName?: string, fromDate?: Date): ToolStats[] {
    const filteredRecords = this.records.filter(record => {
      if (toolName && record.toolName !== toolName) return false;
      if (fromDate && new Date(record.timestamp) < fromDate) return false;
      return true;
    });

    // 按工具名分组
    const groupedStats = new Map<string, StatsRecord[]>();
    filteredRecords.forEach(record => {
      const existing = groupedStats.get(record.toolName) || [];
      existing.push(record);
      groupedStats.set(record.toolName, existing);
    });

    // 计算每个工具的统计数据
    const stats: ToolStats[] = [];
    groupedStats.forEach((records, name) => {
      const totalCalls = records.length;
      const successCalls = records.filter(r => r.success).length;
      const failureCalls = totalCalls - successCalls;
      const totalDuration = records.reduce((sum, r) => sum + r.duration, 0);
      const avgDuration = totalCalls > 0 ? totalDuration / totalCalls : 0;
      const lastCall = records[records.length - 1];
      const successRate = totalCalls > 0 ? (successCalls / totalCalls) * 100 : 0;

      stats.push({
        toolName: name,
        totalCalls,
        successCalls,
        failureCalls,
        totalDuration,
        avgDuration: Math.round(avgDuration),
        lastCallAt: lastCall.timestamp,
        lastError: lastCall.error,
        successRate: Math.round(successRate * 100) / 100,
      });
    });

    // 按调用次数降序排序
    return stats.sort((a, b) => b.totalCalls - a.totalCalls);
  }

  /**
   * 生成统计报告
   */
  generateReport(options?: { topN?: number; fromDate?: Date }): string {
    const { topN = 20, fromDate } = options || {};
    const allStats = this.getStats(undefined, fromDate);
    const topStats = allStats.slice(0, topN);

    const lines: string[] = [];
    lines.push('═══════════════════════════════════════════════════════════════');
    lines.push('                   工具使用统计报告');
    lines.push('═══════════════════════════════════════════════════════════════');
    lines.push('');

    if (fromDate) {
      lines.push(`统计范围: ${fromDate.toISOString()} 至今`);
    } else {
      lines.push('统计范围: 全部历史记录');
    }
    lines.push(`总工具数: ${allStats.length} 个`);
    lines.push(`总调用次数: ${allStats.reduce((sum, s) => sum + s.totalCalls, 0)} 次`);
    lines.push('');

    lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    lines.push(
      '工具名称'.padEnd(30) +
      '调用次数'.padStart(10) +
      '成功率'.padStart(10) +
      '平均耗时'.padStart(12)
    );
    lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    topStats.forEach(stat => {
      lines.push(
        stat.toolName.padEnd(30) +
        String(stat.totalCalls).padStart(10) +
        `${stat.successRate.toFixed(1)}%`.padStart(10) +
        `${stat.avgDuration}ms`.padStart(12)
      );
    });

    lines.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    lines.push('');

    // 慢工具告警（平均耗时 > 5秒）
    const slowTools = allStats.filter(s => s.avgDuration > 5000);
    if (slowTools.length > 0) {
      lines.push('⚠️  慢工具告警（平均耗时 > 5秒）:');
      slowTools.forEach(tool => {
        lines.push(`   • ${tool.toolName}: ${tool.avgDuration}ms`);
      });
      lines.push('');
    }

    // 低成功率告警（成功率 < 80%）
    const unreliableTools = allStats.filter(s => s.successRate < 80 && s.totalCalls >= 5);
    if (unreliableTools.length > 0) {
      lines.push('⚠️  低成功率告警（< 80%，至少5次调用）:');
      unreliableTools.forEach(tool => {
        lines.push(`   • ${tool.toolName}: ${tool.successRate.toFixed(1)}%`);
      });
      lines.push('');
    }

    lines.push('═══════════════════════════════════════════════════════════════');

    return lines.join('\n');
  }

  /**
   * 清空统计数据
   */
  clear(): void {
    this.records = [];
    this.isDirty = true;
    this.saveStats();
  }

  /**
   * 清理旧数据（保留指定天数）
   */
  cleanup(retentionDays: number = 30): number {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - retentionDays);

    const beforeCount = this.records.length;
    this.records = this.records.filter(
      record => new Date(record.timestamp) >= cutoffDate
    );
    const removedCount = beforeCount - this.records.length;

    if (removedCount > 0) {
      this.isDirty = true;
      this.saveStats();
    }

    return removedCount;
  }

  /**
   * 加载统计数据
   */
  private loadStats(): void {
    try {
      if (fs.existsSync(this.statsFile)) {
        const data = fs.readFileSync(this.statsFile, 'utf-8');
        this.records = JSON.parse(data);
        console.log(`[ToolStatsManager] 已加载 ${this.records.length} 条统计记录`);
      }
    } catch (error) {
      console.error('[ToolStatsManager] 加载统计数据失败:', error);
      this.records = [];
    }
  }

  /**
   * 保存统计数据
   */
  private saveStats(): void {
    if (!this.isDirty) return;

    try {
      fs.writeFileSync(this.statsFile, JSON.stringify(this.records, null, 2), 'utf-8');
      this.isDirty = false;
    } catch (error) {
      console.error('[ToolStatsManager] 保存统计数据失败:', error);
    }
  }

  /**
   * 启动自动保存（每5分钟）
   */
  private startAutoSave(): void {
    this.autoSaveInterval = setInterval(() => {
      if (this.isDirty) {
        this.saveStats();
        console.log('[ToolStatsManager] 自动保存统计数据');
      }
    }, 5 * 60 * 1000); // 5分钟
    // 后台定时器不应阻止进程退出（测试/脚本场景的 open handle 根因）
    this.autoSaveInterval.unref?.();
  }

  /**
   * 停止自动保存
   */
  stopAutoSave(): void {
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval);
      this.autoSaveInterval = null;
    }
    // 最后保存一次
    if (this.isDirty) {
      this.saveStats();
    }
  }

  /**
   * 导出统计数据（CSV格式）
   */
  exportToCsv(outputPath: string): void {
    const stats = this.getStats();
    const header = 'Tool Name,Total Calls,Success Calls,Failure Calls,Avg Duration (ms),Success Rate (%),Last Call At';
    const rows = stats.map(s =>
      `"${s.toolName}",${s.totalCalls},${s.successCalls},${s.failureCalls},${s.avgDuration},${s.successRate},"${s.lastCallAt}"`
    );

    const csv = [header, ...rows].join('\n');
    fs.writeFileSync(outputPath, csv, 'utf-8');
    console.log(`[ToolStatsManager] 统计数据已导出到: ${outputPath}`);
  }
}

// 全局单例
let globalStatsManager: ToolStatsManager | null = null;

/**
 * 获取全局统计管理器
 */
export function getStatsManager(): ToolStatsManager {
  if (!globalStatsManager) {
    globalStatsManager = new ToolStatsManager();
  }
  return globalStatsManager;
}

/**
 * 停止统计管理器（进程退出时调用）
 */
export function stopStatsManager(): void {
  if (globalStatsManager) {
    globalStatsManager.stopAutoSave();
    globalStatsManager = null;
  }
}

// 进程退出时自动保存
process.on('exit', () => {
  stopStatsManager();
});

process.on('SIGINT', () => {
  stopStatsManager();
  process.exit(0);
});

process.on('SIGTERM', () => {
  stopStatsManager();
  process.exit(0);
});
