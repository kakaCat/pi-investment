/**
 * versioning.ts - 基因组版本模型操作
 * RFC 007 P0-2 版本管理实施
 */
import type { GenomeMetadata, HistoryEntry, SectionMeta } from './store';
import { incrementGenomeVersion, trimHistory } from './store';

/**
 * 创建新的 history 条目
 */
export function createHistoryEntry(
  genomeData: GenomeMetadata,
  sectionName: string,
  reason: string,
  type: 'update' | 'rollback',
  gitCommit?: string,
  force?: boolean
): HistoryEntry {
  const sectionMeta = genomeData.sections[sectionName];
  
  return {
    version: genomeData.genome_version,
    section: sectionName,
    section_version: sectionMeta.version,
    parent: genomeData.genome_version,
    reason,
    ts: new Date().toISOString(),
    git_commit: gitCommit,
    author: 'agent',
    type,
    force,
  };
}

/**
 * 更新段后的版本推进
 * 返回新的 genomeData
 */
export function advanceVersion(
  genomeData: GenomeMetadata,
  sectionName: string,
  historyEntry: HistoryEntry
): GenomeMetadata {
  const newGenomeVersion = incrementGenomeVersion(genomeData.genome_version);
  const newSectionVersion = genomeData.sections[sectionName].version + 1;
  
  const newData: GenomeMetadata = {
    ...genomeData,
    genome_version: newGenomeVersion,
    updated_at: new Date().toISOString(),
    sections: {
      ...genomeData.sections,
      [sectionName]: {
        ...genomeData.sections[sectionName],
        version: newSectionVersion,
      },
    },
    history: [
      ...(genomeData.history || []),
      {
        ...historyEntry,
        version: newGenomeVersion,
        section_version: newSectionVersion,
      },
    ],
  };
  
  // 限制 history 长度
  newData.history = trimHistory(newData.history!, 50);
  
  return newData;
}

/**
 * 回滚后的版本推进
 * 回滚=新版本（内容同旧版，但代数+1）
 */
export function advanceVersionForRollback(
  genomeData: GenomeMetadata,
  sectionName: string,
  targetVersion: number,
  reason: string,
  gitCommit?: string
): GenomeMetadata {
  const newGenomeVersion = incrementGenomeVersion(genomeData.genome_version);
  const newSectionVersion = genomeData.sections[sectionName].version + 1;
  
  const historyEntry: HistoryEntry = {
    version: newGenomeVersion,
    section: sectionName,
    section_version: newSectionVersion,
    parent: genomeData.genome_version,
    reason: `回滚到 v${targetVersion}: ${reason}`,
    ts: new Date().toISOString(),
    git_commit: gitCommit,
    author: 'agent',
    type: 'rollback',
  };
  
  const newData: GenomeMetadata = {
    ...genomeData,
    genome_version: newGenomeVersion,
    updated_at: new Date().toISOString(),
    sections: {
      ...genomeData.sections,
      [sectionName]: {
        ...genomeData.sections[sectionName],
        version: newSectionVersion,
      },
    },
    history: [
      ...(genomeData.history || []),
      historyEntry,
    ],
  };
  
  newData.history = trimHistory(newData.history!, 50);
  
  return newData;
}

/**
 * 查询 history：按段、按版本范围
 */
export function queryHistory(
  genomeData: GenomeMetadata,
  sectionName?: string,
  limit?: number
): HistoryEntry[] {
  const history = genomeData.history || [];
  
  let filtered = sectionName
    ? history.filter(e => e.section === sectionName)
    : history;
  
  if (limit) {
    filtered = filtered.slice(-limit);
  }
  
  return filtered.reverse();  // 最新的在前
}

/**
 * 获取段的上一个版本号
 */
export function getPreviousSectionVersion(
  genomeData: GenomeMetadata,
  sectionName: string
): number | null {
  const history = genomeData.history || [];
  const sectionHistory = history
    .filter(e => e.section === sectionName)
    .sort((a, b) => b.section_version - a.section_version);
  
  if (sectionHistory.length < 2) {
    return null;  // 只有初始版本或没有历史
  }
  
  return sectionHistory[1].section_version;
}

/**
 * diff 两个版本的段内容
 */
export function diffSections(oldContent: string, newContent: string): {
  additions: number;
  deletions: number;
  diff: string;
} {
  const oldLines = oldContent.split('\n');
  const newLines = newContent.split('\n');
  
  let additions = 0;
  let deletions = 0;
  const diffLines: string[] = [];
  
  // 简单的行级 diff（未来可用 diff 库）
  const maxLen = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];
    
    if (oldLine === undefined) {
      diffLines.push(`+ ${newLine}`);
      additions++;
    } else if (newLine === undefined) {
      diffLines.push(`- ${oldLine}`);
      deletions++;
    } else if (oldLine !== newLine) {
      diffLines.push(`- ${oldLine}`);
      diffLines.push(`+ ${newLine}`);
      deletions++;
      additions++;
    } else {
      diffLines.push(`  ${oldLine}`);
    }
  }
  
  return {
    additions,
    deletions,
    diff: diffLines.join('\n'),
  };
}
