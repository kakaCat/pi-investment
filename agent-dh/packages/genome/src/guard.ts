/**
 * guard.ts - 基因组写入校验（宪法拒绝、花括号、规则ID、锁）
 * RFC 007 P0-2 安全不变量实施
 */
import * as fs from 'fs';
import * as path from 'path';

export interface ValidationError {
  code: string;
  message: string;
}

/**
 * 校验：拒绝修改宪法层
 */
export function guardConstitution(sectionName: string, genomeData: any): void {
  const meta = genomeData.sections[sectionName];
  if (!meta) {
    throw new Error(`Section not found: ${sectionName}`);
  }
  if (meta.class === 'constitution' || meta.locked === true) {
    throw new Error(
      `宪法层段 ${sectionName} 禁止修改。任何进化不得突破宪法约束。`
    );
  }
}

/**
 * 花括号安检：检查未知变量引用（A-4）
 */
export function validateBraces(content: string, sectionName: string): void {
  const pattern = /\{\{([^}]+)\}\}/g;
  const matches = [...content.matchAll(pattern)];
  
  if (matches.length > 0) {
    const knownVars = ['genome_version'];  // 已注册变量清单
    const unknownRefs = matches
      .map(m => m[1].trim())
      .filter(v => !knownVars.includes(v));
    
    if (unknownRefs.length > 0) {
      throw new Error(
        `段 ${sectionName} 含未注册变量 {{${unknownRefs[0]}}}，renderPrompt 会抛异常。` +
        `移除花括号或注册变量。已知变量: ${knownVars.join(', ')}`
      );
    }
  }
}

/**
 * 内容大小限制：防 token 膨胀
 */
export function validateSize(content: string, sectionName: string, maxChars: number = 8000): void {
  if (content.length > maxChars) {
    throw new Error(
      `段 ${sectionName} 内容超限：${content.length} > ${maxChars} 字符。` +
      `请精简内容或拆分段。`
    );
  }
}

/**
 * 规则 ID 提取（统一定义口径，2026-08-20 修复误判）：
 * 只有 markdown 标题行中的 R-\d{3} 算规则"定义"（如 `## R-001 买入前确认`）；
 * 正文中的提及（如"参考 R-001"）是合法引用，不算重复定义。
 */
export function extractRuleDefinitions(content: string): string[] {
  const defPattern = /^#{1,6}\s*(R-\d{3})\b/gm;
  return [...content.matchAll(defPattern)].map(m => m[1]);
}

/**
 * 规则 ID 格式校验：R-\d{3}
 * 计算规则 ID 增删清单（用于 changelog）
 */
export function validateAndExtractRuleIds(
  content: string, 
  sectionName: string
): { ids: string[], added: string[], removed: string[] } {
  if (sectionName !== 'rules') {
    return { ids: [], added: [], removed: [] };
  }

  // 只按定义行（标题）判重；正文引用不受限
  const definitions = extractRuleDefinitions(content);
  const ids = [...new Set(definitions)];
  const duplicates = ids.filter(id => definitions.filter(d => d === id).length > 1);
  if (duplicates.length > 0) {
    throw new Error(
      `规则段含重复定义：${duplicates.join(', ')}。每个规则 ID 只能有一个定义（标题行）；正文可引用但不可重复定义。`
    );
  }

  return { ids, added: [], removed: [] };  // added/removed 由 store 对比计算
}

/**
 * 乐观锁校验：版本号匹配
 */
export function validateVersion(
  expected: number | undefined,
  actual: number,
  sectionName: string
): void {
  if (expected !== undefined && expected !== actual) {
    throw new Error(
      `段 ${sectionName} 版本冲突：期望 v${expected}，实际 v${actual}。` +
      `可能有并发修改，请重新读取后再更新。`
    );
  }
}

/**
 * 文件锁：防并发写
 * stale 超过 5 分钟自动接管
 */
export class GenomeLock {
  private lockPath: string;
  private staleMs: number = 5 * 60 * 1000;  // 5 分钟

  constructor(genomeDir: string) {
    this.lockPath = path.join(genomeDir, 'genome.lock');
  }

  acquire(): void {
    if (fs.existsSync(this.lockPath)) {
      const lockStat = fs.statSync(this.lockPath);
      const age = Date.now() - lockStat.mtimeMs;
      if (age < this.staleMs) {
        throw new Error(
          `基因组写锁被占用（${Math.round(age / 1000)}s 前），请稍后重试。` +
          `若确认无其他进程在写，删除 ${this.lockPath} 后重试。`
        );
      }
      // stale lock，接管
      fs.unlinkSync(this.lockPath);
    }
    
    fs.writeFileSync(this.lockPath, JSON.stringify({
      pid: process.pid,
      acquired_at: new Date().toISOString(),
    }));
  }

  release(): void {
    if (fs.existsSync(this.lockPath)) {
      fs.unlinkSync(this.lockPath);
    }
  }
}

/**
 * 交易时段检查：默认拒改，force 通道留痕
 */
export function checkTradingHours(force: boolean = false): { warning?: string } {
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay();
  
  // 周末不算交易时段
  if (day === 0 || day === 6) {
    return {};
  }
  
  // A股交易时段：9:30-11:30, 13:00-15:00
  const inMorning = (hour === 9 && minute >= 30) || (hour === 10) || (hour === 11 && minute < 30);
  const inAfternoon = (hour === 13) || (hour === 14) || (hour === 15 && minute === 0);
  
  if (inMorning || inAfternoon) {
    if (!force) {
      throw new Error(
        `交易时段（${hour}:${minute.toString().padStart(2, '0')}）禁止修改基因组。` +
        `进化活动安排在盘后/周末。紧急修复传 force=true（会留痕问责）。`
      );
    }
    return {
      warning: `⚠️  force=true 在交易时段修改基因组（${hour}:${minute.toString().padStart(2, '0')}），已留痕 history`
    };
  }
  
  return {};
}
