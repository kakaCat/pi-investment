import { describe, it, expect } from 'vitest';
import { AcceptanceGate } from '../../src/rtm/acceptance-gate.js';
import type { AcceptanceTracking } from '../../src/types/rtm.js';

describe('Acceptance Gate', () => {
  describe('checkGate', () => {
    it('输入 12 个验收项（10 passed, 2 failed），返回 pass_rate=83%, gate_status=blocked, failed_items 包含 2 项', () => {
      // 准备 12 个验收项：10 passed, 2 failed
      const tracking: AcceptanceTracking[] = [];
      
      // 10 个 passed
      for (let i = 1; i <= 10; i++) {
        tracking.push({
          acceptance_id: `FR-${i}-A1`,
          fr_id: `FR-${i}`,
          description: `Test ${i}`,
          verification: 'Verify',
          status: 'passed',
          evidence: `Passed test ${i}`,
          judged_at: Date.now(),
          judged_by: 'test-user',
          user_feedback: null
        });
      }
      
      // 2 个 failed
      tracking.push({
        acceptance_id: 'FR-11-A1',
        fr_id: 'FR-11',
        description: 'Test 11',
        verification: 'Verify',
        status: 'failed',
        evidence: null,
        judged_at: Date.now(),
        judged_by: 'test-user',
        user_feedback: 'Need rework'
      });
      
      tracking.push({
        acceptance_id: 'FR-12-A1',
        fr_id: 'FR-12',
        description: 'Test 12',
        verification: 'Verify',
        status: 'failed',
        evidence: null,
        judged_at: Date.now(),
        judged_by: 'test-user',
        user_feedback: 'Fix required'
      });
      
      const result = AcceptanceGate.checkGate(tracking);
      
      expect(result.total).toBe(12);
      expect(result.passed).toBe(10);
      expect(result.failed).toBe(2);
      expect(result.pending).toBe(0);
      expect(result.pass_rate).toBe(83); // 10/12 = 83.33% ≈ 83%
      expect(result.gate_status).toBe('blocked');
      expect(result.failed_items).toHaveLength(2);
      expect(result.failed_items[0].acceptance_id).toBe('FR-11-A1');
      expect(result.failed_items[1].acceptance_id).toBe('FR-12-A1');
    });
    
    it('输入 12 个验收项（12 passed），返回 pass_rate=100%, gate_status=passed', () => {
      // 准备 12 个全部 passed 的验收项
      const tracking: AcceptanceTracking[] = [];
      
      for (let i = 1; i <= 12; i++) {
        tracking.push({
          acceptance_id: `FR-${i}-A1`,
          fr_id: `FR-${i}`,
          description: `Test ${i}`,
          verification: 'Verify',
          status: 'passed',
          evidence: `Passed test ${i}`,
          judged_at: Date.now(),
          judged_by: 'test-user',
          user_feedback: null
        });
      }
      
      const result = AcceptanceGate.checkGate(tracking);
      
      expect(result.total).toBe(12);
      expect(result.passed).toBe(12);
      expect(result.failed).toBe(0);
      expect(result.pending).toBe(0);
      expect(result.pass_rate).toBe(100);
      expect(result.gate_status).toBe('passed');
      expect(result.failed_items).toHaveLength(0);
    });
    
    it('还有待验项时，gate_status 应为 pending', () => {
      const tracking: AcceptanceTracking[] = [
        {
          acceptance_id: 'FR-1-A1',
          fr_id: 'FR-1',
          status: 'passed',
          evidence: 'Done',
          judged_at: Date.now(),
          judged_by: 'user',
          user_feedback: null
        },
        {
          acceptance_id: 'FR-2-A1',
          fr_id: 'FR-2',
          status: 'pending',
          evidence: null,
          judged_at: null,
          judged_by: null,
          user_feedback: null
        }
      ];
      
      const result = AcceptanceGate.checkGate(tracking);
      
      expect(result.gate_status).toBe('pending');
      expect(result.pending).toBe(1);
    });
  });
  
  describe('shouldAutoArchive', () => {
    it('gate_status=passed 时返回 true', () => {
      const gateResult = {
        total: 12,
        passed: 12,
        failed: 0,
        pending: 0,
        pass_rate: 100,
        gate_status: 'passed' as const,
        failed_items: []
      };
      
      expect(AcceptanceGate.shouldAutoArchive(gateResult)).toBe(true);
    });
    
    it('gate_status=blocked 时返回 false', () => {
      const gateResult = {
        total: 12,
        passed: 10,
        failed: 2,
        pending: 0,
        pass_rate: 83,
        gate_status: 'blocked' as const,
        failed_items: []
      };
      
      expect(AcceptanceGate.shouldAutoArchive(gateResult)).toBe(false);
    });
    
    it('gate_status=pending 时返回 false', () => {
      const gateResult = {
        total: 12,
        passed: 10,
        failed: 0,
        pending: 2,
        pass_rate: 83,
        gate_status: 'pending' as const,
        failed_items: []
      };
      
      expect(AcceptanceGate.shouldAutoArchive(gateResult)).toBe(false);
    });
  });
});
