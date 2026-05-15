/**
 * Query Experience Tool - 经验库查询工具
 *
 * 让 Agent 在决策时查询历史经验，获取类似场景的成功/失败案例
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import type { Experience, ExperienceBase } from '../../types/evolution.js';

/**
 * 计算文本相似度（简单的关键词匹配）
 */
function calculateSimilarity(text1: string, text2: string): number {
  const words1 = text1.toLowerCase().split(/\s+/);
  const words2 = text2.toLowerCase().split(/\s+/);

  const set1 = new Set(words1);
  const set2 = new Set(words2);

  const intersection = new Set([...set1].filter(x => set2.has(x)));
  const union = new Set([...set1, ...set2]);

  return intersection.size / union.size; // Jaccard 相似度
}

/**
 * 匹配条件
 */
function matchConditions(
  expConditions: string[],
  queryConditions: string[]
): boolean {
  if (queryConditions.length === 0) return true;

  // 至少匹配一个条件
  return queryConditions.some(qc =>
    expConditions.some(ec =>
      ec.toLowerCase().includes(qc.toLowerCase()) ||
      qc.toLowerCase().includes(ec.toLowerCase())
    )
  );
}

/**
 * 查询经验库
 */
export function queryExperience(params: {
  scenario: string;
  symbol?: string;
  conditions?: string[];
  minConfidence?: number;
}): Experience[] {
  const piDir = join(process.cwd(), '.pi-invest');
  const experienceFile = join(piDir, 'experience', 'experience-base.json');

  // 加载经验库
  if (!existsSync(experienceFile)) {
    console.log('[经验查询] 经验库文件不存在');
    return [];
  }

  let experienceBase: ExperienceBase;
  try {
    experienceBase = JSON.parse(readFileSync(experienceFile, 'utf-8'));
  } catch (e) {
    console.error('[经验查询] 加载经验库失败:', e);
    return [];
  }

  const { scenario, symbol, conditions = [], minConfidence = 0.5 } = params;

  // 1. 文本相似度匹配
  const textMatches = experienceBase.experiences
    .map(exp => ({
      experience: exp,
      similarity: calculateSimilarity(exp.scenario, scenario)
    }))
    .filter(item => item.similarity > 0.3); // 相似度阈值

  // 2. 条件匹配
  let filtered = textMatches;
  if (conditions.length > 0) {
    filtered = textMatches.filter(item =>
      matchConditions(item.experience.pattern.conditions, conditions)
    );
  }

  // 3. 置信度过滤
  filtered = filtered.filter(item => item.experience.confidence >= minConfidence);

  // 4. 股票代码过滤（如果指定）
  if (symbol) {
    filtered = filtered.filter(item =>
      item.experience.examples.some(ex => ex.symbol === symbol)
    );
  }

  // 5. 按相似度和置信度综合排序
  filtered.sort((a, b) => {
    const scoreA = a.similarity * 0.4 + a.experience.confidence * 0.6;
    const scoreB = b.similarity * 0.4 + b.experience.confidence * 0.6;
    return scoreB - scoreA;
  });

  const results = filtered.map(item => item.experience);

  console.log(`[经验查询] 场景: "${scenario}", 找到 ${results.length} 条相关经验`);

  return results;
}

/**
 * 格式化经验为可读文本
 */
export function formatExperience(experience: Experience): string {
  const lines: string[] = [];

  lines.push(`场景: ${experience.scenario}`);
  lines.push(`建议: ${experience.recommendation}`);
  lines.push(`原因: ${experience.reason}`);
  lines.push(`置信度: ${(experience.confidence * 100).toFixed(0)}%`);
  lines.push(`历史数据:`);
  lines.push(`  - 总案例: ${experience.outcomes.total_cases} 次`);
  lines.push(`  - 胜率: ${(experience.outcomes.win_rate * 100).toFixed(0)}%`);
  lines.push(`  - 平均收益: ${(experience.outcomes.avg_return * 100).toFixed(1)}%`);

  if (experience.outcomes.max_gain) {
    lines.push(`  - 最大盈利: ${(experience.outcomes.max_gain * 100).toFixed(1)}%`);
  }
  if (experience.outcomes.max_loss) {
    lines.push(`  - 最大亏损: ${(experience.outcomes.max_loss * 100).toFixed(1)}%`);
  }

  if (experience.examples.length > 0) {
    lines.push(`示例案例:`);
    for (const ex of experience.examples.slice(0, 3)) {
      lines.push(`  - ${ex.date} ${ex.symbol}: ${(ex.result * 100).toFixed(1)}%`);
    }
  }

  return lines.join('\n');
}

/**
 * 查询并格式化经验（供 Agent 调用）
 */
export function queryAndFormatExperience(params: {
  scenario: string;
  symbol?: string;
  conditions?: string[];
  limit?: number;
}): string {
  const { limit = 5, ...queryParams } = params;

  const experiences = queryExperience(queryParams);

  if (experiences.length === 0) {
    return '未找到相关历史经验。';
  }

  const topExperiences = experiences.slice(0, limit);

  const lines: string[] = [];
  lines.push(`找到 ${experiences.length} 条相关经验，展示前 ${topExperiences.length} 条:\n`);

  for (let i = 0; i < topExperiences.length; i++) {
    lines.push(`\n━━━ 经验 ${i + 1} ━━━`);
    lines.push(formatExperience(topExperiences[i]));
  }

  return lines.join('\n');
}
