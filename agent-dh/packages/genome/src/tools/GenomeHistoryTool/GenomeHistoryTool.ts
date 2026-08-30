import { BaseTool, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import { genomeHistoryPrompt, type GenomeHistoryParams, type GenomeHistoryResult, type GenomeHistoryEntry } from './prompt';
import { readGenomeJson, type GenomeMetadata } from '../../store';
import { queryHistory } from '../../versioning';

export class GenomeHistoryTool extends BaseTool<GenomeHistoryParams, GenomeHistoryResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_history',
    category: 'genome',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = genomeHistoryPrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any
  ) {
    super();
  }

  protected validate(params: GenomeHistoryParams): ValidationResult {
    const { limit } = params;

    if (limit !== undefined && (!Number.isInteger(limit) || limit < 1 || limit > 100)) {
      return {
        success: false,
        issue: `无效的 limit: ${limit}`,
        expected: '1-100 的整数',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeHistoryParams, context: ToolContext): Promise<GenomeHistoryResult> {
    const { section, limit } = params;

    let data: GenomeMetadata = this.genomeData;
    try {
      data = readGenomeJson(this.genomeDir);
    } catch { /* 回退内存数据 */ }

    const history = queryHistory(data, section, limit || 10);

    // B-4 修复：undefined 字段会导致工具输出 "not lossless JSON"，按需拼装
    const sanitized: GenomeHistoryEntry[] = history.map((e: any) => {
      const entry: GenomeHistoryEntry = {
        version: e.version,
        section: e.section,
        section_version: e.section_version,
        parent: e.parent,
        reason: e.reason,
        ts: e.ts,
      };
      if (e.author !== undefined) entry.author = e.author;
      if (e.type !== undefined) entry.type = e.type;
      if (e.git_commit !== undefined) entry.git_commit = e.git_commit;
      if (e.stage !== undefined) entry.stage = e.stage;
      if (e.force !== undefined) entry.force = e.force;
      if (e.baseline_version !== undefined) entry.baseline_version = e.baseline_version;
      return entry;
    });

    return { history: sanitized };
  }

  protected wrap(data: GenomeHistoryResult, context: ToolContext): ToolResponse<GenomeHistoryResult> {
    return {
      success: true,
      data,
      message: `共 ${data.history.length} 条历史记录`,
      metadata: {
        count: data.history.length,
      },
    };
  }
}
