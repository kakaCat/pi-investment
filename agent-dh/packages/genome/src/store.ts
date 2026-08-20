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
  type: 'update' | 'rollback' | 'init' | 'promote';
  force?: boolean;
  /** RFC 008 验证门：candidate=观察版（模拟盘 A/B 中），active=正式版（默认） */
  stage?: 'candidate' | 'active';
  /** 该版本对比的基准基因组代数 */
  baseline_version?: string;
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
 * B-2 修复：git add -A 纳入 CHANGELOG.md；rollback 的 message 标注目标版本
 */
export function gitCommit(
  genomeDir: string,
  genomeVersion: string,
  sectionName: string,
  oldVersion: number,
  newVersion: number,
  reason: string,
  type: 'update' | 'rollback' | 'promote',
  rollbackTarget?: number
): string {
  if (!isGitRepo(genomeDir)) {
    throw new Error(`${genomeDir} is not a git repository. Run 'git init' first.`);
  }

  try {
    // git add 全部（sections/ + genome.json + CHANGELOG.md + .gitignore；genome.lock/*.tmp 已被 .gitignore 排除）
    execSync('git add -A', { cwd: genomeDir, stdio: 'pipe' });

    // 结构化 commit message
    const action = type === 'rollback' ? 'rollback' : type === 'promote' ? 'promote' : 'update';
    const versionChange = type === 'rollback'
      ? `rollback to v${rollbackTarget ?? newVersion}`
      : type === 'promote'
        ? `v${newVersion} candidate→active`
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
 * 用于 genome_rollback / genome_diff
 *
 * B-3 修复：优先按 history 条目的 git_commit 定位；若无条目（如 g1 初始版本
 * 没有 history 记录），回退到文件级 git 历史推导——段文件的第 N 次提交即 vN
 *（每次 init/update/rollback 恰好提交一次段文件）。
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

  const filePath = `sections/${sectionName}.md`;

  try {
    // 优先：遍历 history 找到目标段版本对应的 commit
    const history = genomeData.history || [];
    const targetEntry = history.find(
      e => e.section === sectionName && e.section_version === targetVersion
    );

    if (targetEntry?.git_commit) {
      try {
        return execSync(
          `git show ${targetEntry.git_commit}:${filePath}`,
          { cwd: genomeDir, encoding: 'utf-8' }
        );
      } catch { /* commit 或文件不存在则走兜底 */ }
    }

    // 兜底：段文件的第 N 次提交 = vN（按时间正序）
    const hashes = execSync(
      `git log --format=%h --reverse -- "${filePath}"`,
      { cwd: genomeDir, encoding: 'utf-8' }
    ).trim().split('\n').filter(Boolean);

    const hash = hashes[targetVersion - 1];
    if (!hash) return null;

    return execSync(
      `git show ${hash}:${filePath}`,
      { cwd: genomeDir, encoding: 'utf-8' }
    );
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
  // 2026-08-20 修复：只按定义行（标题）计算增删，正文引用不产生伪增删
  const defPattern = /^#{1,6}\s*(R-\d{3})\b/gm;
  const oldIds = new Set([...oldContent.matchAll(defPattern)].map(m => m[1]));
  const newIds = new Set([...newContent.matchAll(defPattern)].map(m => m[1]));
  
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
