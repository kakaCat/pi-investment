import { describe, it, expect } from 'vitest';
import { RTMManager } from '../../src/rtm/rtm-manager.js';
import { scanFRDirectory } from '../../src/rtm/fr-parser.js';

describe('RTM Manager', () => {
  const testReqDir = 'docs/requirements/REQ-260925172227-2d61';
  
  describe('fillTaskCoverage', () => {
    it('输入 2 个任务，输出 task_coverage 包含 2 项，covers_acceptance 正确填充', () => {
      const tasks = [
        {
          key: 't1',
          title: '任务 1',
          requirement_refs: ['FR-1']
        },
        {
          key: 't2',
          title: '任务 2',
          requirement_refs: ['FR-2', 'FR-3']
        }
      ];
      
      const result = RTMManager.fillTaskCoverage(testReqDir, tasks);
      
      expect(result).toHaveLength(2);
      
      // 检查第一个任务
      expect(result[0].task_key).toBe('t1');
      expect(result[0].covers_frs).toEqual(['FR-1']);
      expect(result[0].covers_acceptance.length).toBeGreaterThan(0);
      expect(result[0].covers_acceptance.some(id => id.startsWith('FR-1-'))).toBe(true);
      
      // 检查第二个任务
      expect(result[1].task_key).toBe('t2');
      expect(result[1].covers_frs).toEqual(['FR-2', 'FR-3']);
      expect(result[1].covers_acceptance.length).toBeGreaterThan(0);
      expect(result[1].covers_acceptance.some(id => id.startsWith('FR-2-'))).toBe(true);
      expect(result[1].covers_acceptance.some(id => id.startsWith('FR-3-'))).toBe(true);
    });
  });
  
  describe('fillAcceptanceTracking', () => {
    it('输入 3 个 FR（共 12 个验收项），输出 12 条 pending 记录', () => {
      const frMetadata = scanFRDirectory(testReqDir);
      
      // 应该至少有 3 个 FR
      expect(frMetadata.length).toBeGreaterThanOrEqual(3);
      
      const result = RTMManager.fillAcceptanceTracking(frMetadata);
      
      // 应该至少有 12 条记录（3 个 FR × 至少 4 个验收项）
      expect(result.length).toBeGreaterThanOrEqual(12);
      
      // 所有记录初始状态应该是 pending
      expect(result.every(r => r.status === 'pending')).toBe(true);
      
      // 检查第一条记录的结构
      expect(result[0]).toHaveProperty('acceptance_id');
      expect(result[0]).toHaveProperty('fr_id');
      expect(result[0]).toHaveProperty('description');
      expect(result[0]).toHaveProperty('verification');
      expect(result[0].status).toBe('pending');
      expect(result[0].evidence).toBeNull();
      expect(result[0].judged_at).toBeNull();
      expect(result[0].judged_by).toBeNull();
    });
  });
  
  describe('updateAcceptanceTracking', () => {
    it('输入 judgements（10 passed, 2 failed），更新后状态正确', () => {
      // 1. 先生成初始追踪记录
      const frMetadata = scanFRDirectory(testReqDir);
      const tracking = RTMManager.fillAcceptanceTracking(frMetadata);
      
      // 2. 构造裁决结果：前 10 条 passed，后 2 条 failed
      const judgements: Record<string, { status: 'passed' | 'failed'; evidence?: string; feedback?: string }> = {};
      
      for (let i = 0; i < Math.min(10, tracking.length); i++) {
        judgements[tracking[i].acceptance_id] = {
          status: 'passed',
          evidence: `Test passed for ${tracking[i].acceptance_id}`
        };
      }
      
      for (let i = 10; i < Math.min(12, tracking.length); i++) {
        judgements[tracking[i].acceptance_id] = {
          status: 'failed',
          feedback: `Need rework for ${tracking[i].acceptance_id}`
        };
      }
      
      // 3. 更新追踪记录
      const updated = RTMManager.updateAcceptanceTracking(tracking, judgements, 'test-user');
      
      // 4. 验证更新结果
      const passed = updated.filter(r => r.status === 'passed');
      const failed = updated.filter(r => r.status === 'failed');
      const pending = updated.filter(r => r.status === 'pending');
      
      expect(passed.length).toBe(10);
      expect(failed.length).toBe(2);
      expect(pending.length).toBe(tracking.length - 12);
      
      // 验证 passed 记录有 evidence
      expect(passed[0].evidence).toBeTruthy();
      expect(passed[0].judged_at).toBeTruthy();
      expect(passed[0].judged_by).toBe('test-user');
      
      // 验证 failed 记录有 feedback
      expect(failed[0].user_feedback).toBeTruthy();
      expect(failed[0].judged_at).toBeTruthy();
      expect(failed[0].judged_by).toBe('test-user');
    });
  });
});
