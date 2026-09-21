import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { genomeRollbackPrompt, type GenomeRollbackParams, type GenomeRollbackResult } from './prompt';
import type { GenomeWriteHost } from '../host';
import {
  readGenomeJson,
  writeGenomeJson,
  readSection,
  writeSection,
  gitCommit,
  appendChangelog,
  getHistoricalSection,
  type GenomeMetadata,
} from '../../store';
import { advanceVersionForRollback, getPreviousSectionVersion } from '../../versioning';
import { guardConstitution, validateBraces, validateSize } from '../../guard';

export class GenomeRollbackTool extends BaseTool<GenomeRollbackParams, GenomeRollbackResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_rollback',
    category: 'genome',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = genomeRollbackPrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any,
    private lockGuard: any,
    private host?: GenomeWriteHost
  ) {
    super();
  }

  protected validate(params: GenomeRollbackParams): ValidationResult {
    const { section, to_section_version, reason } = params;

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
        issue: '必须提供回滚理由',
      };
    }

    if (to_section_version !== undefined &&
        (!Number.isInteger(to_section_version) || to_section_version < 1)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'to_section_version',
        issue: '目标版本必须是正整数（整数版本模型）',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeRollbackParams, context: ToolContext): Promise<GenomeRollbackResult> {
    const { section, to_section_version, reason } = params;

    let data: GenomeMetadata = this.genomeData;
    try {
      data = readGenomeJson(this.genomeDir);
    } catch { /* 回退内存数据 */ }

    const release = await this.lockGuard.acquire();
    let snapshot: { sectionContent: string; genomeJson: GenomeMetadata } | null = null;

    try {
      // 宪法层禁止回滚
      guardConstitution(section, data);

      // 确定目标版本：显式指定，否则回退到上一版本
      const targetVersion = to_section_version !== undefined
        ? to_section_version
        : getPreviousSectionVersion(data, section);

      if (targetVersion === null) {
        throw new Error(`段 ${section} 没有可回滚的历史版本`);
      }

      // 从 git 历史获取目标版本内容
      const targetContent = getHistoricalSection(this.genomeDir, section, targetVersion, data);
      if (!targetContent) {
        throw new Error(`无法从 git 历史获取 ${section} v${targetVersion} 内容`);
      }

      // 校验目标内容
      validateBraces(targetContent, section);
      validateSize(targetContent, section);

      // 备份（金丝雀失败自动还原，与 update 对称）
      snapshot = {
        genomeJson: { ...data },
        sectionContent: readSection(this.genomeDir, section),
      };

      const oldVersion = data.sections[section].version;
      const newVersion = oldVersion + 1;

      // 写入回滚内容
      writeSection(this.genomeDir, section, targetContent);

      // 更新 genome.json（回滚=新版本）
      const newGenomeData = advanceVersionForRollback(data, section, targetVersion, reason);
      writeGenomeJson(this.genomeDir, newGenomeData);

      // CHANGELOG
      try {
        appendChangelog(this.genomeDir, newGenomeData.history![newGenomeData.history!.length - 1]);
      } catch { /* 不阻塞 */ }

      // git commit（非 git 环境不阻塞）
      let gitHash: string | undefined;
      try {
        gitHash = gitCommit(
          this.genomeDir,
          newGenomeData.genome_version,
          section,
          oldVersion,
          newVersion,
          reason,
          'rollback',
          targetVersion
        );
      } catch { /* 非 git 环境 */ }

      // 补 commit hash 进 history
      if (gitHash) {
        const rbEntries = newGenomeData.history!;
        rbEntries[rbEntries.length - 1].git_commit = gitHash;
        writeGenomeJson(this.genomeDir, newGenomeData);
      }

      // 热替换 + 金丝雀
      if (this.host) {
        try {
          this.host.hotSwapSection(
            section,
            newGenomeData.genome_version,
            newVersion,
            newGenomeData.sections[section].order,
            targetContent
          );
          await this.host.canaryRender();
        } catch (renderError: any) {
          writeSection(this.genomeDir, section, snapshot.sectionContent);
          writeGenomeJson(this.genomeDir, snapshot.genomeJson);
          try {
            execSync('git add -A', { cwd: this.genomeDir, stdio: 'pipe' });
            execSync(`git commit -m "genome(${snapshot.genomeJson.genome_version}): canary-restore ${section} v${oldVersion} — 回滚金丝雀失败自动还原"`, { cwd: this.genomeDir, stdio: 'pipe' });
          } catch { /* 不阻塞 */ }
          throw new Error(`回滚后渲染金丝雀失败，已自动还原到 v${oldVersion}。错误: ${renderError.message}`);
        }
      }

      // 同步内存
      Object.assign(this.genomeData, newGenomeData);

      return {
        success: true,
        genome_version: newGenomeData.genome_version,
        section_version: newVersion,
        rolled_back_to: targetVersion,
        git_commit: gitHash,
      };
    } catch (error: any) {
      if (snapshot) {
        try {
          writeSection(this.genomeDir, section, snapshot.sectionContent);
          writeGenomeJson(this.genomeDir, snapshot.genomeJson);
        } catch { /* 不阻塞 */ }
      }
      throw error;
    } finally {
      release();
    }
  }

  protected wrap(data: GenomeRollbackResult, context: ToolContext): ToolResponse<GenomeRollbackResult> {
    const { section_version, rolled_back_to, git_commit, genome_version } = data;
    let message = `回滚到 v${rolled_back_to}，当前段版本 v${section_version} (${genome_version})`;
    if (git_commit) message += ` [${git_commit}]`;

    return {
      success: true,
      data,
      message,
      metadata: {
        section_version,
        rolled_back_to,
        commit_hash: git_commit,
      },
    };
  }
}
