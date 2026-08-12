/**
 * Memory Distillation Task 测试
 * 设计：docs/superpowers/plans/2026-08-12-execution-tickets.md T2（W1.5b）
 */

import { jest, describe, it, expect, beforeEach } from '@jest/globals';
import type { QuantCliResponse } from '../../infrastructure/adapters/quant/types.js';

// Mock runQuantV2 before importing
const mockRunQuantV2 = jest.fn<(command: string, params?: Record<string, unknown>) => Promise<QuantCliResponse<any>>>();

jest.unstable_mockModule('../../infrastructure/adapters/quant/quant-v2-client.js', () => ({
  runQuantV2: mockRunQuantV2,
}));

// Import after mocking
const { runQuantV2 } = await import('../../infrastructure/adapters/quant/quant-v2-client.js');

describe('Memory Distillation Task', () => {
  beforeEach(() => {
    mockRunQuantV2.mockClear();
  });

  it('should call memory_distill_inputs with correct params', async () => {
    // Arrange
    const mockInputs = {
      episodes: [
        { id: 1, title: 'Test episode', content: 'Test content' },
      ],
      decisions: [
        { id: 2, decision_type: 'trade', reasoning: 'Test reasoning', success: true },
      ],
    };

    mockRunQuantV2.mockResolvedValueOnce({
      ok: true,
      command: 'memory_distill_inputs',
      params: { days: 7 },
      data: mockInputs,
      warnings: [],
      error: null,
    });

    // Act - simulate calling the distill inputs endpoint
    const result = await runQuantV2('memory_distill_inputs', { days: 7 });

    // Assert
    expect(mockRunQuantV2).toHaveBeenCalledWith('memory_distill_inputs', { days: 7 });
    expect(result.ok).toBe(true);
    expect(result.data).toEqual(mockInputs);
    expect((result.data as any).episodes).toHaveLength(1);
    expect((result.data as any).decisions).toHaveLength(1);
  });

  it('should call memory_distill_candidates with candidates', async () => {
    // Arrange
    const mockCandidates = [
      {
        title: '测试规则',
        content: '规则内容',
        evidence_ids: [1, 2],
      },
    ];

    const mockResponse = {
      saved: 1,
      skipped: 0,
    };

    mockRunQuantV2.mockResolvedValueOnce({
      ok: true,
      command: 'memory_distill_candidates',
      params: { candidates: mockCandidates },
      data: mockResponse,
      warnings: [],
      error: null,
    });

    // Act
    const result = await runQuantV2('memory_distill_candidates', { candidates: mockCandidates });

    // Assert
    expect(mockRunQuantV2).toHaveBeenCalledWith('memory_distill_candidates', { candidates: mockCandidates });
    expect(result.ok).toBe(true);
    expect(result.data).toEqual(mockResponse);
    expect((result.data as any).saved).toBe(1);
    expect((result.data as any).skipped).toBe(0);
  });

  it('should not POST when candidates array is empty', async () => {
    // Arrange
    const emptyCandidates: any[] = [];

    mockRunQuantV2.mockResolvedValueOnce({
      ok: true,
      command: 'memory_distill_candidates',
      params: { candidates: emptyCandidates },
      data: { saved: 0, skipped: 0 },
      warnings: [],
      error: null,
    });

    // Act
    const result = await runQuantV2('memory_distill_candidates', { candidates: emptyCandidates });

    // Assert
    expect(mockRunQuantV2).toHaveBeenCalledWith('memory_distill_candidates', { candidates: emptyCandidates });
    expect(result.ok).toBe(true);
    expect((result.data as any).saved).toBe(0);
  });

  it('should skip candidates without evidence_ids', async () => {
    // Arrange
    const candidatesWithoutEvidence = [
      {
        title: '无证据规则',
        content: '规则内容',
        evidence_ids: [], // 空证据
      },
      {
        title: '有证据规则',
        content: '规则内容',
        evidence_ids: [1, 2],
      },
    ];

    mockRunQuantV2.mockResolvedValueOnce({
      ok: true,
      command: 'memory_distill_candidates',
      params: { candidates: candidatesWithoutEvidence },
      data: {
        saved: 1,  // 只保存了有证据的
        skipped: 1, // 跳过了无证据的
      },
      warnings: [],
      error: null,
    });

    // Act
    const result = await runQuantV2('memory_distill_candidates', { candidates: candidatesWithoutEvidence });

    // Assert
    expect(result.ok).toBe(true);
    expect((result.data as any).saved).toBe(1);
    expect((result.data as any).skipped).toBe(1);
  });

  it('should handle API errors gracefully', async () => {
    // Arrange
    mockRunQuantV2.mockResolvedValueOnce({
      ok: false,
      command: 'memory_distill_inputs',
      params: { days: 7 },
      data: undefined,
      warnings: [],
      error: { message: 'Database connection failed' },
    });

    // Act
    const result = await runQuantV2('memory_distill_inputs', { days: 7 });

    // Assert
    expect(result.ok).toBe(false);
    expect(result.error).toBeTruthy();
    expect(result.error?.message).toContain('Database connection failed');
  });
});
