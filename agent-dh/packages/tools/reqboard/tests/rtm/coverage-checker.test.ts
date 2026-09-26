import { describe, it, expect } from 'vitest';
import { CoverageChecker } from '../../src/rtm/coverage-checker.js';
import type { FRMetadata, TaskCoverage } from '../../src/types/rtm.js';

describe('Coverage Checker', () => {
  describe('checkCoverage', () => {
    it('输入 3 个 FR（task_coverage 只覆盖 2 个），返回 unreceived_clauses = [FR-3], coverage_rate = 67%', () => {
      // 准备 3 个 FR
      const frMetadata: FRMetadata[] = [
        {
          id: 'FR-1',
          title: 'FR 1',
          priority: 'P1',
          file: 'FR-1.md',
          acceptance_criteria: [
            { id: 'FR-1-A1', description: 'Test 1', verification: 'Test' }
          ]
        },
        {
          id: 'FR-2',
          title: 'FR 2',
          priority: 'P1',
          file: 'FR-2.md',
          acceptance_criteria: [
            { id: 'FR-2-A1', description: 'Test 2', verification: 'Test' }
          ]
        },
        {
          id: 'FR-3',
          title: 'FR 3',
          priority: 'P1',
          file: 'FR-3.md',
          acceptance_criteria: [
            { id: 'FR-3-A1', description: 'Test 3', verification: 'Test' }
          ]
        }
      ];
      
      // 准备任务覆盖（只覆盖 FR-1 和 FR-2）
      const taskCoverage: TaskCoverage[] = [
        {
          task_id: 't-1',
          task_key: 't1',
          task_title: 'Task 1',
          covers_frs: ['FR-1'],
          covers_acceptance: ['FR-1-A1'],
          assigned_at: Date.now()
        },
        {
          task_id: 't-2',
          task_key: 't2',
          task_title: 'Task 2',
          covers_frs: ['FR-2'],
          covers_acceptance: ['FR-2-A1'],
          assigned_at: Date.now()
        }
      ];
      
      // 检查覆盖度
      const result = CoverageChecker.checkCoverage(frMetadata, taskCoverage);
      
      expect(result.total_frs).toBe(3);
      expect(result.covered_frs).toBe(2);
      expect(result.unreceived_clauses).toEqual(['FR-3']);
      expect(result.coverage_rate).toBe(67); // 2/3 = 66.67% ≈ 67%
    });
    
    it('所有 FR 都被覆盖时，返回 coverage_rate = 100%', () => {
      const frMetadata: FRMetadata[] = [
        {
          id: 'FR-1',
          title: 'FR 1',
          priority: 'P1',
          file: 'FR-1.md',
          acceptance_criteria: []
        },
        {
          id: 'FR-2',
          title: 'FR 2',
          priority: 'P1',
          file: 'FR-2.md',
          acceptance_criteria: []
        }
      ];
      
      const taskCoverage: TaskCoverage[] = [
        {
          task_id: 't-1',
          task_key: 't1',
          task_title: 'Task 1',
          covers_frs: ['FR-1', 'FR-2'],
          covers_acceptance: [],
          assigned_at: Date.now()
        }
      ];
      
      const result = CoverageChecker.checkCoverage(frMetadata, taskCoverage);
      
      expect(result.total_frs).toBe(2);
      expect(result.covered_frs).toBe(2);
      expect(result.unreceived_clauses).toEqual([]);
      expect(result.coverage_rate).toBe(100);
    });
  });
  
  describe('validateCoverage', () => {
    it('覆盖度 < 100% 时抛出错误，错误信息包含 "未覆盖的 FR: FR-3"', () => {
      const frMetadata: FRMetadata[] = [
        { id: 'FR-1', title: 'FR 1', priority: 'P1', file: 'FR-1.md', acceptance_criteria: [] },
        { id: 'FR-2', title: 'FR 2', priority: 'P1', file: 'FR-2.md', acceptance_criteria: [] },
        { id: 'FR-3', title: 'FR 3', priority: 'P1', file: 'FR-3.md', acceptance_criteria: [] }
      ];
      
      const taskCoverage: TaskCoverage[] = [
        {
          task_id: 't-1',
          task_key: 't1',
          task_title: 'Task 1',
          covers_frs: ['FR-1', 'FR-2'],
          covers_acceptance: [],
          assigned_at: Date.now()
        }
      ];
      
      expect(() => {
        CoverageChecker.validateCoverage(frMetadata, taskCoverage);
      }).toThrow('未覆盖的 FR: FR-3');
    });
    
    it('覆盖度 = 100% 时不抛出错误', () => {
      const frMetadata: FRMetadata[] = [
        { id: 'FR-1', title: 'FR 1', priority: 'P1', file: 'FR-1.md', acceptance_criteria: [] },
        { id: 'FR-2', title: 'FR 2', priority: 'P1', file: 'FR-2.md', acceptance_criteria: [] }
      ];
      
      const taskCoverage: TaskCoverage[] = [
        {
          task_id: 't-1',
          task_key: 't1',
          task_title: 'Task 1',
          covers_frs: ['FR-1', 'FR-2'],
          covers_acceptance: [],
          assigned_at: Date.now()
        }
      ];
      
      expect(() => {
        CoverageChecker.validateCoverage(frMetadata, taskCoverage);
      }).not.toThrow();
    });
  });
});
