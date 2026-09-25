import { describe, it, expect } from 'vitest';
import { checkAcceptanceGate } from '../src/application/internal/accept-sheet-rtm-integration.js';
import type { VerificationSheet } from '../src/shared/protocol.js';

describe('AcceptSheet RTM Integration', () => {
  it('部分通过：12项验收（10 passed, 2 failed），返回gate_status=blocked, archived=false', () => {
    const sheet: VerificationSheet = {
      version: 1,
      items: [
        // 10 项 passed
        ...Array.from({ length: 10 }, (_, i) => ({
          id: `item-${i + 1}`,
          source: { kind: 'task' as const, taskId: `t-${i + 1}` },
          criterion: `验收项${i + 1}`,
          howToVerify: `验证方式${i + 1}`,
          status: 'passed' as const,
          evidence: `已通过 ${i + 1}`,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: null
        })),
        // 2 项 failed
        {
          id: 'item-11',
          source: { kind: 'task' as const, taskId: 't-11' },
          criterion: '验收项11',
          howToVerify: '验证方式11',
          status: 'failed' as const,
          evidence: null,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: 'Need rework'
        },
        {
          id: 'item-12',
          source: { kind: 'task' as const, taskId: 't-12' },
          criterion: '验收项12',
          howToVerify: '验证方式12',
          status: 'failed' as const,
          evidence: null,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: 'Fix required'
        }
      ],
      reworkOnly: false,
      generatedAt: Date.now(),
      generatedBy: { kind: 'agent' as const, sessionId: 'test' }
    };

    const result = checkAcceptanceGate(sheet);

    // 验证门禁检查结果
    expect(result.gate_check.total).toBe(12);
    expect(result.gate_check.passed).toBe(10);
    expect(result.gate_check.failed).toBe(2);
    expect(result.gate_check.pending).toBe(0);
    expect(result.gate_check.pass_rate).toBe(83); // 10/12 ≈ 83%
    expect(result.gate_check.gate_status).toBe('blocked');
    
    // 验证不应该自动归档
    expect(result.should_archive).toBe(false);
  });

  it('全部通过：12项验收（12 passed），返回gate_status=passed, archived=true', () => {
    const sheet: VerificationSheet = {
      version: 1,
      items: Array.from({ length: 12 }, (_, i) => ({
        id: `item-${i + 1}`,
        source: { kind: 'task' as const, taskId: `t-${i + 1}` },
        criterion: `验收项${i + 1}`,
        howToVerify: `验证方式${i + 1}`,
        status: 'passed' as const,
        evidence: `已通过 ${i + 1}`,
        decidedAt: Date.now(),
        decidedBy: { kind: 'human' as const, sessionId: 'test' },
        opinion: null
      })),
      reworkOnly: false,
      generatedAt: Date.now(),
      generatedBy: { kind: 'agent' as const, sessionId: 'test' }
    };

    const result = checkAcceptanceGate(sheet);

    // 验证门禁检查结果
    expect(result.gate_check.total).toBe(12);
    expect(result.gate_check.passed).toBe(12);
    expect(result.gate_check.failed).toBe(0);
    expect(result.gate_check.pending).toBe(0);
    expect(result.gate_check.pass_rate).toBe(100);
    expect(result.gate_check.gate_status).toBe('passed');
    
    // 验证应该自动归档
    expect(result.should_archive).toBe(true);
  });

  it('部分待验：10项验收（5 passed, 0 failed, 5 pending），返回gate_status=pending, archived=false', () => {
    const sheet: VerificationSheet = {
      version: 1,
      items: [
        // 5 项 passed
        ...Array.from({ length: 5 }, (_, i) => ({
          id: `item-${i + 1}`,
          source: { kind: 'task' as const, taskId: `t-${i + 1}` },
          criterion: `验收项${i + 1}`,
          howToVerify: `验证方式${i + 1}`,
          status: 'passed' as const,
          evidence: `已通过 ${i + 1}`,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: null
        })),
        // 5 项 pending
        ...Array.from({ length: 5 }, (_, i) => ({
          id: `item-${i + 6}`,
          source: { kind: 'task' as const, taskId: `t-${i + 6}` },
          criterion: `验收项${i + 6}`,
          howToVerify: `验证方式${i + 6}`,
          status: 'pending' as const,
          evidence: null,
          decidedAt: null,
          decidedBy: null,
          opinion: null
        }))
      ],
      reworkOnly: false,
      generatedAt: Date.now(),
      generatedBy: { kind: 'agent' as const, sessionId: 'test' }
    };

    const result = checkAcceptanceGate(sheet);

    // 验证门禁检查结果
    expect(result.gate_check.total).toBe(10);
    expect(result.gate_check.passed).toBe(5);
    expect(result.gate_check.failed).toBe(0);
    expect(result.gate_check.pending).toBe(5);
    expect(result.gate_check.pass_rate).toBe(50); // 5/10 = 50%
    expect(result.gate_check.gate_status).toBe('pending');
    
    // 验证不应该自动归档
    expect(result.should_archive).toBe(false);
  });

  it('兼容性：无验收单时返回默认值不报错', () => {
    const result = checkAcceptanceGate(undefined);

    expect(result.gate_check.total).toBe(0);
    expect(result.gate_check.passed).toBe(0);
    expect(result.gate_check.failed).toBe(0);
    expect(result.gate_check.pending).toBe(0);
    expect(result.gate_check.pass_rate).toBe(0);
    expect(result.gate_check.gate_status).toBe('pending');
    expect(result.should_archive).toBe(false);
  });
});
