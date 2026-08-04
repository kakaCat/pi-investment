/**
 * Strategy Batch Validate Tool Tests
 */
import { describe, it, expect, jest, beforeEach } from '@jest/globals';

const mockBatchValidateStrategies = jest.fn<(params: any) => Promise<any>>();

jest.unstable_mockModule('../../adapters/quant/quant-v2-client.js', () => ({
  batchValidateStrategies: mockBatchValidateStrategies
}));

const { strategyBatchValidateTool } = await import('./batch-validate-tool.js');

describe('strategyBatchValidateTool', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should validate strategies successfully', async () => {
    // Arrange
    const mockResponse = {
      success: true,
      data: {
        total: 2,
        passed: 1,
        failed: 1,
        duration: 120,
        details: [
          {
            strategyId: 1,
            strategyName: 'Strategy A',
            score: 68.5,
            status: 'passed' as const,
            metrics: {
              annualReturn: 0.15,
              sharpeRatio: 1.5,
              maxDrawdown: -0.20,
              winRate: 0.60,
              profitFactor: 2.0
            },
            backtestCount: 400,
            errorCount: 5
          }
        ]
      }
    };

    mockBatchValidateStrategies.mockResolvedValue(mockResponse);

    // Act
    const result = await (strategyBatchValidateTool.execute as any)('test-call-id', {
      startDate: '2024-05-27',
      endDate: '2026-05-27',
      threshold: 60,
      dryRun: false
    });

    // Assert
    expect(mockBatchValidateStrategies).toHaveBeenCalledWith({
      startDate: '2024-05-27',
      endDate: '2026-05-27',
      threshold: 60,
      dryRun: false
    });
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    expect((result.content[0] as any).text).toContain('总数: 2');
    expect((result.content[0] as any).text).toContain('通过: 1');
    expect((result.content[0] as any).text).toContain('失败: 1');
  });

  it('should handle validation errors', async () => {
    // Arrange
    mockBatchValidateStrategies.mockRejectedValue(new Error('API error'));

    // Act
    const result = await (strategyBatchValidateTool.execute as any)('test-call-id', {
      startDate: '2024-05-27',
      endDate: '2026-05-27',
      threshold: 60,
      dryRun: false
    });

    // Assert
    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    expect((result.content[0] as any).text).toContain('执行失败');
    expect((result.content[0] as any).text).toContain('API error');
  });
});
