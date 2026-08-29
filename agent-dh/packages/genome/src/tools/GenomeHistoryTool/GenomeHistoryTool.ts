import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { genomeHistoryPrompt, type GenomeHistoryParams, type GenomeHistoryResult, type GenomeVersionInfo } from './prompt';

export class GenomeHistoryTool extends BaseTool<GenomeHistoryParams, GenomeHistoryResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_history',
    category: 'genome',
    version: '1.0.0',
    timeoutMs: 5000,
  };

  protected readonly prompt = genomeHistoryPrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any
  ) {
    super();
  }

  protected validate(params: GenomeHistoryParams): ValidationResult {
    const { section, limit } = params;

    // 检查 section 是否存在
    if (!this.genomeData.sections[section]) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'section',
        issue: `段 ${section} 不存在`,
        expected: `可用段: ${Object.keys(this.genomeData.sections).join(', ')}`,
      };
    }

    // 检查 limit 范围
    if (limit !== undefined && (limit < 1 || limit > 100)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'limit',
        issue: `limit 必须在 1-100 之间，当前值: ${limit}`,
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeHistoryParams, context: ToolContext): Promise<GenomeHistoryResult> {
    const { section, limit = 10 } = params;
    const currentVersion = this.genomeData.sections[section].version;

    const historyDir = path.join(this.genomeDir, 'history', section);
    const history: GenomeVersionInfo[] = [];

    // 读取历史目录
    if (fs.existsSync(historyDir)) {
      const files = fs.readdirSync(historyDir);

      // 按版本号排序（从新到旧）
      const versionFiles = files
        .filter(f => f.endsWith('.md'))
        .map(f => {
          const version = f.replace('.md', '');
          const filePath = path.join(historyDir, f);
          const stats = fs.statSync(filePath);
          return { version, filePath, mtime: stats.mtime };
        })
        .sort((a, b) => b.mtime.getTime() - a.mtime.getTime())
        .slice(0, limit);

      // 读取每个版本的信息
      for (const { version, filePath, mtime } of versionFiles) {
        const content = fs.readFileSync(filePath, 'utf-8');
        const stats = fs.statSync(filePath);
        const preview = content.substring(0, 200) + (content.length > 200 ? '...' : '');

        history.push({
          version,
          timestamp: mtime.toISOString(),
          file_size: stats.size,
          preview,
        });
      }
    }

    return {
      section,
      current_version: currentVersion,
      history,
      total_versions: history.length,
    };
  }

  protected wrap(data: GenomeHistoryResult, context: ToolContext): ToolResponse<GenomeHistoryResult> {
    const { section, current_version, total_versions } = data;

    const message = `${section} (当前: v${current_version}): 找到 ${total_versions} 个历史版本`;

    return {
      success: true,
      data,
      message,
      metadata: {
        section,
        current_version,
        total_versions,
      },
    };
  }
}
