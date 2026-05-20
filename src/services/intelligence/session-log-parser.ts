import * as fs from 'fs/promises';
import * as path from 'path';
import * as readline from 'readline';
import { createReadStream } from 'fs';
import type {
  SessionEvent,
  ToolCallEvent,
  ToolResultEvent,
  SessionMetadata,
  ToolStats,
  SessionAnalysis,
} from '../../types/session-log.js';

/**
 * Session 日志解析器
 * 从 .pi-invest/sessions 目录解析 session 日志
 */
export class SessionLogParser {
  private sessionDir: string;

  constructor(sessionDir: string) {
    this.sessionDir = sessionDir;
  }

  /**
   * 解析 session 日志并生成分析报告
   */
  async analyze(): Promise<SessionAnalysis> {
    // 1. 读取元数据
    const metadata = await this.parseMetadata();

    // 2. 解析事件日志
    const events = await this.parseEvents();

    // 3. 提取工具调用和结果
    const toolCalls = events.filter((e) => e.event === 'tool.call') as ToolCallEvent[];
    const toolResults = events.filter((e) => e.event === 'tool.result') as ToolResultEvent[];

    // 4. 构建工具统计
    const toolStatsMap = new Map<string, ToolStats>();

    for (const result of toolResults) {
      const { tool_name, success, duration_ms } = result;

      if (!toolStatsMap.has(tool_name)) {
        toolStatsMap.set(tool_name, {
          name: tool_name,
          callCount: 0,
          successCount: 0,
          failureCount: 0,
          totalDuration: 0,
          avgDuration: 0,
          errorRate: 0,
        });
      }

      const stats = toolStatsMap.get(tool_name)!;
      stats.callCount++;
      stats.totalDuration += duration_ms;
      if (success) {
        stats.successCount++;
      } else {
        stats.failureCount++;
      }
    }

    // 5. 计算平均值和错误率
    const toolStats = Array.from(toolStatsMap.values()).map((stats) => ({
      ...stats,
      avgDuration: stats.callCount > 0 ? stats.totalDuration / stats.callCount : 0,
      errorRate: stats.callCount > 0 ? stats.failureCount / stats.callCount : 0,
    }));

    // 6. 计算总体统计
    const totalToolCalls = toolStats.reduce((sum, s) => sum + s.callCount, 0);
    const totalToolFailures = toolStats.reduce((sum, s) => sum + s.failureCount, 0);
    const overallErrorRate = totalToolCalls > 0 ? totalToolFailures / totalToolCalls : 0;
    const totalDuration = toolStats.reduce((sum, s) => sum + s.totalDuration, 0);
    const avgToolDuration = totalToolCalls > 0 ? totalDuration / totalToolCalls : 0;

    // 7. 排序生成 Top 列表
    const topTools = [...toolStats].sort((a, b) => b.callCount - a.callCount).slice(0, 5);
    const slowestTools = [...toolStats].sort((a, b) => b.avgDuration - a.avgDuration).slice(0, 5);
    const mostFailedTools = [...toolStats]
      .filter((s) => s.failureCount > 0)
      .sort((a, b) => b.failureCount - a.failureCount)
      .slice(0, 5);

    return {
      metadata,
      toolStats,
      totalToolCalls,
      totalToolFailures,
      overallErrorRate,
      avgToolDuration,
      topTools,
      slowestTools,
      mostFailedTools,
    };
  }

  /**
   * 解析 metadata.json
   */
  private async parseMetadata(): Promise<SessionMetadata> {
    const metadataPath = path.join(this.sessionDir, 'metadata.json');
    const content = await fs.readFile(metadataPath, 'utf-8');
    return JSON.parse(content);
  }

  /**
   * 解析 events.jsonl（逐行读取，避免内存溢出）
   */
  private async parseEvents(): Promise<SessionEvent[]> {
    const eventsPath = path.join(this.sessionDir, 'events.jsonl');
    const events: SessionEvent[] = [];

    const fileStream = createReadStream(eventsPath);
    const rl = readline.createInterface({
      input: fileStream,
      crlfDelay: Infinity,
    });

    for await (const line of rl) {
      if (line.trim()) {
        try {
          const event = JSON.parse(line);
          events.push(event);
        } catch (error) {
          console.warn(`[SessionLogParser] 解析事件失败: ${line.slice(0, 100)}...`);
        }
      }
    }

    return events;
  }
}

/**
 * 从 session 目录解析日志
 */
export async function parseSessionLog(sessionDir: string): Promise<SessionAnalysis> {
  const parser = new SessionLogParser(sessionDir);
  return parser.analyze();
}
