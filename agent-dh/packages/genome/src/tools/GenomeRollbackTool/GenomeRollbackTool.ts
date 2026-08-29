import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { genomeRollbackPrompt, type GenomeRollbackParams, type GenomeRollbackResult } from './prompt';

export class GenomeRollbackTool extends BaseTool<GenomeRollbackParams, GenomeRollbackResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_rollback',
    category: 'genome',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = genomeRollbackPrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any,
    private lockGuard: any,
    private versionManager: any
  ) {
    super();
  }

  protected validate(params: GenomeRollbackParams): ValidationResult {
    const { section, target_version } = params;

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

    // 检查 target_version 格式
    if (!target_version || !/^\d+\.\d+\.\d+$/.test(target_version)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'target_version',
        issue: `无效的版本号格式: ${target_version}`,
        expected: '语义化版本号，如 1.0.0',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeRollbackParams, context: ToolContext): Promise<GenomeRollbackResult> {
    const { section, target_version } = params;

    // 获取锁
    const release = await this.lockGuard.acquire();
    try {
      const oldVersion = this.genomeData.sections[section].version;

      // 从版本历史中查找目标版本
      const historyPath = path.join(this.genomeDir, 'history', section, `${target_version}.md`);
      if (!fs.existsSync(historyPath)) {
        throw new Error(`版本 ${target_version} 不存在于历史记录中`);
      }

      // 读取目标版本内容
      const restoredContent = fs.readFileSync(historyPath, 'utf-8');

      // 写入当前文件
      const filePath = path.join(this.genomeDir, 'sections', `${section}.md`);
      fs.writeFileSync(filePath, restoredContent, 'utf-8');

      // 更新 metadata
      this.genomeData.sections[section].version = target_version;
      this.genomeData.sections[section].updated_at = new Date().toISOString();

      const metaPath = path.join(this.genomeDir, 'genome.json');
      fs.writeFileSync(metaPath, JSON.stringify(this.genomeData, null, 2), 'utf-8');

      // Git 提交
      let commitHash: string | undefined;
      try {
        execSync(`git add "${filePath}" "${metaPath}"`, { cwd: this.genomeDir });
        execSync(`git commit -m "genome: rollback ${section} to v${target_version}"`, { cwd: this.genomeDir });
        commitHash = execSync('git rev-parse --short HEAD', { cwd: this.genomeDir })
          .toString()
          .trim();
      } catch (error) {
        commitHash = undefined;
      }

      // 生成内容预览（前 200 字符）
      const contentPreview = restoredContent.substring(0, 200) + (restoredContent.length > 200 ? '...' : '');

      return {
        section,
        old_version: oldVersion,
        restored_version: target_version,
        content_preview: contentPreview,
        commit_hash: commitHash,
      };
    } finally {
      release();
    }
  }

  protected wrap(data: GenomeRollbackResult, context: ToolContext): ToolResponse<GenomeRollbackResult> {
    const { section, old_version, restored_version, commit_hash } = data;

    let message = `${section}: v${old_version} 回滚到 v${restored_version}`;
    if (commit_hash) {
      message += ` [${commit_hash}]`;
    }

    return {
      success: true,
      data,
      message,
      metadata: {
        section,
        version_change: `${old_version} → ${restored_version}`,
        commit_hash,
      },
    };
  }
}
