import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';
import { genomeUpdatePrompt, type GenomeUpdateParams, type GenomeUpdateResult } from './prompt';
import type { GenomeWriteHost } from '../host';
import {
  readGenomeJson,
  writeGenomeJson,
  writeSection,
  gitCommit,
  appendChangelog,
  computeRuleIdChanges,
  type GenomeMetadata,
} from '../../store';
import { createHistoryEntry, advanceVersion } from '../../versioning';
import {
  guardConstitution,
  validateVersion,
  validateBraces,
  validateSize,
  validateAndExtractRuleIds,
  checkTradingHours,
} from '../../guard';

const VALID_STAGES = ['active', 'candidate'] as const;

export class GenomeUpdateTool extends BaseTool<GenomeUpdateParams, GenomeUpdateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_update',
    category: 'genome',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = genomeUpdatePrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any,
    private lockGuard: any,
    private host?: GenomeWriteHost
  ) {
    super();
  }

  protected validate(params: GenomeUpdateParams): ValidationResult {
    const { section, content, reason, expected_section_version, stage } = params;

    // 检查 section 是否存在
    if (!this.genomeData.sections || !this.genomeData.sections[section]) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'section',
        issue: `段 ${section} 不存在`,
        expected: `可用段: ${this.genomeData.sections ? Object.keys(this.genomeData.sections).join(', ') : '(无)'}`,
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

    // 乐观锁版本号必须是正整数
    if (expected_section_version !== undefined &&
        (!Number.isInteger(expected_section_version) || expected_section_version < 1)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'expected_section_version',
        issue: '期望版本号必须是正整数（整数版本模型）',
      };
    }

    // stage 枚举
    if (stage && !(VALID_STAGES as readonly string[]).includes(stage)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'stage',
        issue: `无效的 stage: ${stage}`,
        expected: 'active 或 candidate',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeUpdateParams, context: ToolContext): Promise<GenomeUpdateResult> {
    const { section, content, reason, expected_section_version, stage, force } = params;

    // 重新读取 genome.json（避免内存数据过期，与原始实现一致）
    let data: GenomeMetadata = this.genomeData;
    try {
      data = readGenomeJson(this.genomeDir);
    } catch { /* 读取失败时回退内存数据 */ }

    const release = await this.lockGuard.acquire();
    let snapshot: { sectionContent: string; genomeJson: GenomeMetadata };

    try {
      // Step 1: 快照（金丝雀/异常失败自动还原）
      const filePath = path.join(this.genomeDir, 'sections', `${section}.md`);
      snapshot = {
        sectionContent: fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf-8') : '',
        genomeJson: data,
      };

      // Step 2-6: 安全守卫
      guardConstitution(section, data);  // 宪法层禁止修改
      validateVersion(expected_section_version, data.sections[section].version, section);
      validateBraces(content, section);
      validateSize(content, section);
      const ruleIds = validateAndExtractRuleIds(content, section);
      const hoursWarning = checkTradingHours(!!force);

      const oldVersion = data.sections[section].version;
      const diffSummary = this.calculateDiff(snapshot.sectionContent, content);

      // Step 7: 写入段文件
      writeSection(this.genomeDir, section, content);

      // Step 8: 版本推进 + history 条目
      const entry = createHistoryEntry(data, section, reason, 'update', undefined, !!force);
      if (stage) entry.stage = stage;
      const newData = advanceVersion(data, section, entry);

      // Step 9: 写入 genome.json
      writeGenomeJson(this.genomeDir, newData);

      // Step 10: 规则 ID 变更（changelog 用）
      const ruleChanges = computeRuleIdChanges(snapshot.sectionContent, content);

      // Step 11: 结构化 git 提交（非 git 环境不阻塞）
      let gitHash: string | undefined;
      try {
        gitHash = gitCommit(
          this.genomeDir,
          newData.genome_version,
          section,
          oldVersion,
          newData.sections[section].version,
          reason,
          'update'
        );
      } catch { /* 非 git 环境：不阻塞写入 */ }

      // Step 12: 回填 commit hash 到 history 条目
      if (gitHash) {
        const h = newData.history![newData.history!.length - 1];
        h.git_commit = gitHash;
        writeGenomeJson(this.genomeDir, newData);
      }

      // Step 13: CHANGELOG
      try {
        appendChangelog(this.genomeDir, newData.history![newData.history!.length - 1], ruleChanges);
      } catch { /* changelog 失败不阻塞 */ }

      // Step 14: 热替换段注册 + 渲染金丝雀（失败自动还原）
      if (this.host) {
        try {
          this.host.hotSwapSection(
            section,
            newData.genome_version,
            newData.sections[section].version,
            newData.sections[section].order,
            content
          );
          await this.host.canaryRender();
        } catch (renderError: any) {
          // 金丝雀失败 → 自动还原文件
          writeSection(this.genomeDir, section, snapshot.sectionContent);
          writeGenomeJson(this.genomeDir, snapshot.genomeJson);
          try {
            execSync('git add -A', { cwd: this.genomeDir, stdio: 'pipe' });
            execSync(`git commit -m "genome(${snapshot.genomeJson.genome_version}): canary-restore ${section} v${oldVersion} — 渲染金丝雀失败自动还原"`, { cwd: this.genomeDir, stdio: 'pipe' });
          } catch { /* 还原提交失败不阻塞 */ }
          throw new Error(`渲染金丝雀失败，已自动还原到 v${oldVersion}。错误: ${renderError.message}`);
        }
      }

      // Step 15: 同步插件内存
      Object.assign(this.genomeData, newData);

      // B-4 修复：undefined 字段会导致工具输出 "not lossless JSON"，按需拼装
      const result: GenomeUpdateResult = {
        success: true,
        section,
        old_version: oldVersion,
        new_version: newData.sections[section].version,
        genome_version: newData.genome_version,
        diff_summary: diffSummary,
        rule_id_changes: ruleChanges,
        git_commit: gitHash,
      };
      if (hoursWarning?.warning) result.warning = hoursWarning.warning;

      return result;
    } catch (error: any) {
      // 写入/git 阶段失败 → 还原快照（仅当已发生写入时）
      if (snapshot) {
        try {
          writeSection(this.genomeDir, section, snapshot.sectionContent);
          writeGenomeJson(this.genomeDir, snapshot.genomeJson);
        } catch { /* 还原失败不阻塞原始错误 */ }
      }
      throw error;
    } finally {
      release();
    }
  }

  protected wrap(data: GenomeUpdateResult, context: ToolContext): ToolResponse<GenomeUpdateResult> {
    const { section, old_version, new_version, diff_summary, git_commit, genome_version, warning } = data;

    const { added_lines, removed_lines, changed_lines } = diff_summary;
    let message = `${section}: v${old_version} → v${new_version} (${genome_version})`;
    message += ` +(${added_lines}/-${removed_lines}/~${changed_lines})`;
    if (git_commit) message += ` [${git_commit}]`;
    if (warning) message += ` ⚠️ ${warning}`;

    return {
      success: true,
      data,
      message,
      metadata: {
        section,
        version_change: `${old_version} → ${new_version}`,
        diff_summary,
        commit_hash: git_commit,
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
