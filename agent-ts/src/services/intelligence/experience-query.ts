/**
 * Query Experience Tool - 经验库查询工具
 *
 * 让 Agent 在决策时查询历史经验，获取类似场景的成功/失败案例
 *
 * ═══════════════════════════════════════════════════════════════════════════════
 * 匹配算法诊断（2026-05-28）
 * ═══════════════════════════════════════════════════════════════════════════════
 *
 * 当前算法：字符集 Jaccard 相似度 + 简单 includes 条件匹配
 *
 * 已知缺陷：
 * 1. 【高危】中文字符级 Jaccard 无法区分语义：
 *    "RSI超卖反弹" vs "RSI超买" → 共享 "RSI超" → 相似度 0.75
 *    但"超卖"和"超买"意义完全相反！
 *
 * 2. 【高危】8 条经验库过于稀疏 — 相似度阈值 0.3 时，随机噪声掩盖真实信号。
 *    大多数查询只能匹配到 0-2 条结果，无法形成统计显著性。
 *
 * 3. 【中危】无法识别同义表达：
 *    "MACD金叉" vs "均线交叉上穿" → 零字符共享 → 相似度 0
 *
 * 4. 【中危】常见中文字符（的、了、是、在）稀释有效匹配信号
 *
 * 5. 【低危】技术术语无权重：
 *    MACD、RSI、PE、ROE、金叉、死叉 应比普通字符权重高 3x+
 *
 * 6. 【低危】条件匹配是纯 includes — "RSI>70" 匹配不到 "RSI(14) > 75"
 *
 * ───────────────────────────────────────────────────────────────────────────────
 * 优化路线图（按优先级）
 * ───────────────────────────────────────────────────────────────────────────────
 *
 * Phase 1 — 立即改善（不改架构，只调参数）：
 *   - 提高相似度阈值：0.3 → 0.5
 *   - 加入常见中文字符黑名单：的/了/是/在/和/与/或/等/其/且
 *   - 触发词权重：技术术语（MACD/RSI/KDJ/PE/ROE/金叉/死叉/突破/跌破）x3
 *
 * Phase 2 — 中等改动（换匹配算法）：
 *   - 用 bigram TF-IDF 替换字符集 Jaccard
 *   （中文 bigram 天然携带短语信息，"超卖""反弹""金叉"都作为独立单元）
 *   - 实现成本低（纯 JS，无外部依赖），但匹配精度提升显著
 *
 * Phase 3 — 大改（引入语义模型）：
 *   - sentence-transformers 做语义 embedding → 余弦相似度
 *   - 需要 Python 后端支持 + 模型加载
 *   - 仅在经验库 > 100 条 + 高频查询时值得投入
 *
 * Phase 4 — 经验库自动化填充：
 *   - 每次 agent 做交易决策 → 自动生成经验记录
 *   - evolution_run 完成后 → 提取高置信度模式写入经验库
 *   - 目标：经验库从 8 条增长到 100+ 条
 * ═══════════════════════════════════════════════════════════════════════════════
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import type { Experience, ExperienceBase } from '../../types/evolution.js';

/**
 * 计算文本相似度（支持中文）
 */
function calculateSimilarity(text1: string, text2: string): number {
  if (!text1 || !text2) return 0;

  // 转换为小写
  const t1 = text1.toLowerCase();
  const t2 = text2.toLowerCase();

  // 简单的包含匹配（适合中文短语）
  if (t1.includes(t2) || t2.includes(t1)) {
    return 0.8;
  }

  // 字符级别的相似度（适合中文）
  const chars1 = Array.from(t1);
  const chars2 = Array.from(t2);

  const set1 = new Set(chars1);
  const set2 = new Set(chars2);

  const intersection = new Set([...set1].filter(x => set2.has(x)));
  const union = new Set([...set1, ...set2]);

  return intersection.size / union.size;
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
  scenario?: string;
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
  lines.push(`  - 胜率: ${experience.outcomes.win_rate.toFixed(1)}%`);
  lines.push(`  - 平均收益: ${experience.outcomes.avg_return.toFixed(2)}%`);

  if (experience.outcomes.max_gain) {
    lines.push(`  - 最大盈利: ${experience.outcomes.max_gain.toFixed(2)}%`);
  }
  if (experience.outcomes.max_loss) {
    lines.push(`  - 最大亏损: ${experience.outcomes.max_loss.toFixed(2)}%`);
  }

  if (experience.examples.length > 0) {
    lines.push(`示例案例:`);
    for (const ex of experience.examples.slice(0, 3)) {
      lines.push(`  - ${ex.date} ${ex.symbol}: ${ex.result.toFixed(2)}%`);
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
