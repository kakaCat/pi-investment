import { promises as fs } from 'fs';
import * as path from 'path';
import { getSessionDir } from '../../logging/observable-logger.js';

/**
 * 持久化结果接口
 */
export interface PersistedResult {
  success: boolean;
  filePath: string;
  summary?: string;
  metadata?: Record<string, any>;
  message: string;
  timestamp: string;
}

/**
 * 保存选项
 */
export interface SaveOptions {
  toolName: string;
  data: any;
  summary?: string;
  metadata?: Record<string, any>;
  autoCleanup?: boolean;
}

/**
 * 工具结果持久化类
 * 用于将大量数据写入本地文件，避免污染LLM上下文
 *
 * 存储位置：{sessionDir}/tool-results/
 * 文件命名：{toolName}_YYYYMMDD_HHmmss.json
 */
export class ToolResultPersister {
  private maxAgeMs: number;

  constructor(maxAgeHours: number = 24) {
    this.maxAgeMs = maxAgeHours * 60 * 60 * 1000;
  }

  /**
   * 获取存储目录路径（基于当前 session）
   */
  private getBaseDir(): string {
    const sessionDir = getSessionDir();
    if (!sessionDir) {
      // Fallback to .cache if no session directory available
      return path.join(process.cwd(), '.cache/tool-results');
    }
    return path.join(sessionDir, 'tool-results');
  }

  /**
   * 保存工具结果到本地文件
   */
  async saveResult(options: SaveOptions): Promise<PersistedResult> {
    const { toolName, data, summary, metadata, autoCleanup = true } = options;

    try {
      const baseDir = this.getBaseDir();

      // 确保目录存在
      await fs.mkdir(baseDir, { recursive: true });

      // 生成文件名：toolName_YYYYMMDD_HHmmss_RANDOM.json
      // RANDOM 用于避免并行调用在秒级时间戳相同时覆盖文件（Bug 2 fix）
      const timestamp = new Date().toISOString();
      const dateStr = timestamp.replace(/[-:]/g, '').split('.')[0].replace('T', '_');
      const randomSuffix = Math.random().toString(36).substring(2, 8);
      const fileName = `${toolName}_${dateStr}_${randomSuffix}.json`;
      const filePath = path.join(baseDir, fileName);

      // 构建文件内容
      const fileContent = {
        toolName,
        timestamp,
        metadata: metadata || {},
        data,
      };

      // 写入文件
      await fs.writeFile(filePath, JSON.stringify(fileContent, null, 2), 'utf-8');

      // 自动清理旧文件
      if (autoCleanup) {
        this.cleanup().catch(err => {
          console.error('清理旧文件失败:', err);
        });
      }

      // 生成摘要消息
      const dataSize = JSON.stringify(data).length;
      const summaryMessage = summary || this._generateSummary(data, dataSize);

      return {
        success: true,
        filePath,
        summary: summaryMessage,
        metadata: metadata || {},
        message: `数据已保存到 ${fileName}。${summaryMessage}\n\n💡 使用 Read 工具查看完整数据：Read({ file_path: "${filePath}" })`,
        timestamp,
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        success: false,
        filePath: '',
        message: `保存数据失败: ${errorMessage}`,
        timestamp: new Date().toISOString(),
      };
    }
  }

  /**
   * 读取持久化的结果
   */
  async readResult(filePath: string): Promise<any> {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  }

  /**
   * 清理过期的结果文件
   */
  async cleanup(maxAge?: number): Promise<void> {
    const maxAgeToUse = maxAge || this.maxAgeMs;
    const now = Date.now();
    const baseDir = this.getBaseDir();

    try {
      const files = await fs.readdir(baseDir);

      for (const file of files) {
        if (!file.endsWith('.json')) continue;

        const filePath = path.join(baseDir, file);
        const stats = await fs.stat(filePath);
        const age = now - stats.mtimeMs;

        if (age > maxAgeToUse) {
          await fs.unlink(filePath);
        }
      }
    } catch (error) {
      // 忽略目录不存在等错误
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
        throw error;
      }
    }
  }

  /**
   * 列出所有持久化的结果
   */
  async listResults(): Promise<Array<{ fileName: string; toolName: string; timestamp: string; size: number }>> {
    const baseDir = this.getBaseDir();

    try {
      const files = await fs.readdir(baseDir);
      const results = [];

      for (const file of files) {
        if (!file.endsWith('.json')) continue;

        const filePath = path.join(baseDir, file);
        const stats = await fs.stat(filePath);

        // 从文件名解析工具名（格式：toolName_YYYYMMDD_HHmmss.json）
        const match = file.match(/^(.+?)_\d{8}_\d{6}\.json$/);
        const toolName = match ? match[1] : 'unknown';

        results.push({
          fileName: file,
          toolName,
          timestamp: stats.mtime.toISOString(),
          size: stats.size,
        });
      }

      return results.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
        return [];
      }
      throw error;
    }
  }

  /**
   * 生成数据摘要
   */
  private _generateSummary(data: any, dataSize: number): string {
    const parts: string[] = [];

    // 数据大小
    if (dataSize > 1024 * 1024) {
      parts.push(`大小: ${(dataSize / 1024 / 1024).toFixed(2)} MB`);
    } else if (dataSize > 1024) {
      parts.push(`大小: ${(dataSize / 1024).toFixed(2)} KB`);
    } else {
      parts.push(`大小: ${dataSize} bytes`);
    }

    // 数组长度
    if (Array.isArray(data)) {
      parts.push(`包含 ${data.length} 条记录`);
    } else if (typeof data === 'object' && data !== null) {
      const keys = Object.keys(data);
      parts.push(`包含 ${keys.length} 个字段`);

      // 如果有数组字段，显示长度
      for (const key of keys) {
        if (Array.isArray(data[key])) {
          parts.push(`${key}: ${data[key].length} 项`);
        }
      }
    }

    return parts.join(', ');
  }
}

/**
 * 单例实例
 */
export const toolResultPersister = new ToolResultPersister();

/**
 * 便捷函数：保存结果
 */
export async function saveToolResult(options: SaveOptions): Promise<PersistedResult> {
  return toolResultPersister.saveResult(options);
}

/**
 * 便捷函数：读取结果
 */
export async function readToolResult(filePath: string): Promise<any> {
  return toolResultPersister.readResult(filePath);
}

/**
 * 便捷函数：清理过期结果
 */
export async function cleanupOldResults(maxAgeHours?: number): Promise<void> {
  const maxAgeMs = maxAgeHours ? maxAgeHours * 60 * 60 * 1000 : undefined;
  return toolResultPersister.cleanup(maxAgeMs);
}

/**
 * 便捷函数：列出所有结果
 */
export async function listToolResults(): Promise<Array<{ fileName: string; toolName: string; timestamp: string; size: number }>> {
  return toolResultPersister.listResults();
}
