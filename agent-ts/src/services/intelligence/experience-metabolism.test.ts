/**
 * Experience Metabolism Tests — 经验库新陈代谢机制
 *
 * 覆盖：
 * - 时间衰减（effective_weight = weight * 0.5^(days / half_life_days)）
 * - verifyExperience confirm / refute 路径
 * - 连续 3 次失败自动弃用（deprecated）
 * - 旧格式条目（无新字段）兼容
 * - 查询默认过滤 deprecated，include_deprecated 显式包含
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'fs';
import { join } from 'path';
import {
  loadExperienceBase,
  addExperience,
  queryExperience,
  verifyExperience,
  computeEffectiveWeight,
  normalizeExperience,
} from './experience-manager.js';
import type { Experience, ExperienceBase } from '../../types/evolution.js';

const TEST_DIR = join(process.cwd(), '.test-experience-metabolism');

function createTestExperience(id: string, overrides: Partial<Experience> = {}): Experience {
  return {
    id,
    scenario: '测试场景',
    pattern: {
      conditions: ['条件1', '条件2'],
      action: 'buy',
    },
    outcomes: {
      total_cases: 10,
      win_rate: 60,
      avg_return: 5.5,
    },
    recommendation: 'moderate',
    reason: '测试原因',
    examples: [],
    confidence: 0.7,
    last_updated: '2026-07-01',
    ...overrides,
  };
}

function daysAgoIso(days: number, from: Date = new Date()): string {
  const d = new Date(from.getTime() - days * 24 * 60 * 60 * 1000);
  return d.toISOString();
}

describe('Experience Metabolism', () => {
  beforeEach(() => {
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
  });

  // ─── normalizeExperience：旧格式兼容 ────────────────────────────────────

  describe('normalizeExperience (legacy compat)', () => {
    it('should fill default metabolism fields for legacy entries', () => {
      const legacy = createTestExperience('exp-legacy');
      const normalized = normalizeExperience(legacy);

      expect(normalized.weight).toBe(1.0);
      expect(normalized.last_verified_at).toBeNull();
      expect(normalized.consecutive_failures).toBe(0);
      expect(normalized.half_life_days).toBe(30);
      expect(normalized.deprecated).toBe(false);
    });

    it('should not overwrite existing metabolism fields', () => {
      const exp = createTestExperience('exp-new', {
        weight: 0.6,
        last_verified_at: '2026-07-20T00:00:00.000Z',
        consecutive_failures: 2,
        half_life_days: 15,
        deprecated: false,
      });
      const normalized = normalizeExperience(exp);

      expect(normalized.weight).toBe(0.6);
      expect(normalized.last_verified_at).toBe('2026-07-20T00:00:00.000Z');
      expect(normalized.consecutive_failures).toBe(2);
      expect(normalized.half_life_days).toBe(15);
    });
  });

  // ─── 时间衰减 ────────────────────────────────────────────────────────────

  describe('computeEffectiveWeight (time decay)', () => {
    const NOW = new Date('2026-07-29T00:00:00.000Z');

    it('should return full weight when verified just now', () => {
      const exp = createTestExperience('exp-1', {
        weight: 1.0,
        last_verified_at: NOW.toISOString(),
      });
      expect(computeEffectiveWeight(exp, NOW)).toBeCloseTo(1.0, 5);
    });

    it('should halve weight after one half-life', () => {
      const exp = createTestExperience('exp-1', {
        weight: 1.0,
        last_verified_at: daysAgoIso(30, NOW),
        half_life_days: 30,
      });
      expect(computeEffectiveWeight(exp, NOW)).toBeCloseTo(0.5, 5);
    });

    it('should quarter weight after two half-lives', () => {
      const exp = createTestExperience('exp-1', {
        weight: 0.8,
        last_verified_at: daysAgoIso(60, NOW),
        half_life_days: 30,
      });
      expect(computeEffectiveWeight(exp, NOW)).toBeCloseTo(0.8 * 0.25, 5);
    });

    it('should respect custom half_life_days', () => {
      const exp = createTestExperience('exp-1', {
        weight: 1.0,
        last_verified_at: daysAgoIso(10, NOW),
        half_life_days: 10,
      });
      expect(computeEffectiveWeight(exp, NOW)).toBeCloseTo(0.5, 5);
    });

    it('should fall back to last_updated for legacy entries never verified', () => {
      const legacy = createTestExperience('exp-legacy', {
        last_updated: daysAgoIso(30, NOW).split('T')[0],
      });
      // legacy: weight 默认 1.0，half_life 默认 30 → 30 天后衰减为 0.5
      expect(computeEffectiveWeight(legacy, NOW)).toBeCloseTo(0.5, 2);
    });

    it('should prefer last_verified_at over last_updated', () => {
      const exp = createTestExperience('exp-1', {
        weight: 1.0,
        last_updated: '2026-01-01', // 很久以前
        last_verified_at: NOW.toISOString(), // 但刚验证过
      });
      expect(computeEffectiveWeight(exp, NOW)).toBeCloseTo(1.0, 5);
    });
  });

  // ─── verifyExperience：confirm 路径 ──────────────────────────────────────

  describe('verifyExperience confirmed', () => {
    it('should increase weight by 0.1, reset failures, update last_verified_at', () => {
      addExperience(
        createTestExperience('exp-1', {
          weight: 0.5,
          consecutive_failures: 2,
        }),
        TEST_DIR
      );

      const updated = verifyExperience('exp-1', 'confirmed', TEST_DIR);

      expect(updated).not.toBeNull();
      expect(updated!.weight).toBeCloseTo(0.6, 5);
      expect(updated!.consecutive_failures).toBe(0);
      expect(updated!.last_verified_at).not.toBeNull();

      // 持久化验证
      const base = loadExperienceBase(TEST_DIR);
      expect(base.experiences[0].weight).toBeCloseTo(0.6, 5);
      expect(base.experiences[0].consecutive_failures).toBe(0);
    });

    it('should cap weight at 1.0', () => {
      addExperience(createTestExperience('exp-1', { weight: 0.95 }), TEST_DIR);

      const updated = verifyExperience('exp-1', 'confirmed', TEST_DIR);
      expect(updated!.weight).toBe(1.0);
    });

    it('should revive a deprecated experience (failures reset below 3)', () => {
      addExperience(
        createTestExperience('exp-1', {
          weight: 0.1,
          consecutive_failures: 3,
          deprecated: true,
        }),
        TEST_DIR
      );

      const updated = verifyExperience('exp-1', 'confirmed', TEST_DIR);
      expect(updated!.consecutive_failures).toBe(0);
      expect(updated!.deprecated).toBe(false);
    });
  });

  // ─── verifyExperience：refute 路径 ───────────────────────────────────────

  describe('verifyExperience refuted', () => {
    it('should decrease weight by 0.2, increment failures, update last_verified_at', () => {
      addExperience(createTestExperience('exp-1', { weight: 0.5 }), TEST_DIR);

      const updated = verifyExperience('exp-1', 'refuted', TEST_DIR);

      expect(updated!.weight).toBeCloseTo(0.3, 5);
      expect(updated!.consecutive_failures).toBe(1);
      expect(updated!.last_verified_at).not.toBeNull();
      expect(updated!.deprecated).toBe(false);
    });

    it('should floor weight at 0', () => {
      addExperience(createTestExperience('exp-1', { weight: 0.1 }), TEST_DIR);

      const updated = verifyExperience('exp-1', 'refuted', TEST_DIR);
      expect(updated!.weight).toBe(0);
    });

    it('should mark deprecated after 3 consecutive failures', () => {
      addExperience(createTestExperience('exp-1', { weight: 1.0 }), TEST_DIR);

      verifyExperience('exp-1', 'refuted', TEST_DIR);
      verifyExperience('exp-1', 'refuted', TEST_DIR);
      const third = verifyExperience('exp-1', 'refuted', TEST_DIR);

      expect(third!.consecutive_failures).toBe(3);
      expect(third!.deprecated).toBe(true);
      expect(third!.weight).toBeCloseTo(0.4, 5); // 1.0 - 0.2*3
    });

    it('should work on legacy entries without metabolism fields', () => {
      // 旧格式：完全没有新字段
      addExperience(createTestExperience('exp-legacy'), TEST_DIR);

      const updated = verifyExperience('exp-legacy', 'refuted', TEST_DIR);

      expect(updated).not.toBeNull();
      expect(updated!.weight).toBeCloseTo(0.8, 5); // 默认 1.0 - 0.2
      expect(updated!.consecutive_failures).toBe(1);
    });

    it('should return null for unknown id', () => {
      const result = verifyExperience('exp-not-exist', 'confirmed', TEST_DIR);
      expect(result).toBeNull();
    });
  });

  // ─── 查询：deprecated 过滤 + effective_weight 标注 ───────────────────────

  describe('queryExperience with metabolism', () => {
    beforeEach(() => {
      const active = createTestExperience('exp-active', {
        scenario: '突破前高后回调',
        weight: 1.0,
        last_verified_at: new Date().toISOString(),
      });
      const deprecated = createTestExperience('exp-deprecated', {
        scenario: '突破前高后回调',
        weight: 0.2,
        consecutive_failures: 3,
        deprecated: true,
      });
      addExperience(active, TEST_DIR);
      addExperience(deprecated, TEST_DIR);
    });

    it('should exclude deprecated entries by default', () => {
      const results = queryExperience({ scenario: '突破' }, TEST_DIR);
      const ids = results.map(e => e.id);
      expect(ids).toContain('exp-active');
      expect(ids).not.toContain('exp-deprecated');
    });

    it('should include deprecated entries when include_deprecated is true', () => {
      const results = queryExperience({ scenario: '突破', include_deprecated: true }, TEST_DIR);
      const ids = results.map(e => e.id);
      expect(ids).toContain('exp-active');
      expect(ids).toContain('exp-deprecated');
    });

    it('should annotate effective_weight on query results', () => {
      const thirtyDaysAgo = daysAgoIso(30);
      addExperience(
        createTestExperience('exp-old', {
          scenario: '突破前高后回调',
          weight: 1.0,
          last_verified_at: thirtyDaysAgo,
          half_life_days: 30,
        }),
        TEST_DIR
      );

      const results = queryExperience({ scenario: '突破' }, TEST_DIR);
      const old = results.find(e => e.id === 'exp-old');
      expect(old).toBeDefined();
      expect(old!.effective_weight).toBeCloseTo(0.5, 1);

      const active = results.find(e => e.id === 'exp-active');
      expect(active!.effective_weight).toBeCloseTo(1.0, 1);
    });

    it('should normalize legacy entries in query results (default fields present)', () => {
      addExperience(createTestExperience('exp-legacy', { scenario: '突破前高后回调' }), TEST_DIR);

      const results = queryExperience({ scenario: '突破' }, TEST_DIR);
      const legacy = results.find(e => e.id === 'exp-legacy');

      expect(legacy).toBeDefined();
      expect(legacy!.weight).toBe(1.0);
      expect(legacy!.consecutive_failures).toBe(0);
      expect(legacy!.last_verified_at).toBeNull();
      expect(legacy!.half_life_days).toBe(30);
      expect(typeof legacy!.effective_weight).toBe('number');
    });
  });

  // ─── experience-query.ts（query_experience 工具背后的模块）────────────────

  describe('experience-query module (tool-facing)', () => {
    const QUERY_TEST_DIR = join(process.cwd(), '.test-experience-metabolism-query');
    const EXP_DIR = join(QUERY_TEST_DIR, '.pi-invest', 'experience');

    beforeEach(() => {
      if (existsSync(QUERY_TEST_DIR)) {
        rmSync(QUERY_TEST_DIR, { recursive: true });
      }
      mkdirSync(EXP_DIR, { recursive: true });
    });

    afterEach(() => {
      if (existsSync(QUERY_TEST_DIR)) {
        rmSync(QUERY_TEST_DIR, { recursive: true });
      }
    });

    function seedBase(experiences: Experience[]): void {
      const base: ExperienceBase = {
        version: '1.0.0',
        last_updated: '2026-07-29',
        experiences,
      };
      writeFileSync(join(EXP_DIR, 'experience-base.json'), JSON.stringify(base, null, 2));
    }

    it('should annotate weight/effective_weight/last_verified_at in formatted output', async () => {
      seedBase([
        createTestExperience('exp-1', {
          scenario: 'MACD金叉买入',
          weight: 0.8,
          last_verified_at: new Date().toISOString(),
          confidence: 0.9,
        }),
      ]);

      const origCwd = process.cwd;
      process.cwd = () => QUERY_TEST_DIR;
      try {
        const { queryAndFormatExperience } = await import('./experience-query.js');
        const result = queryAndFormatExperience({ scenario: 'MACD金叉', limit: 5 });

        expect(result).toContain('MACD金叉买入');
        expect(result).toContain('权重');
        expect(result).toContain('有效权重');
        expect(result).toContain('最近验证');
      } finally {
        process.cwd = origCwd;
      }
    });

    it('should filter deprecated entries by default and include them on demand', async () => {
      seedBase([
        createTestExperience('exp-ok', {
          scenario: 'MACD金叉买入',
          weight: 1.0,
          last_verified_at: new Date().toISOString(),
          confidence: 0.9,
        }),
        createTestExperience('exp-bad', {
          scenario: 'MACD金叉买入',
          weight: 0.1,
          consecutive_failures: 3,
          deprecated: true,
          confidence: 0.9,
          reason: '连续三次验证失败的经验',
        }),
      ]);

      const origCwd = process.cwd;
      process.cwd = () => QUERY_TEST_DIR;
      try {
        const { queryAndFormatExperience } = await import('./experience-query.js');

        const defaultResult = queryAndFormatExperience({ scenario: 'MACD金叉', limit: 5 });
        expect(defaultResult).not.toContain('连续三次验证失败的经验');

        const withDeprecated = queryAndFormatExperience({
          scenario: 'MACD金叉',
          limit: 5,
          include_deprecated: true,
        });
        expect(withDeprecated).toContain('连续三次验证失败的经验');
        expect(withDeprecated).toContain('已弃用');
      } finally {
        process.cwd = origCwd;
      }
    });
  });
});
