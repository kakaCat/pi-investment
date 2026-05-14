/**
 * Experience Manager - 经验库管理器
 *
 * 管理历史经验的存储、加载和查询
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import type { ExperienceBase, Experience } from '../../types/evolution.js';

const DEFAULT_BASE_DIR = join(process.cwd(), '.pi-invest');

/**
 * 获取经验库文件路径
 */
function getExperienceFilePath(baseDir: string = DEFAULT_BASE_DIR): string {
  return join(baseDir, 'experience', 'experience-base.json');
}

/**
 * 加载经验库
 */
export function loadExperienceBase(baseDir: string = DEFAULT_BASE_DIR): ExperienceBase {
  const filePath = getExperienceFilePath(baseDir);

  if (!existsSync(filePath)) {
    return {
      version: '1.0',
      last_updated: new Date().toISOString().split('T')[0],
      experiences: []
    };
  }

  const content = readFileSync(filePath, 'utf-8');
  return JSON.parse(content);
}

/**
 * 保存经验库
 */
export function saveExperienceBase(
  base: ExperienceBase,
  baseDir: string = DEFAULT_BASE_DIR
): void {
  const filePath = getExperienceFilePath(baseDir);
  const dir = join(baseDir, 'experience');

  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }

  base.last_updated = new Date().toISOString().split('T')[0];
  writeFileSync(filePath, JSON.stringify(base, null, 2));
}

/**
 * 添加经验
 */
export function addExperience(
  experience: Experience,
  baseDir: string = DEFAULT_BASE_DIR
): void {
  const base = loadExperienceBase(baseDir);

  // 检查是否已存在
  const existingIndex = base.experiences.findIndex(e => e.id === experience.id);

  if (existingIndex >= 0) {
    base.experiences[existingIndex] = experience;
  } else {
    base.experiences.push(experience);
  }

  saveExperienceBase(base, baseDir);
}

interface QueryParams {
  scenario?: string;
  symbol?: string;
  conditions?: string[];
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
 */
export function queryExperience(
  params: QueryParams,
  baseDir: string = DEFAULT_BASE_DIR
): Experience[] {
  const base = loadExperienceBase(baseDir);
  let results = base.experiences;

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

  // 3. 按置信度排序
  return results.sort((a, b) => b.confidence - a.confidence);
}
