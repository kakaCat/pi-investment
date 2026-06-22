/**
 * Data Validators - 数据验证器
 *
 * 验证经验库和数据采集的数据完整性
 */

import type { Experience, ExperienceBase } from '../../types/evolution.js';
import type { Holding, Trade } from './data-collector.js';

// ============ 验证错误 ============

export class ValidationError extends Error {
  constructor(
    message: string,
    public field?: string,
    public value?: any
  ) {
    super(message);
    this.name = 'ValidationError';
  }
}

// ============ Experience 验证 ============

/**
 * 验证经验对象
 */
export function validateExperience(exp: any): exp is Experience {
  const errors: string[] = [];

  // 必填字段
  if (!exp.id || typeof exp.id !== 'string') {
    errors.push('id is required and must be a string');
  }

  if (!exp.scenario || typeof exp.scenario !== 'string') {
    errors.push('scenario is required and must be a string');
  }

  // pattern 验证
  if (!exp.pattern || typeof exp.pattern !== 'object') {
    errors.push('pattern is required and must be an object');
  } else {
    if (!Array.isArray(exp.pattern.conditions)) {
      errors.push('pattern.conditions must be an array');
    }
    if (!['buy', 'sell', 'hold'].includes(exp.pattern.action)) {
      errors.push('pattern.action must be one of: buy, sell, hold');
    }
  }

  // outcomes 验证
  if (!exp.outcomes || typeof exp.outcomes !== 'object') {
    errors.push('outcomes is required and must be an object');
  } else {
    if (typeof exp.outcomes.total_cases !== 'number' || exp.outcomes.total_cases < 0) {
      errors.push('outcomes.total_cases must be a non-negative number');
    }
    if (typeof exp.outcomes.win_rate !== 'number' || exp.outcomes.win_rate < 0 || exp.outcomes.win_rate > 100) {
      errors.push('outcomes.win_rate must be a number between 0 and 100');
    }
    if (typeof exp.outcomes.avg_return !== 'number') {
      errors.push('outcomes.avg_return must be a number');
    }
  }

  // recommendation 验证
  if (!['aggressive', 'moderate', 'cautious', 'avoid'].includes(exp.recommendation)) {
    errors.push('recommendation must be one of: aggressive, moderate, cautious, avoid');
  }

  // reason 验证
  if (!exp.reason || typeof exp.reason !== 'string') {
    errors.push('reason is required and must be a string');
  }

  // examples 验证
  if (!Array.isArray(exp.examples)) {
    errors.push('examples must be an array');
  }

  // confidence 验证
  if (typeof exp.confidence !== 'number' || exp.confidence < 0 || exp.confidence > 1) {
    errors.push('confidence must be a number between 0 and 1');
  }

  // last_updated 验证
  if (!exp.last_updated || typeof exp.last_updated !== 'string') {
    errors.push('last_updated is required and must be a string');
  }

  if (errors.length > 0) {
    throw new ValidationError(`Experience validation failed: ${errors.join('; ')}`);
  }

  return true;
}

/**
 * 验证经验库
 */
export function validateExperienceBase(base: any): base is ExperienceBase {
  const errors: string[] = [];

  if (!base.version || typeof base.version !== 'string') {
    errors.push('version is required and must be a string');
  }

  if (!base.last_updated || typeof base.last_updated !== 'string') {
    errors.push('last_updated is required and must be a string');
  }

  if (!Array.isArray(base.experiences)) {
    errors.push('experiences must be an array');
  } else {
    // 验证每个经验
    for (let i = 0; i < base.experiences.length; i++) {
      try {
        validateExperience(base.experiences[i]);
      } catch (error) {
        if (error instanceof ValidationError) {
          errors.push(`experiences[${i}]: ${error.message}`);
        }
      }
    }
  }

  if (errors.length > 0) {
    throw new ValidationError(`ExperienceBase validation failed: ${errors.join('; ')}`);
  }

  return true;
}

// ============ Portfolio 验证 ============

/**
 * 验证持仓对象
 */
export function validateHolding(holding: any): holding is Holding {
  const errors: string[] = [];

  if (!holding.symbol || typeof holding.symbol !== 'string') {
    errors.push('symbol is required and must be a string');
  }

  if (!holding.name || typeof holding.name !== 'string') {
    errors.push('name is required and must be a string');
  }

  if (typeof holding.quantity !== 'number' || holding.quantity <= 0) {
    errors.push('quantity must be a positive number');
  }

  if (typeof holding.avg_cost !== 'number' || holding.avg_cost <= 0) {
    errors.push('avg_cost must be a positive number');
  }

  if (!['A', 'HK', 'US'].includes(holding.market)) {
    errors.push('market must be one of: A, HK, US');
  }

  if (typeof holding.notes !== 'string') {
    errors.push('notes must be a string');
  }

  if (!holding.added_date || typeof holding.added_date !== 'string') {
    errors.push('added_date is required and must be a string');
  }

  if (typeof holding.original_cost !== 'number' || holding.original_cost <= 0) {
    errors.push('original_cost must be a positive number');
  }

  if (typeof holding.total_invested !== 'number' || holding.total_invested <= 0) {
    errors.push('total_invested must be a positive number');
  }

  if (errors.length > 0) {
    throw new ValidationError(`Holding validation failed: ${errors.join('; ')}`, 'holding', holding.symbol);
  }

  return true;
}

// ============ Trade 验证 ============

/**
 * 验证交易对象
 */
export function validateTrade(trade: any): trade is Trade {
  const errors: string[] = [];

  if (!trade.date || typeof trade.date !== 'string') {
    errors.push('date is required and must be a string');
  }

  if (!['buy', 'sell'].includes(trade.action)) {
    errors.push('action must be one of: buy, sell');
  }

  if (!trade.symbol || typeof trade.symbol !== 'string') {
    errors.push('symbol is required and must be a string');
  }

  if (!trade.name || typeof trade.name !== 'string') {
    errors.push('name is required and must be a string');
  }

  if (typeof trade.quantity !== 'number' || trade.quantity <= 0) {
    errors.push('quantity must be a positive number');
  }

  if (typeof trade.price !== 'number' || trade.price <= 0) {
    errors.push('price must be a positive number');
  }

  if (typeof trade.amount !== 'number' || trade.amount <= 0) {
    errors.push('amount must be a positive number');
  }

  if (!['A', 'HK', 'US'].includes(trade.market)) {
    errors.push('market must be one of: A, HK, US');
  }

  if (typeof trade.notes !== 'string') {
    errors.push('notes must be a string');
  }

  if (!trade.time || typeof trade.time !== 'string') {
    errors.push('time is required and must be a string');
  }

  if (errors.length > 0) {
    throw new ValidationError(`Trade validation failed: ${errors.join('; ')}`, 'trade', trade.symbol);
  }

  return true;
}

// ============ 数据完整性检查 ============

/**
 * 检查经验库数据完整性
 */
export interface IntegrityCheckResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  stats: {
    total_experiences: number;
    duplicate_ids: string[];
    low_confidence: string[];
    outdated: string[];
  };
}

export function checkExperienceBaseIntegrity(base: ExperienceBase): IntegrityCheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const duplicate_ids: string[] = [];
  const low_confidence: string[] = [];
  const outdated: string[] = [];

  // 检查重复 ID
  const idSet = new Set<string>();
  for (const exp of base.experiences) {
    if (idSet.has(exp.id)) {
      duplicate_ids.push(exp.id);
      errors.push(`Duplicate experience ID: ${exp.id}`);
    }
    idSet.add(exp.id);
  }

  // 检查低置信度经验
  for (const exp of base.experiences) {
    if (exp.confidence < 0.3) {
      low_confidence.push(exp.id);
      warnings.push(`Low confidence experience: ${exp.id} (${exp.confidence})`);
    }
  }

  // 检查过期经验（超过1年未更新）
  const oneYearAgo = new Date();
  oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
  const oneYearAgoStr = oneYearAgo.toISOString().split('T')[0];

  for (const exp of base.experiences) {
    if (exp.last_updated < oneYearAgoStr) {
      outdated.push(exp.id);
      warnings.push(`Outdated experience: ${exp.id} (last updated: ${exp.last_updated})`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    stats: {
      total_experiences: base.experiences.length,
      duplicate_ids,
      low_confidence,
      outdated,
    },
  };
}

/**
 * 修复经验库数据
 */
export function repairExperienceBase(base: ExperienceBase): ExperienceBase {
  const repaired: ExperienceBase = {
    ...base,
    experiences: [],
  };

  const idSet = new Set<string>();

  for (const exp of base.experiences) {
    // 跳过重复 ID
    if (idSet.has(exp.id)) {
      continue;
    }
    idSet.add(exp.id);

    // 修复数据
    const repairedExp: Experience = {
      ...exp,
      confidence: Math.max(0, Math.min(1, exp.confidence)), // 限制在 [0, 1]
      outcomes: {
        ...exp.outcomes,
        win_rate: Math.max(0, Math.min(100, exp.outcomes.win_rate)), // 限制在 [0, 100]
        total_cases: Math.max(0, exp.outcomes.total_cases), // 非负
      },
    };

    repaired.experiences.push(repairedExp);
  }

  return repaired;
}
