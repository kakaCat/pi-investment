/**
 * Experience Manager - 经验库管理器
 *
 * 管理历史经验的存储、加载和查询
 * 支持版本管理、增量更新、自动备份
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, copyFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import type { ExperienceBase, Experience } from '../../types/evolution.js';

const DEFAULT_BASE_DIR = join(process.cwd(), '.pi-invest');
const MAX_BACKUPS = 10;

// ─── 新陈代谢机制常量 ──────────────────────────────────────────────────────
const DEFAULT_WEIGHT = 1.0;
const DEFAULT_HALF_LIFE_DAYS = 30;
const CONFIRM_WEIGHT_DELTA = 0.1;
const REFUTE_WEIGHT_DELTA = 0.2;
const DEPRECATE_FAILURE_THRESHOLD = 3;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * 获取经验库目录路径
 */
function getExperienceDir(baseDir: string = DEFAULT_BASE_DIR): string {
  return join(baseDir, 'experience');
}

/**
 * 获取经验库文件路径
 */
function getExperienceFilePath(baseDir: string = DEFAULT_BASE_DIR): string {
  return join(getExperienceDir(baseDir), 'experiences.json');
}

/**
 * 获取索引文件路径
 */
function getIndexFilePath(baseDir: string = DEFAULT_BASE_DIR): string {
  return join(getExperienceDir(baseDir), 'index.json');
}

/**
 * 获取备份目录路径
 */
function getBackupDir(baseDir: string = DEFAULT_BASE_DIR): string {
  return join(getExperienceDir(baseDir), 'backups');
}

/**
 * 加载经验库
 */
export function loadExperienceBase(baseDir: string = DEFAULT_BASE_DIR): ExperienceBase {
  const filePath = getExperienceFilePath(baseDir);

  if (!existsSync(filePath)) {
    return {
      version: '1.0.0',
      last_updated: new Date().toISOString().split('T')[0],
      experiences: []
    };
  }

  try {
    const content = readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);

    // 数据验证
    if (!data.version || !data.experiences || !Array.isArray(data.experiences)) {
      throw new Error('Invalid experience base format');
    }

    return data;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(`Failed to parse experiences.json: ${error.message}`);
    }
    throw error;
  }
}

/**
 * 创建备份
 */
function createBackup(baseDir: string = DEFAULT_BASE_DIR): void {
  const filePath = getExperienceFilePath(baseDir);
  const backupDir = getBackupDir(baseDir);

  if (!existsSync(filePath)) {
    return;
  }

  // 确保备份目录存在
  if (!existsSync(backupDir)) {
    mkdirSync(backupDir, { recursive: true });
  }

  // 创建带时间戳的备份
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T').join('_').slice(0, -5);
  const backupPath = join(backupDir, `experiences_${timestamp}.json`);
  copyFileSync(filePath, backupPath);

  // 清理旧备份，只保留最近 MAX_BACKUPS 个
  cleanupOldBackups(backupDir);
}

/**
 * 清理旧备份
 */
function cleanupOldBackups(backupDir: string): void {
  if (!existsSync(backupDir)) {
    return;
  }

  const backups = readdirSync(backupDir)
    .filter(f => f.startsWith('experiences_') && f.endsWith('.json'))
    .sort()
    .reverse();

  // 删除超出限制的备份
  for (let i = MAX_BACKUPS; i < backups.length; i++) {
    const oldBackup = join(backupDir, backups[i]);
    try {
      unlinkSync(oldBackup);
    } catch (error) {
      // 忽略删除失败
    }
  }
}

/**
 * 增加版本号
 */
function incrementVersion(version: string): string {
  const parts = version.split('.');
  const patch = parseInt(parts[2] || '0') + 1;
  return `${parts[0]}.${parts[1]}.${patch}`;
}

/**
 * 保存经验库（带版本管理和备份）
 */
export function saveExperienceBase(
  base: ExperienceBase,
  baseDir: string = DEFAULT_BASE_DIR,
  options: { backup?: boolean; incrementVersion?: boolean } = {}
): void {
  const { backup = true, incrementVersion: shouldIncrementVersion = true } = options;

  const filePath = getExperienceFilePath(baseDir);
  const dir = getExperienceDir(baseDir);

  // 确保目录存在
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }

  // 创建备份
  if (backup && existsSync(filePath)) {
    createBackup(baseDir);
  }

  // 更新元数据
  base.last_updated = new Date().toISOString().split('T')[0];
  if (shouldIncrementVersion) {
    base.version = incrementVersion(base.version);
  }

  // 保存主文件
  writeFileSync(filePath, JSON.stringify(base, null, 2));

  // 更新索引
  updateIndex(base, baseDir);
}

/**
 * 更新索引文件
 */
interface ExperienceIndex {
  total: number;
  by_scenario: Record<string, number>;
  by_action: Record<string, number>;
  last_updated: string;
}

function updateIndex(base: ExperienceBase, baseDir: string = DEFAULT_BASE_DIR): void {
  const indexPath = getIndexFilePath(baseDir);

  const index: ExperienceIndex = {
    total: base.experiences.length,
    by_scenario: {},
    by_action: {},
    last_updated: base.last_updated,
  };

  // 统计场景和动作
  for (const exp of base.experiences) {
    // 按场景统计
    const scenario = exp.scenario.split(/[，。；]/)[0]; // 取第一句作为场景分类
    index.by_scenario[scenario] = (index.by_scenario[scenario] || 0) + 1;

    // 按动作统计
    const action = exp.pattern.action;
    index.by_action[action] = (index.by_action[action] || 0) + 1;
  }

  writeFileSync(indexPath, JSON.stringify(index, null, 2));
}

/**
 * 添加经验（增量更新）
 */
export function addExperience(
  experience: Experience,
  baseDir: string = DEFAULT_BASE_DIR
): void {
  const base = loadExperienceBase(baseDir);

  // 检查是否已存在
  const existingIndex = base.experiences.findIndex(e => e.id === experience.id);

  if (existingIndex >= 0) {
    // 更新现有经验
    base.experiences[existingIndex] = experience;
  } else {
    // 添加新经验
    base.experiences.push(experience);
  }

  saveExperienceBase(base, baseDir);
}

/**
 * 批量添加经验（增量更新）
 */
export function addExperiences(
  experiences: Experience[],
  baseDir: string = DEFAULT_BASE_DIR
): { added: number; updated: number } {
  const base = loadExperienceBase(baseDir);
  let added = 0;
  let updated = 0;

  for (const experience of experiences) {
    const existingIndex = base.experiences.findIndex(e => e.id === experience.id);

    if (existingIndex >= 0) {
      base.experiences[existingIndex] = experience;
      updated++;
    } else {
      base.experiences.push(experience);
      added++;
    }
  }

  saveExperienceBase(base, baseDir);

  return { added, updated };
}

/**
 * 删除经验
 */
export function removeExperience(
  experienceId: string,
  baseDir: string = DEFAULT_BASE_DIR
): boolean {
  const base = loadExperienceBase(baseDir);
  const initialLength = base.experiences.length;

  base.experiences = base.experiences.filter(e => e.id !== experienceId);

  if (base.experiences.length < initialLength) {
    saveExperienceBase(base, baseDir);
    return true;
  }

  return false;
}

/**
 * 合并经验（去重和冲突解决）
 */
export function mergeExperiences(
  newExperiences: Experience[],
  baseDir: string = DEFAULT_BASE_DIR,
  strategy: 'keep_existing' | 'keep_new' | 'merge_outcomes' = 'merge_outcomes'
): { merged: number; skipped: number; conflicts: number } {
  const base = loadExperienceBase(baseDir);
  let merged = 0;
  let skipped = 0;
  let conflicts = 0;

  for (const newExp of newExperiences) {
    const existingIndex = base.experiences.findIndex(e => e.id === newExp.id);

    if (existingIndex === -1) {
      // 新经验，直接添加
      base.experiences.push(newExp);
      merged++;
    } else {
      // 冲突处理
      conflicts++;
      const existing = base.experiences[existingIndex];

      if (strategy === 'keep_existing') {
        skipped++;
      } else if (strategy === 'keep_new') {
        base.experiences[existingIndex] = newExp;
        merged++;
      } else if (strategy === 'merge_outcomes') {
        // 合并结果数据
        const mergedExp = { ...existing };
        mergedExp.outcomes.total_cases += newExp.outcomes.total_cases;

        // 重新计算加权平均
        const totalCases = mergedExp.outcomes.total_cases;
        const existingWeight = existing.outcomes.total_cases / totalCases;
        const newWeight = newExp.outcomes.total_cases / totalCases;

        mergedExp.outcomes.win_rate =
          existing.outcomes.win_rate * existingWeight +
          newExp.outcomes.win_rate * newWeight;

        mergedExp.outcomes.avg_return =
          existing.outcomes.avg_return * existingWeight +
          newExp.outcomes.avg_return * newWeight;

        // 更新最大值
        if (newExp.outcomes.max_gain && (!mergedExp.outcomes.max_gain || newExp.outcomes.max_gain > mergedExp.outcomes.max_gain)) {
          mergedExp.outcomes.max_gain = newExp.outcomes.max_gain;
        }
        if (newExp.outcomes.max_loss && (!mergedExp.outcomes.max_loss || newExp.outcomes.max_loss < mergedExp.outcomes.max_loss)) {
          mergedExp.outcomes.max_loss = newExp.outcomes.max_loss;
        }

        // 合并示例
        mergedExp.examples = [...existing.examples, ...newExp.examples]
          .sort((a, b) => b.date.localeCompare(a.date))
          .slice(0, 10); // 只保留最近10个

        mergedExp.last_updated = newExp.last_updated;

        base.experiences[existingIndex] = mergedExp;
        merged++;
      }
    }
  }

  saveExperienceBase(base, baseDir);

  return { merged, skipped, conflicts };
}

interface QueryParams {
  scenario?: string;
  symbol?: string;
  conditions?: string[];
  /** 是否包含已弃用（deprecated）的经验，默认 false */
  include_deprecated?: boolean;
}

// ─── 新陈代谢机制 ──────────────────────────────────────────────────────────
//
// 经验只进不出会变成偏见仓库。新陈代谢机制：
// 1. 时间衰减：effective_weight = weight * 0.5^(距最近验证或创建天数 / half_life_days)
// 2. 验证反馈：confirmed → weight +0.1（封顶 1），refuted → weight -0.2（封底 0）
// 3. 自动弃用：连续 3 次验证失败 → deprecated = true，查询默认过滤

/**
 * 归一化经验条目：为旧格式条目（缺省新字段）填充默认值
 * 返回新对象，不修改入参
 */
export function normalizeExperience(exp: Experience): Experience {
  return {
    ...exp,
    weight: exp.weight ?? DEFAULT_WEIGHT,
    last_verified_at: exp.last_verified_at ?? null,
    consecutive_failures: exp.consecutive_failures ?? 0,
    half_life_days: exp.half_life_days ?? DEFAULT_HALF_LIFE_DAYS,
    deprecated: exp.deprecated ?? false,
  };
}

/**
 * 计算有效权重（时间衰减）
 *
 * effective_weight = weight * 0.5^(days_since_last_verified_or_created / half_life_days)
 *
 * 衰减基准时间：last_verified_at 优先，从未验证的旧条目回退到 last_updated（创建/更新时间的代理）
 */
export function computeEffectiveWeight(exp: Experience, now: Date = new Date()): number {
  const normalized = normalizeExperience(exp);
  const baseTimeStr = normalized.last_verified_at ?? normalized.last_updated;
  const baseTime = new Date(baseTimeStr).getTime();

  if (isNaN(baseTime)) {
    return normalized.weight!;
  }

  const daysSince = Math.max(0, (now.getTime() - baseTime) / MS_PER_DAY);
  const decay = Math.pow(0.5, daysSince / normalized.half_life_days!);
  return normalized.weight! * decay;
}

/**
 * 验证经验（证实/打脸反馈）
 *
 * - confirmed：consecutive_failures 归零，weight = min(1, weight + 0.1)，last_verified_at 更新
 * - refuted：consecutive_failures +1，weight = max(0, weight - 0.2)，last_verified_at 更新
 * - consecutive_failures >= 3 时标记 deprecated = true（查询默认过滤）
 * - confirmed 后 failures 归零，deprecated 自动解除（经验被"复活"）
 *
 * @returns 更新后的经验条目；id 不存在时返回 null
 */
export function verifyExperience(
  id: string,
  outcome: 'confirmed' | 'refuted',
  baseDir: string = DEFAULT_BASE_DIR
): Experience | null {
  const base = loadExperienceBase(baseDir);
  const index = base.experiences.findIndex(e => e.id === id);

  if (index === -1) {
    return null;
  }

  const exp = normalizeExperience(base.experiences[index]);
  const now = new Date().toISOString();

  if (outcome === 'confirmed') {
    exp.consecutive_failures = 0;
    exp.weight = Math.min(1, exp.weight! + CONFIRM_WEIGHT_DELTA);
  } else {
    exp.consecutive_failures = exp.consecutive_failures! + 1;
    exp.weight = Math.max(0, exp.weight! - REFUTE_WEIGHT_DELTA);
  }

  exp.last_verified_at = now;
  exp.deprecated = exp.consecutive_failures! >= DEPRECATE_FAILURE_THRESHOLD;

  base.experiences[index] = exp;
  saveExperienceBase(base, baseDir);

  return exp;
}

/**
 * 计算文本相似度（简单实现）
 */
function similarity(text1: string, text2: string): number {
  const lower1 = text1.toLowerCase();
  const lower2 = text2.toLowerCase();

  // 如果一个字符串包含另一个，返回高相似度
  if (lower1.includes(lower2) || lower2.includes(lower1)) {
    return 1.0;
  }

  const words1 = lower1.split('');
  const words2 = lower2.split('');

  let matches = 0;
  for (const word of words1) {
    if (words2.includes(word)) {
      matches++;
    }
  }

  return matches / Math.max(words1.length, words2.length);
}

/**
 * 检查条件是否匹配
 */
function matchConditions(patternConditions: string[], queryConditions: string[]): boolean {
  for (const qc of queryConditions) {
    const found = patternConditions.some(pc =>
      pc.toLowerCase().includes(qc.toLowerCase()) ||
      qc.toLowerCase().includes(pc.toLowerCase())
    );
    if (found) return true;
  }
  return false;
}

/**
 * 查询经验
 *
 * 默认过滤 deprecated 条目（include_deprecated: true 时包含）。
 * 返回的条目经过归一化（旧格式自动补默认字段），并附带 effective_weight（时间衰减后的有效权重）。
 */
export function queryExperience(
  params: QueryParams,
  baseDir: string = DEFAULT_BASE_DIR
): Experience[] {
  const base = loadExperienceBase(baseDir);
  let results = base.experiences;

  // 0. 弃用过滤
  if (!params.include_deprecated) {
    results = results.filter(exp => exp.deprecated !== true);
  }

  // 1. 场景文本匹配
  if (params.scenario) {
    results = results.filter(exp =>
      similarity(exp.scenario, params.scenario!) > 0.3
    );
  }

  // 2. 条件匹配
  if (params.conditions && params.conditions.length > 0) {
    results = results.filter(exp =>
      matchConditions(exp.pattern.conditions, params.conditions!)
    );
  }

  // 3. 归一化 + 有效权重标注（不修改存储中的原始数据）
  const now = new Date();
  const annotated = results.map(exp => {
    const normalized = normalizeExperience(exp);
    normalized.effective_weight = computeEffectiveWeight(normalized, now);
    return normalized;
  });

  // 4. 按置信度排序
  return annotated.sort((a, b) => b.confidence - a.confidence);
}
