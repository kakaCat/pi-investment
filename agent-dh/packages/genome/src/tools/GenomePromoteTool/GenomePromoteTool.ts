import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import { genomePromotePrompt, type GenomePromoteParams, type GenomePromoteResult } from './prompt';
import type { GenomeWriteHost } from '../host';
import {
  readGenomeJson,
  writeGenomeJson,
  gitCommit,
  appendChangelog,
  type GenomeMetadata,
} from '../../store';
import { promoteCandidate } from '../../versioning';
import { guardConstitution } from '../../guard';

export class GenomePromoteTool extends BaseTool<GenomePromoteParams, GenomePromoteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_promote',
    category: 'genome',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = genomePromotePrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any,
    private lockGuard: any,
    private host?: GenomeWriteHost
  ) {
    super();
  }

  protected validate(params: GenomePromoteParams): ValidationResult {
    const { section, reason } = params;

    if (!this.genomeData.sections || !this.genomeData.sections[section]) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'section',
        issue: `段 ${section} 不存在`,
        expected: `可用段: ${this.genomeData.sections ? Object.keys(this.genomeData.sections).join(', ') : '(无)'}`,
      };
    }

    if (!reason || reason.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'reason',
        issue: '必须提供转正理由',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomePromoteParams, context: ToolContext): Promise<GenomePromoteResult> {
    const { section, reason } = params;

    let data: GenomeMetadata = this.genomeData;
    try {
      data = readGenomeJson(this.genomeDir);
    } catch { /* 回退内存数据 */ }

    const release = await this.lockGuard.acquire();

    try {
      // 宪法层禁止转正
      guardConstitution(section, data);

      // 转正（改 history 标记，不动段内容与版本号）
      const newGenomeData = promoteCandidate(data, section, reason);
      writeGenomeJson(this.genomeDir, newGenomeData);

      // CHANGELOG
      try {
        appendChangelog(this.genomeDir, newGenomeData.history![newGenomeData.history!.length - 1]);
      } catch { /* 不阻塞 */ }

      // git commit（promote 只改元数据；标签用当前代数）
      const sectionVersion = newGenomeData.sections[section].version;
      let gitHash: string | undefined;
      try {
        gitHash = gitCommit(
          this.genomeDir,
          newGenomeData.genome_version,
          section,
          sectionVersion,
          sectionVersion,
          reason,
          'promote'
        );
      } catch { /* 非 git 环境 */ }

      // 补 commit hash
      if (gitHash) {
        const pEntries = newGenomeData.history!;
        pEntries[pEntries.length - 1].git_commit = gitHash;
        writeGenomeJson(this.genomeDir, newGenomeData);
      }

      // 同步内存
      Object.assign(this.genomeData, newGenomeData);

      return {
        success: true,
        genome_version: newGenomeData.genome_version,
        section,
        section_version: sectionVersion,
        git_commit: gitHash,
      };
    } finally {
      release();
    }
  }

  protected wrap(data: GenomePromoteResult, context: ToolContext): ToolResponse<GenomePromoteResult> {
    const { section, section_version, genome_version, git_commit } = data;
    let message = `${section} v${section_version} 转正成功 (${genome_version})`;
    if (git_commit) message += ` [${git_commit}]`;

    return {
      success: true,
      data,
      message,
      metadata: {
        section,
        section_version,
        genome_version,
        commit_hash: git_commit,
      },
    };
  }
}
