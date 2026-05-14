/**
 * Experience Manager Tests
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdirSync, writeFileSync, rmSync, existsSync, readdirSync } from 'fs';
import { join } from 'path';
import {
  loadExperienceBase,
  saveExperienceBase,
  addExperience,
  addExperiences,
  removeExperience,
  mergeExperiences,
  queryExperience,
} from './experience-manager.js';
import type { Experience, ExperienceBase } from '../../types/evolution.js';

const TEST_DIR = join(process.cwd(), '.test-experience');

describe('Experience Manager', () => {
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

  const createTestExperience = (id: string): Experience => ({
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
      max_gain: 15,
      max_loss: -8,
    },
    recommendation: 'moderate',
    reason: '测试原因',
    examples: [
      {
        date: '2026-05-13',
        symbol: '600036',
        session_id: 'test-session',
        result: 5.5,
      },
    ],
    confidence: 0.7,
    last_updated: '2026-05-14',
  });

  describe('loadExperienceBase', () => {
    it('should return empty base if file does not exist', () => {
      const base = loadExperienceBase(TEST_DIR);
      expect(base.version).toBe('1.0.0');
      expect(base.experiences).toEqual([]);
    });

    it('should load existing experience base', () => {
      const testBase: ExperienceBase = {
        version: '1.0.0',
        last_updated: '2026-05-14',
        experiences: [createTestExperience('exp-1')],
      };

      const expDir = join(TEST_DIR, 'experience');
      mkdirSync(expDir, { recursive: true });
      writeFileSync(
        join(expDir, 'experiences.json'),
        JSON.stringify(testBase, null, 2)
      );

      const loaded = loadExperienceBase(TEST_DIR);
      expect(loaded.version).toBe('1.0.0');
      expect(loaded.experiences).toHaveLength(1);
      expect(loaded.experiences[0].id).toBe('exp-1');
    });

    it('should throw error if format is invalid', () => {
      const expDir = join(TEST_DIR, 'experience');
      mkdirSync(expDir, { recursive: true });
      writeFileSync(join(expDir, 'experiences.json'), '{"invalid": true}');

      expect(() => loadExperienceBase(TEST_DIR)).toThrow('Invalid experience base format');
    });
  });

  describe('saveExperienceBase', () => {
    it('should save experience base with version increment', () => {
      const base: ExperienceBase = {
        version: '1.0.0',
        last_updated: '2026-05-14',
        experiences: [createTestExperience('exp-1')],
      };

      saveExperienceBase(base, TEST_DIR);

      const loaded = loadExperienceBase(TEST_DIR);
      expect(loaded.version).toBe('1.0.1');
      expect(loaded.experiences).toHaveLength(1);
    });
  });

  describe('addExperience', () => {
    it('should add new experience', () => {
      const exp = createTestExperience('exp-1');
      addExperience(exp, TEST_DIR);

      const base = loadExperienceBase(TEST_DIR);
      expect(base.experiences).toHaveLength(1);
      expect(base.experiences[0].id).toBe('exp-1');
    });

    it('should update existing experience', () => {
      const exp1 = createTestExperience('exp-1');
      addExperience(exp1, TEST_DIR);

      const exp2 = { ...exp1, confidence: 0.9 };
      addExperience(exp2, TEST_DIR);

      const base = loadExperienceBase(TEST_DIR);
      expect(base.experiences).toHaveLength(1);
      expect(base.experiences[0].confidence).toBe(0.9);
    });
  });

  describe('queryExperience', () => {
    beforeEach(() => {
      const exp1 = createTestExperience('exp-1');
      exp1.scenario = '突破前高后回调';
      exp1.pattern.conditions = ['MACD金叉', 'RSI>70'];
      exp1.confidence = 0.8;

      const exp2 = createTestExperience('exp-2');
      exp2.scenario = '跌破支撑位';
      exp2.pattern.conditions = ['MACD死叉', 'RSI<30'];
      exp2.pattern.action = 'sell';
      exp2.confidence = 0.6;

      addExperiences([exp1, exp2], TEST_DIR);
    });

    it('should query by scenario', () => {
      const results = queryExperience({ scenario: '突破' }, TEST_DIR);
      expect(results.length).toBeGreaterThanOrEqual(1);
    });

    it('should query by conditions', () => {
      const results = queryExperience({ conditions: ['MACD金叉'] }, TEST_DIR);
      expect(results.length).toBeGreaterThanOrEqual(1);
    });

    it('should sort by confidence', () => {
      const results = queryExperience({ scenario: '突破' }, TEST_DIR);
      if (results.length > 1) {
        expect(results[0].confidence).toBeGreaterThanOrEqual(results[1].confidence);
      }
    });
  });
});
