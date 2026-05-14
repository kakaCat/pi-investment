import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { loadExperienceBase, saveExperienceBase, addExperience, queryExperience } from './experience-manager.js';
import { existsSync, mkdirSync, writeFileSync, unlinkSync, rmdirSync } from 'fs';
import { join } from 'path';

const TEST_DIR = join(process.cwd(), '.pi-invest-test');
const TEST_EXPERIENCE_FILE = join(TEST_DIR, 'experience', 'experience-base.json');

describe('ExperienceManager', () => {
  beforeEach(() => {
    if (!existsSync(TEST_DIR)) {
      mkdirSync(TEST_DIR, { recursive: true });
      mkdirSync(join(TEST_DIR, 'experience'), { recursive: true });
    }
  });

  afterEach(() => {
    if (existsSync(TEST_EXPERIENCE_FILE)) {
      unlinkSync(TEST_EXPERIENCE_FILE);
    }
    if (existsSync(join(TEST_DIR, 'experience'))) {
      rmdirSync(join(TEST_DIR, 'experience'));
    }
    if (existsSync(TEST_DIR)) {
      rmdirSync(TEST_DIR);
    }
  });

  it('应该加载空经验库', () => {
    const base = loadExperienceBase(TEST_DIR);

    expect(base.version).toBe('1.0');
    expect(base.experiences).toEqual([]);
  });

  it('应该加载现有经验库', () => {
    const mockBase = {
      version: '1.0',
      last_updated: '2026-05-14',
      experiences: [
        {
          id: 'exp_001',
          scenario: '追涨买入',
          pattern: { conditions: ['涨幅>5%'], action: 'buy' as const },
          outcomes: { total_cases: 5, win_rate: 0.2, avg_return: -0.03 },
          recommendation: 'avoid' as const,
          reason: '胜率低',
          examples: [],
          confidence: 0.8,
          last_updated: '2026-05-14'
        }
      ]
    };

    writeFileSync(TEST_EXPERIENCE_FILE, JSON.stringify(mockBase, null, 2));

    const base = loadExperienceBase(TEST_DIR);

    expect(base.experiences).toHaveLength(1);
    expect(base.experiences[0].id).toBe('exp_001');
    expect(base.experiences[0].scenario).toBe('追涨买入');
  });

  it('应该保存经验库', () => {
    const base = loadExperienceBase(TEST_DIR);

    base.experiences.push({
      id: 'exp_002',
      scenario: 'MACD金叉',
      pattern: { conditions: ['MACD>0'], action: 'buy' },
      outcomes: { total_cases: 10, win_rate: 0.7, avg_return: 0.05 },
      recommendation: 'moderate',
      reason: '胜率较高',
      examples: [],
      confidence: 0.85,
      last_updated: '2026-05-14'
    });

    saveExperienceBase(base, TEST_DIR);

    const reloaded = loadExperienceBase(TEST_DIR);
    expect(reloaded.experiences).toHaveLength(1);
    expect(reloaded.experiences[0].scenario).toBe('MACD金叉');
  });
});

describe('ExperienceManager - queryExperience', () => {
  beforeEach(() => {
    if (!existsSync(TEST_DIR)) {
      mkdirSync(TEST_DIR, { recursive: true });
      mkdirSync(join(TEST_DIR, 'experience'), { recursive: true });
    }

    const base = {
      version: '1.0',
      last_updated: '2026-05-14',
      experiences: [
        {
          id: 'exp_001',
          scenario: '追涨买入',
          pattern: { conditions: ['涨幅>5%', 'RSI>70'], action: 'buy' as const },
          outcomes: { total_cases: 8, win_rate: 0.25, avg_return: -0.035 },
          recommendation: 'avoid' as const,
          reason: '胜率低',
          examples: [],
          confidence: 0.88,
          last_updated: '2026-05-14'
        },
        {
          id: 'exp_002',
          scenario: 'MACD金叉买入',
          pattern: { conditions: ['MACD>0', '成交量放大'], action: 'buy' as const },
          outcomes: { total_cases: 12, win_rate: 0.75, avg_return: 0.058 },
          recommendation: 'moderate' as const,
          reason: '胜率较高',
          examples: [],
          confidence: 0.82,
          last_updated: '2026-05-14'
        }
      ]
    };

    writeFileSync(TEST_EXPERIENCE_FILE, JSON.stringify(base, null, 2));
  });

  afterEach(() => {
    if (existsSync(TEST_EXPERIENCE_FILE)) {
      unlinkSync(TEST_EXPERIENCE_FILE);
    }
    if (existsSync(join(TEST_DIR, 'experience'))) {
      rmdirSync(join(TEST_DIR, 'experience'));
    }
    if (existsSync(TEST_DIR)) {
      rmdirSync(TEST_DIR);
    }
  });

  it('应该根据场景查询经验', () => {
    const results = queryExperience({ scenario: '追涨' }, TEST_DIR);

    expect(results).toHaveLength(1);
    expect(results[0].scenario).toBe('追涨买入');
  });

  it('应该根据条件查询经验', () => {
    const results = queryExperience(
      { conditions: ['MACD>0'] },
      TEST_DIR
    );

    expect(results).toHaveLength(1);
    expect(results[0].scenario).toBe('MACD金叉买入');
  });

  it('应该按置信度排序', () => {
    const results = queryExperience({ scenario: '买入' }, TEST_DIR);

    expect(results).toHaveLength(2);
    expect(results[0].confidence).toBeGreaterThanOrEqual(results[1].confidence);
  });

  it('应该返回空数组如果没有匹配', () => {
    const results = queryExperience({ scenario: '不存在的场景' }, TEST_DIR);

    expect(results).toEqual([]);
  });
});
