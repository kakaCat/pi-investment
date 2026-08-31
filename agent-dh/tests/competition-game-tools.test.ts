/**
 * OpponentBehaviorTool + ManipulationDetectTool 单元测试（M7-1/M7-3）
 *
 * 验证：参数校验 + 执行映射（camelCase→schema 字段、默认值兜底）
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OpponentBehaviorTool } from '../packages/competition/src/tools/OpponentBehaviorTool/OpponentBehaviorTool.js';
import { ManipulationDetectTool } from '../packages/competition/src/tools/ManipulationDetectTool/ManipulationDetectTool.js';
import { RetailPanicIndexTool } from '../packages/competition/src/tools/RetailPanicIndexTool/RetailPanicIndexTool.js';

describe('OpponentBehaviorTool', () => {
  let tool: OpponentBehaviorTool;
  let mockClient: any;
  const mockContext = {} as any;

  beforeEach(() => {
    mockClient = { getOpponentBehavior: vi.fn() };
    tool = new OpponentBehaviorTool(mockClient);
  });

  describe('validate', () => {
    it('accepts empty params (全量分析)', () => {
      const result = (tool as any).validate({});
      expect(result.success).toBe(true);
    });

    it('accepts valid focus', () => {
      expect((tool as any).validate({ focus: 'institution' }).success).toBe(true);
    });

    it('rejects invalid focus', () => {
      const result = (tool as any).validate({ focus: 'bad' });
      expect(result.success).toBe(false);
      expect(result.field).toBe('focus');
    });
  });

  describe('execute', () => {
    it('maps backend camelCase to schema fields with defaults', async () => {
      mockClient.getOpponentBehavior.mockResolvedValue({
        retail: { behavior: 'neutral', net_flow: 2.1e9, emotion_index: 50, common_mistakes: [], degraded: false, description: '观望' },
        institution: { behavior: 'accumulating', net_flow: 6.4e10, target_sectors: ['电子设备'], position_change: 'increasing', degraded: false, description: '建仓' },
        hot_money: { behavior: 'inactive', target_stocks: [], stage: null, activity_level: 'low', estimated: true, description: '平静' },
        market_phase: 'consolidation', risk_appetite: 'medium', opportunity_map: { x: 1 }, degraded: false, timestamp: '2026-09-01T00:00:00',
      });

      const result = await (tool as any).execute({}, mockContext);
      expect(result.market_phase).toBe('consolidation');
      expect(result.institution.behavior).toBe('accumulating');
      expect(result.retail.net_flow).toBe(2.1e9);
      expect(Object.keys(result.opportunity_map)).toHaveLength(1);
      expect(result.degraded).toBe(false);
    });

    it('passes focus param to client', async () => {
      mockClient.getOpponentBehavior.mockResolvedValue({ retail: {}, institution: {}, hot_money: {} });
      await (tool as any).execute({ focus: 'hot_money' }, mockContext);
      expect(mockClient.getOpponentBehavior).toHaveBeenCalledWith({ focus: 'hot_money' });
    });

    it('falls back to defaults when backend returns empty', async () => {
      mockClient.getOpponentBehavior.mockResolvedValue({});
      const result = await (tool as any).execute({}, mockContext);
      expect(result.retail.behavior).toBe('unknown');
      expect(result.retail.degraded).toBe(true);
      expect(result.market_phase).toBe('unknown');
      expect(result.hot_money.estimated).toBe(true);
    });

    it('throws on client error', async () => {
      mockClient.getOpponentBehavior.mockRejectedValue(new Error('boom'));
      await expect((tool as any).execute({}, mockContext)).rejects.toThrow('对手行为分析失败');
    });
  });
});

describe('ManipulationDetectTool', () => {
  let tool: ManipulationDetectTool;
  let mockClient: any;
  const mockContext = {} as any;

  beforeEach(() => {
    mockClient = { detectManipulation: vi.fn() };
    tool = new ManipulationDetectTool(mockClient);
  });

  describe('validate', () => {
    it('rejects non-6-digit symbol', () => {
      expect((tool as any).validate({ symbol: '60051' }).success).toBe(false);
    });

    it('accepts valid symbol', () => {
      expect((tool as any).validate({ symbol: '600519' }).success).toBe(true);
    });
  });

  describe('execute', () => {
    it('maps detection result', async () => {
      mockClient.detectManipulation.mockResolvedValue({
        symbol: '600519', risk_level: 'medium', signals: ['异常放量'],
        volume_anomaly: true, price_pump: true, wash_trade: false, description: '测试',
      });
      const result = await (tool as any).execute({ symbol: '600519', days: 20 }, mockContext);
      expect(result.risk_level).toBe('medium');
      expect(result.volume_anomaly).toBe(true);
      expect(result.signals).toContain('异常放量');
      expect(mockClient.detectManipulation).toHaveBeenCalledWith({ symbol: '600519', days: 20 });
    });

    it('falls back when backend returns empty', async () => {
      mockClient.detectManipulation.mockResolvedValue({});
      const result = await (tool as any).execute({ symbol: '600519' }, mockContext);
      expect(result.risk_level).toBe('low');
      expect(result.symbol).toBe('600519');
    });
  });
});

describe('RetailPanicIndexTool (M7-2)', () => {
  let tool: RetailPanicIndexTool;
  let mockClient: any;
  const mockContext = {} as any;

  beforeEach(() => {
    mockClient = { getRetailPanicIndex: vi.fn() };
    tool = new RetailPanicIndexTool(mockClient);
  });

  describe('validate', () => {
    it('accepts empty params', () => {
      expect((tool as any).validate({}).success).toBe(true);
    });

    it('rejects invalid days', () => {
      const result = (tool as any).validate({ days: 0 });
      expect(result.success).toBe(false);
      expect(result.field).toBe('days');
    });

    it('rejects invalid trade_date', () => {
      expect((tool as any).validate({ trade_date: '2026/08/28' }).success).toBe(false);
    });
  });

  describe('execute', () => {
    it('maps single-day result', async () => {
      mockClient.getRetailPanicIndex.mockResolvedValue({
        success: true, trade_date: '2026-08-28', panic_index: 19.6, level: 'greed', degraded: false,
        dimensions: { retail_flow_score: 46.4, ad_ratio_score: 0, volume_score: 0, fear_greed_score: 5, volatility_score: 46.5 },
        raw: { retail_flow_yi: 2.2, ad_ratio: 2.42, volume_ratio: 0.81, fear_greed_index: 95, volatility: 1.59 },
      });
      const result = await (tool as any).execute({}, mockContext);
      expect(result.panic_index).toBe(19.6);
      expect(result.level).toBe('greed');
      expect(result.dimensions.retail_flow_score).toBe(46.4);
      expect(result.raw.fear_greed_index).toBe(95);
      expect(result.degraded).toBe(false);
      expect(mockClient.getRetailPanicIndex).toHaveBeenCalledWith({});
    });

    it('maps series result', async () => {
      mockClient.getRetailPanicIndex.mockResolvedValue({
        success: true,
        series: [
          { trade_date: '2026-08-28', panic_index: 19.6, level: 'greed', degraded: false, dimensions: {}, raw: {} },
          { trade_date: '2026-08-27', panic_index: 22.0, level: 'greed', degraded: false, dimensions: {}, raw: {} },
        ],
      });
      const result = await (tool as any).execute({ days: 2 }, mockContext);
      expect(result.panic_index).toBe(19.6);
      expect(mockClient.getRetailPanicIndex).toHaveBeenCalledWith({ days: 2 });
    });

    it('falls back when backend returns empty', async () => {
      mockClient.getRetailPanicIndex.mockResolvedValue({});
      const result = await (tool as any).execute({}, mockContext);
      expect(result.panic_index).toBeNull();
      expect(result.degraded).toBe(true);
      expect(result.level).toBe('unknown');
    });

    it('throws on client error', async () => {
      mockClient.getRetailPanicIndex.mockRejectedValue(new Error('boom'));
      await expect((tool as any).execute({}, mockContext)).rejects.toThrow('散户恐慌指数查询失败');
    });
  });
});
