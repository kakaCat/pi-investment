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
