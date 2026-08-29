import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { genomePromotePrompt, type GenomePromoteParams, type GenomePromoteResult } from './prompt';

export class GenomePromoteTool extends BaseTool<GenomePromoteParams, GenomePromoteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_promote',
    category: 'genome',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = genomePromotePrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any,
    private lockGuard: any,
    private versionManager: any
  ) {
    super();
  }

  protected validate(params: GenomePromoteParams): ValidationResult {
    const { section, increment, reason } = params;

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

    // 检查 increment 类型
    if (!['major', 'minor', 'patch'].includes(increment)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'increment',
        issue: `无效的增量类型: ${increment}`,
        expected: 'major, minor, 或 patch',
      };
    }

    // 检查 reason 不为空
    if (!reason || reason.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'reason',
        issue: '必须提供版本提升原因',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomePromoteParams, context: ToolContext): Promise<GenomePromoteResult> {
    const { section, increment, reason } = params;

    // 获取锁
    const release = await this.lockGuard.acquire();
    try {
      const oldVersion = this.genomeData.sections[section].version;

      // 计算新版本号
      const newVersion = this.versionManager.bumpVersion(oldVersion, increment);

      // 更新 metadata（不修改文件内容）
      this.genomeData.sections[section].version = newVersion;
      this.genomeData.sections[section].updated_at = new Date().toISOString();

      const metaPath = path.join(this.genomeDir, 'genome.json');
      fs.writeFileSync(metaPath, JSON.stringify(this.genomeData, null, 2), 'utf-8');

      // Git 提交
      let commitHash: string | undefined;
      try {
        execSync(`git add "${metaPath}"`, { cwd: this.genomeDir });
        execSync(`git commit -m "genome: promote ${section} to v${newVersion} - ${reason}"`, { cwd: this.genomeDir });
        commitHash = execSync('git rev-parse --short HEAD', { cwd: this.genomeDir })
          .toString()
          .trim();
      } catch (error) {
        commitHash = undefined;
      }

      return {
        section,
        old_version: oldVersion,
        new_version: newVersion,
        increment_type: increment,
        commit_hash: commitHash,
      };
    } finally {
      release();
    }
  }

  protected wrap(data: GenomePromoteResult, context: ToolContext): ToolResponse<GenomePromoteResult> {
    const { section, old_version, new_version, increment_type, commit_hash } = data;

    let message = `${section}: v${old_version} → v${new_version} (${increment_type})`;
    if (commit_hash) {
      message += ` [${commit_hash}]`;
    }

    return {
      success: true,
      data,
      message,
      metadata: {
        section,
        version_change: `${old_version} → ${new_version}`,
        increment_type,
        commit_hash,
      },
    };
  }
}
