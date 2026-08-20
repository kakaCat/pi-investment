/**
 * store.ts - 基因组文件与 git 存储操作
 * RFC 007 P0-2 版本化存储实施
 */
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

export interface GenomeMetadata {
  genome_version: string;
  updated_at: string;
  sections: Record<string, SectionMeta>;
  history?: HistoryEntry[];
}

export interface SectionMeta {
  class: 'constitution' | 'evolvable';
  version: number;
  order: number;
  locked?: boolean;
}

export interface HistoryEntry {
  version: string;
  section: string;
  section_version: number;
  parent: string;
  reason: string;
  ts: string;
  git_commit?: string;
  author: 'agent' | 'human';
  type: 'update' | 'rollback' | 'init';
  force?: boolean;
}

/**
 * 读取 genome.json
 */
export function readGenomeJson(genomeDir: string): GenomeMetadata {
  const genomePath = path.join(genomeDir, 'genome.json');
  if (!fs.existsSync(genomePath)) {
    throw new Error(`genome.json not found at ${genomePath}`);
  }
  return JSON.parse(fs.readFileSync(genomePath, 'utf-8'));
}

/**
 * 写入 genome.json（原子写）
 */
export function writeGenomeJson(genomeDir: string, data: GenomeMetadata): void {
  const genomePath = path.join(genomeDir, 'genome.json');
  const tmpPath = genomePath + '.tmp';
  
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2));
  fs.renameSync(tmpPath, genomePath);  // 原子替换
}

/**
 * 读取段文件内容
 */
export function readSection(genomeDir: string, sectionName: string): string {
  const filePath = path.join(genomeDir, 'sections', `${sectionName}.md`);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Section file not found: ${sectionName}.md`);
  }
  return fs.readFileSync(filePath, 'utf-8');
}

/**
 * 写入段文件内容（原子写）
 */
export function writeSection(genomeDir: string, sectionName: string, content: string): void {
  const sectionsDir = path.join(genomeDir, 'sections');
  if (!fs.existsSync(sectionsDir)) {
    fs.mkdirSync(sectionsDir, { recursive: true });
  }
  
  const filePath = path.join(sectionsDir, `${sectionName}.md`);
  const tmpPath = filePath + '.tmp';
  
  fs.writeFileSync(tmpPath, content, 'utf-8');
  fs.renameSync(tmpPath, filePath);  // 原子替换
}

/**
 * 递增基因组代数：g1 → g2
 */
export function incrementGenomeVersion(current: string): string {
  const match = current.match(/^g(\d+)$/);
  if (!match) {
    throw new Error(`Invalid genome_version format: ${current}. Expected g<N>`);
  }
  const num = parseInt(match[1], 10);
  return `g${num + 1}`;
}

/**
 * git 操作：检查是否初始化
 */
export function isGitRepo(genomeDir: string): boolean {
  const gitDir = path.join(genomeDir, '.git');
  return fs.existsSync(gitDir);
}

/**
 * git commit（结构化提交信息）
 * 返回 commit hash
 */
export function gitCommit(
  genomeDir: string,
  genomeVersion: string,
  sectionName: string,
  oldVersion: number,
  newVersion: number,
  reason: string,
  type: 'update' | 'rollback'
): string {
  if (!isGitRepo(genomeDir)) {
    throw new Error(`${genomeDir} is not a git repository. Run 'git init' first.`);
  }

  try {
    // git add
    execSync('git add genome.json sections/', { cwd: genomeDir, stdio: 'pipe' });
    
    // 结构化 commit message
    const action = type === 'rollback' ? 'rollback' : 'update';
    const versionChange = type === 'rollback' 
      ? `rollback to v${newVersion}` 
      : `v${oldVersion}→v${newVersion}`;
    const message = `genome(${genomeVersion}): ${action} ${sectionName} ${versionChange} — ${reason}`;
    
    execSync(`git commit -m "${message.replace(/"/g, '\\"')}"`, { 
      cwd: genomeDir, 
      stdio: 'pipe' 
    });
    
    // 获取 commit hash
    const hash = execSync('git rev-parse --short HEAD', { 
      cwd: genomeDir, 
      encoding: 'utf-8' 
    }).trim();
    
    return hash;
  } catch (error: any) {
    throw new Error(`Git commit failed: ${error.message}`);
  }
}

/**
 * 追加 CHANGELOG.md（人类可读摘要）
 */
export function appendChangelog(
  genomeDir: string,
  entry: HistoryEntry,
  ruleIdChanges?: { added: string[], removed: string[] }
): void {
  const changelogPath = path.join(genomeDir, 'CHANGELOG.md');
  
  // 首次创建时写入头部
  if (!fs.existsSync(changelogPath)) {
    fs.writeFileSync(changelogPath, '# 基因组变更日志\n\n', 'utf-8');
  }
  
  const timestamp = new Date(entry.ts).toLocaleString('zh-CN', { 
    timeZone: 'Asia/Shanghai',
    hour12: false 
  });
  
  let changelogEntry = `## ${entry.version} (${timestamp})\n\n`;
  changelogEntry += `- **段**: ${entry.section} (v${entry.section_version})\n`;
  changelogEntry += `- **类型**: ${entry.type === 'rollback' ? '回滚' : '更新'}\n`;
  changelogEntry += `- **理由**: ${entry.reason}\n`;
  
  if (ruleIdChanges && entry.section === 'rules') {
    if (ruleIdChanges.added.length > 0) {
      changelogEntry += `- **新增规则**: ${ruleIdChanges.added.join(', ')}\n`;
    }
    if (ruleIdChanges.removed.length > 0) {
      changelogEntry += `- **移除规则**: ${ruleIdChanges.removed.join(', ')}\n`;
    }
  }
  
  if (entry.git_commit) {
    changelogEntry += `- **提交**: ${entry.git_commit}\n`;
  }
  
  if (entry.force) {
    changelogEntry += `- ⚠️  **强制修改**（交易时段）\n`;
  }
  
  changelogEntry += '\n';
  
  // 追加
  fs.appendFileSync(changelogPath, changelogEntry, 'utf-8');
}

/**
 * 从 git 历史获取指定版本的段内容
 * 用于 genome_rollback
 */
export function getHistoricalSection(
  genomeDir: string,
  sectionName: string,
  targetVersion: number,
  genomeData: GenomeMetadata
): string | null {
  if (!isGitRepo(genomeDir)) {
    return null;
  }

  try {
    // 遍历 history 找到目标段版本对应的 commit
    const history = genomeData.history || [];
    const targetEntry = history.find(
      e => e.section === sectionName && e.section_version === targetVersion
    );
    
    if (!targetEntry || !targetEntry.git_commit) {
      return null;
    }

    const filePath = `sections/${sectionName}.md`;
    const content = execSync(
      `git show ${targetEntry.git_commit}:${filePath}`,
      { cwd: genomeDir, encoding: 'utf-8' }
    );
    
    return content;
  } catch (error: any) {
    // commit 不存在或文件在该 commit 不存在
    return null;
  }
}

/**
 * 计算规则 ID 增删（对比旧内容）
 */
export function computeRuleIdChanges(
  oldContent: string,
  newContent: string
): { added: string[], removed: string[] } {
  const pattern = /\b(R-\d{3})\b/g;
  
  const oldIds = new Set([...oldContent.matchAll(pattern)].map(m => m[1]));
  const newIds = new Set([...newContent.matchAll(pattern)].map(m => m[1]));
  
  const added = [...newIds].filter(id => !oldIds.has(id));
  const removed = [...oldIds].filter(id => !newIds.has(id));
  
  return { added, removed };
}

/**
 * 限制 history 数组长度（保留最近 N 条）
 */
export function trimHistory(history: HistoryEntry[], maxEntries: number = 50): HistoryEntry[] {
  if (history.length <= maxEntries) {
    return history;
  }
  return history.slice(-maxEntries);  // 保留最后 N 条
}
