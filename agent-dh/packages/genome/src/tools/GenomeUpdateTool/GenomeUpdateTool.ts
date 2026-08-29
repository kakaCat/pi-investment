import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { genomeUpdatePrompt, type GenomeUpdateParams, type GenomeUpdateResult } from './prompt';

export class GenomeUpdateTool extends BaseTool<GenomeUpdateParams, GenomeUpdateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_update',
    category: 'genome',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = genomeUpdatePrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any,
    private lockGuard: any,
    private versionManager: any
  ) {
    super();
  }

  protected validate(params: GenomeUpdateParams): ValidationResult {
    const { section, content, reason } = params;

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

    // 检查 content 不为空
    if (!content || content.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'content',
        issue: '内容不能为空',
      };
    }

    // 检查 reason 不为空
    if (!reason || reason.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'reason',
        issue: '必须提供更新原因',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeUpdateParams, context: ToolContext): Promise<GenomeUpdateResult> {
    const { section, content, reason } = params;

    // 获取锁
    const release = await this.lockGuard.acquire();
    try {
      const filePath = path.join(this.genomeDir, 'sections', `${section}.md`);
      const oldContent = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf-8') : '';
      const oldVersion = this.genomeData.sections[section].version;

      // 计算 diff
      const diffSummary = this.calculateDiff(oldContent, content);

      // 写入新内容
      fs.writeFileSync(filePath, content, 'utf-8');

      // 更新版本号
      const newVersion = this.versionManager.bumpVersion(oldVersion, 'minor');
      this.genomeData.sections[section].version = newVersion;
      this.genomeData.sections[section].updated_at = new Date().toISOString();

      // 保存 metadata
      const metaPath = path.join(this.genomeDir, 'genome.json');
      fs.writeFileSync(metaPath, JSON.stringify(this.genomeData, null, 2), 'utf-8');

      // Git 提交
      let commitHash: string | undefined;
      try {
        execSync(`git add "${filePath}" "${metaPath}"`, { cwd: this.genomeDir });
        execSync(`git commit -m "genome: update ${section} - ${reason}"`, { cwd: this.genomeDir });
        commitHash = execSync('git rev-parse --short HEAD', { cwd: this.genomeDir })
          .toString()
          .trim();
      } catch (error) {
        // Git 提交失败不影响更新操作
        commitHash = undefined;
      }

      return {
        section,
        old_version: oldVersion,
        new_version: newVersion,
        diff_summary: diffSummary,
        commit_hash: commitHash,
      };
    } finally {
      release();
    }
  }

  protected wrap(data: GenomeUpdateResult, context: ToolContext): ToolResponse<GenomeUpdateResult> {
    const { section, old_version, new_version, diff_summary, commit_hash } = data;

    const { added_lines, removed_lines, changed_lines } = diff_summary;
    let message = `${section}: v${old_version} → v${new_version}`;
    message += ` (+${added_lines}/-${removed_lines}/~${changed_lines})`;
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
        diff_summary,
        commit_hash,
      },
    };
  }

  private calculateDiff(oldContent: string, newContent: string): { added_lines: number; removed_lines: number; changed_lines: number } {
    const oldLines = oldContent.split('\n');
    const newLines = newContent.split('\n');

    let added = 0;
    let removed = 0;
    let changed = 0;

    const maxLen = Math.max(oldLines.length, newLines.length);
    for (let i = 0; i < maxLen; i++) {
      const oldLine = oldLines[i];
      const newLine = newLines[i];

      if (oldLine === undefined) {
        added++;
      } else if (newLine === undefined) {
        removed++;
      } else if (oldLine !== newLine) {
        changed++;
      }
    }

    return { added_lines: added, removed_lines: removed, changed_lines: changed };
  }
}
