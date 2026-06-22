/**
 * K线数据质量控制单元测试
 */

import { describe, it, expect } from '@jest/globals';
import {
  validateKlineData,
  cleanKlineData,
  calculateQualityMetrics,
  getQualityGrade,
  type ValidationError,
  type ValidationWarning,
} from './kline-data-quality.js';
import type { KlineDataPoint } from './types.js';

describe('K线数据质量控制', () => {
  describe('validateKlineData', () => {
    it('应该通过正常数据的验证', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000, change_pct: 5 },
        { date: '2024-01-02', open: 105, high: 115, low: 100, close: 110, volume: 1200, change_pct: 4.76 },
      ];

      const result = validateKlineData(data);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('应该检测缺失的必填字段', () => {
      const data: any[] = [
        { date: '2024-01-01', open: 100, high: 110, low: 95 }, // 缺少 close 和 volume
      ];

      const result = validateKlineData(data);

      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.errors.some((e: ValidationError) => e.type === 'missing_field' && e.field === 'close')).toBe(true);
      expect(result.errors.some((e: ValidationError) => e.type === 'missing_field' && e.field === 'volume')).toBe(true);
    });

    it('应该安全处理非数组输入（后端异常时不抛 data.forEach is not a function）', () => {
      // 模拟 v2 API 在异常/未就绪时返回对象而非数组
      const badData = { error: 'backend not ready' } as any;

      expect(() => validateKlineData(badData)).not.toThrow();

      const result = validateKlineData(badData);
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
      expect(result.warnings.some((w: ValidationWarning) => w.type === 'gap')).toBe(true);
    });

    it('应该检测无效的价格（<= 0）', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 0, high: 110, low: 95, close: 105, volume: 1000, change_pct: 5 },
        { date: '2024-01-02', open: 100, high: -10, low: 95, close: 105, volume: 1000, change_pct: 0 },
      ];

      const result = validateKlineData(data);

      expect(result.isValid).toBe(false);
      expect(result.errors.some((e: ValidationError) => e.type === 'invalid_value' && e.field === 'open')).toBe(true);
      expect(result.errors.some((e: ValidationError) => e.type === 'invalid_value' && e.field === 'high')).toBe(true);
    });

    it('应该检测数据不一致（高 < 低）', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 95, low: 110, close: 105, volume: 1000, change_pct: 5 },
      ];

      const result = validateKlineData(data);

      expect(result.errors.some((e: ValidationError) => e.type === 'inconsistent_data')).toBe(true);
    });

    it('应该检测重复日期', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000, change_pct: 5 },
        { date: '2024-01-01', open: 105, high: 115, low: 100, close: 110, volume: 1200, change_pct: 4.76 },
      ];

      const result = validateKlineData(data);

      expect(result.isValid).toBe(false);
      expect(result.errors.some((e: ValidationError) => e.type === 'duplicate' && e.field === 'date')).toBe(true);
    });

    it('应该检测价格异常波动', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 100, volume: 1000, change_pct: 0 },
        { date: '2024-01-02', open: 100, high: 150, low: 95, close: 140, volume: 1200, change_pct: 40 }, // 40% 涨幅
      ];

      const result = validateKlineData(data);

      expect(result.warnings.some((w: ValidationWarning) => w.type === 'outlier' && w.field === 'close')).toBe(true);
    });

    it('应该检测成交量异常', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 0, change_pct: 5 },
      ];

      const result = validateKlineData(data);

      expect(result.warnings.some((w: ValidationWarning) => w.type === 'suspicious_value' && w.field === 'volume')).toBe(true);
    });
  });

  describe('cleanKlineData', () => {
    it('应该移除包含无效值的记录', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000, change_pct: 5 },
        { date: '2024-01-02', open: 0, high: 110, low: 95, close: 105, volume: 1000, change_pct: 0 }, // 无效
        { date: '2024-01-03', open: 105, high: 115, low: 100, close: 110, volume: 1200, change_pct: 4.76 },
      ];

      const validation = validateKlineData(data);
      const result = cleanKlineData(data, validation);

      expect(result.cleaned.length).toBe(2);
      expect(result.removed).toBe(1);
    });

    it('应该修复高低价不一致的数据', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 100, high: 95, low: 110, close: 105, volume: 1000, change_pct: 5 }, // high < low
      ];

      const validation = validateKlineData(data);
      const result = cleanKlineData(data, validation);

      expect(result.cleaned.length).toBe(1);
      expect(result.cleaned[0].high).toBe(110); // 应该交换
      expect(result.cleaned[0].low).toBe(95);
      expect(result.fixed).toBe(1);
    });

    it('应该调整不合理的最高价', () => {
      const data: KlineDataPoint[] = [
        { date: '2024-01-01', open: 110, high: 100, low: 95, close: 105, volume: 1000, change_pct: 5 }, // high < open
      ];

      const validation = validateKlineData(data);
      const result = cleanKlineData(data, validation);

      expect(result.cleaned[0].high).toBe(110); // 应该调整为 open
      expect(result.fixed).toBe(1);
    });
  });

  describe('calculateQualityMetrics', () => {
    it('应该计算正确的质量指标', () => {
      const validation = {
        isValid: false,
        errors: [{ type: 'invalid_value' as const, message: 'test', index: 1 }],
        warnings: [],
      };

      const cleaning = {
        cleaned: [
          { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000, change_pct: 5 },
        ],
        removed: 1,
        fixed: 0,
        operations: [],
      };

      const metrics = calculateQualityMetrics(2, validation, cleaning);

      expect(metrics.totalRecords).toBe(2);
      expect(metrics.validRecords).toBe(1);
      expect(metrics.invalidRecords).toBe(1);
      expect(metrics.completeness).toBe(0.5); // 1/2
      expect(metrics.overall).toBeGreaterThan(0);
      expect(metrics.overall).toBeLessThanOrEqual(1);
    });

    it('应该为完美数据返回满分', () => {
      const validation = {
        isValid: true,
        errors: [],
        warnings: [],
      };

      const cleaning = {
        cleaned: [
          { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000, change_pct: 5 },
          { date: '2024-01-02', open: 105, high: 115, low: 100, close: 110, volume: 1200, change_pct: 4.76 },
        ],
        removed: 0,
        fixed: 0,
        operations: [],
      };

      const metrics = calculateQualityMetrics(2, validation, cleaning);

      expect(metrics.completeness).toBe(1);
      expect(metrics.consistency).toBe(1);
      expect(metrics.accuracy).toBe(1);
      expect(metrics.overall).toBe(1);
    });
  });

  describe('getQualityGrade', () => {
    it('应该返回正确的评级', () => {
      expect(getQualityGrade(0.96)).toBe('A+ (优秀)');
      expect(getQualityGrade(0.92)).toBe('A (良好)');
      expect(getQualityGrade(0.85)).toBe('B (合格)');
      expect(getQualityGrade(0.75)).toBe('C (一般)');
      expect(getQualityGrade(0.65)).toBe('D (较差)');
    });
  });
});
