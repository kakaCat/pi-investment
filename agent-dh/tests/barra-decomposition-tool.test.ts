/**
 * BarraDecompositionTool 单元测试
 *
 * 验证 C/D-class 修复：工具传递 symbols+dates 而非 account_name
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BarraDecompositionTool } from '../packages/risk/src/tools/BarraDecompositionTool/BarraDecompositionTool.js';

describe('BarraDecompositionTool', () => {
  let tool: BarraDecompositionTool;
  let mockClient: any;
  const mockContext = {} as any;

  beforeEach(() => {
    mockClient = {
      getBarraDecomposition: vi.fn(),
    };
    tool = new BarraDecompositionTool(mockClient);
  });

  describe('validate', () => {
    it('always passes (all params optional)', () => {
      const result = (tool as any).validate({});
      expect(result.success).toBe(true);
    });
  });

  describe('execute', () => {
    it('uses default symbols when none provided', async () => {
      mockClient.getBarraDecomposition.mockResolvedValue({
        total_risk: 15.5,
        factor_risks: [],
        idiosyncratic_risk: 5.0,
        industry_concentration: 0.3,
        style_exposure: {},
      });

      await (tool as any).execute({}, mockContext);

      expect(mockClient.getBarraDecomposition).toHaveBeenCalledOnce();
      const callArgs = mockClient.getBarraDecomposition.mock.calls[0][0];
      expect(callArgs.symbols).toEqual(['600519', '000858', '601318', '000001', '600036']);
      expect(callArgs.start_date).toBeDefined();
      expect(callArgs.end_date).toBeDefined();
    });

    it('passes custom symbols when provided', async () => {
      mockClient.getBarraDecomposition.mockResolvedValue({ total_risk: 10 });

      await (tool as any).execute({
        symbols: ['000001', '600036'],
        start_date: '2026-01-01',
        end_date: '2026-08-30',
      }, mockContext);

      const callArgs = mockClient.getBarraDecomposition.mock.calls[0][0];
      expect(callArgs.symbols).toEqual(['000001', '600036']);
      expect(callArgs.start_date).toBe('2026-01-01');
      expect(callArgs.end_date).toBe('2026-08-30');
    });

    it('passes weights when provided', async () => {
      mockClient.getBarraDecomposition.mockResolvedValue({ total_risk: 10 });

      await (tool as any).execute({
        symbols: ['000001'],
        weights: [1.0],
      }, mockContext);

      const callArgs = mockClient.getBarraDecomposition.mock.calls[0][0];
      expect(callArgs.weights).toEqual([1.0]);
    });

    it('maps snake_case and camelCase response fields', async () => {
      mockClient.getBarraDecomposition.mockResolvedValue({
        totalRisk: 15.5,
        factorRisks: [{ factor: 'size', risk: 5 }],
        idiosyncraticRisk: 3.0,
        industryConcentration: 0.4,
        styleExposure: { value: 0.2 },
      });

      const result = await (tool as any).execute({ symbols: ['000001'] }, mockContext);

      expect(result.total_risk).toBe(15.5);
      expect(result.factor_risks).toEqual([{ factor: 'size', risk: 5 }]);
      expect(result.idiosyncratic_risk).toBe(3.0);
      expect(result.industry_concentration).toBe(0.4);
      expect(result.style_exposure).toEqual({ value: 0.2 });
    });

    it('maps snake_case response fields', async () => {
      mockClient.getBarraDecomposition.mockResolvedValue({
        total_risk: 12.0,
        factor_risks: [],
        idiosyncratic_risk: 2.0,
        industry_concentration: 0.1,
        style_exposure: {},
      });

      const result = await (tool as any).execute({ symbols: ['000001'] }, mockContext);

      expect(result.total_risk).toBe(12.0);
    });

    it('defaults to 0/empty when fields missing', async () => {
      mockClient.getBarraDecomposition.mockResolvedValue({});

      const result = await (tool as any).execute({ symbols: ['000001'] }, mockContext);

      expect(result.total_risk).toBe(0);
      expect(result.factor_risks).toEqual([]);
      expect(result.idiosyncratic_risk).toBe(0);
      expect(result.industry_concentration).toBe(0);
      expect(result.style_exposure).toEqual({});
    });
  });

  describe('wrap', () => {
    it('wraps result as success', () => {
      const data = { total_risk: 10, factor_risks: [] };
      const result = (tool as any).wrap(data, mockContext);
      expect(result.success).toBe(true);
      expect(result.data).toBe(data);
    });
  });
});
