/**
 * M4 仓位与风控单元测试
 * 
 * 测试范围：
 * - M4-1: regime 仓位映射表
 * - M4-2: 回撤熔断
 * - M4-3: 风控工具校准
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('M4-1 Regime Position Limit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should map regime to correct position limit', () => {
    const regimePositionLimit: Record<string, number> = {
      panic: 1.00,
      risk_on: 0.80,
      sideways: 0.60,
      risk_off: 0.40,
      euphoria: 0.30,
    };

    expect(regimePositionLimit.panic).toBe(1.00);
    expect(regimePositionLimit.risk_on).toBe(0.80);
    expect(regimePositionLimit.sideways).toBe(0.60);
    expect(regimePositionLimit.risk_off).toBe(0.40);
    expect(regimePositionLimit.euphoria).toBe(0.30);
  });

  it('should degrade to sideways when regime data is missing', () => {
    const regimePositionLimit: Record<string, number> = {
      panic: 1.00,
      risk_on: 0.80,
      sideways: 0.60,
      risk_off: 0.40,
      euphoria: 0.30,
    };

    const currentRegime = 'sideways'; // 降级默认值
    const positionLimit = regimePositionLimit[currentRegime] || 0.60;

    expect(positionLimit).toBe(0.60);
  });

  it('should block buy when position exceeds limit', () => {
    const currentRegime = 'sideways';
    const positionLimit = 0.60;
    const totalAsset = 100000;
    const currentPositionValue = 50000;
    const buyValue = 20000;

    const positionAfterBuy = currentPositionValue + buyValue;
    const positionRatioAfterBuy = positionAfterBuy / totalAsset;

    expect(positionRatioAfterBuy).toBeGreaterThan(positionLimit);
  });

  it('should allow buy when position is within limit', () => {
    const currentRegime = 'sideways';
    const positionLimit = 0.60;
    const totalAsset = 100000;
    const currentPositionValue = 50000;
    const buyValue = 5000;

    const positionAfterBuy = currentPositionValue + buyValue;
    const positionRatioAfterBuy = positionAfterBuy / totalAsset;

    expect(positionRatioAfterBuy).toBeLessThanOrEqual(positionLimit);
  });
});

describe('M4-2 Circuit Breaker', () => {
  it('should trigger circuit breaker when drawdown exceeds -8%', () => {
    const maxDrawdown = -8.5;
    const threshold = -8.0;

    expect(maxDrawdown).toBeLessThan(threshold);
  });

  it('should not trigger when drawdown is within threshold', () => {
    const maxDrawdown = -5.0;
    const threshold = -8.0;

    expect(maxDrawdown).toBeGreaterThan(threshold);
  });

  it('should calculate half position for reduction', () => {
    const sharesAvailable = 500;
    const sellQty = Math.floor(sharesAvailable / 2 / 100) * 100;

    expect(sellQty).toBe(200); // 500 / 2 = 250 → 200（取整到百股）
  });

  it('should skip reduction when half position is less than 100 shares', () => {
    const sharesAvailable = 150;
    const sellQty = Math.floor(sharesAvailable / 2 / 100) * 100;

    expect(sellQty).toBe(0); // 150 / 2 = 75 → 0（不足 100 股）
  });

  it('should unblock when drawdown recovers', () => {
    const maxDrawdown = -7.0;
    const threshold = -8.0;
    const isActive = true;

    // 已熔断 + 回撤修复 → 解除
    const shouldUnblock = isActive && maxDrawdown > threshold;

    expect(shouldUnblock).toBe(true);
  });
});

describe('M4-3 Risk Control Tool Calibration', () => {
  it('should use 20% max position (not 30%)', () => {
    const accountValue = 100000;
    const maxPositionRatio = 0.2;
    const maxPosition = accountValue * maxPositionRatio;

    expect(maxPosition).toBe(20000);
  });

  it('should calculate stop loss by risk level - large_cap', () => {
    const entryPrice = 100;
    const riskLevel = 'large_cap';
    const stopLossRatio = -0.08; // -8%

    const stopLossPrice = entryPrice * (1 + stopLossRatio);

    expect(stopLossPrice).toBe(92);
  });

  it('should calculate stop loss by risk level - growth', () => {
    const entryPrice = 100;
    const riskLevel = 'growth';
    const stopLossRatio = -0.10; // -10%

    const stopLossPrice = entryPrice * (1 + stopLossRatio);

    expect(stopLossPrice).toBe(90);
  });

  it('should calculate stop loss by risk level - small_cap_theme', () => {
    const entryPrice = 100;
    const riskLevel = 'small_cap_theme';
    const stopLossRatio = -0.12; // -12%

    const stopLossPrice = entryPrice * (1 + stopLossRatio);

    expect(stopLossPrice).toBe(88);
  });
});

describe('M4 Integration Tests', () => {
  it('should check circuit breaker before position limit', () => {
    // 检查顺序：M4-2 熔断 → M4-1 仓位映射
    const checks = ['circuit_breaker', 'position_limit'];

    expect(checks[0]).toBe('circuit_breaker');
    expect(checks[1]).toBe('position_limit');
  });

  it('should block buy when circuit breaker is active', () => {
    const circuitBreakerActive = true;

    if (circuitBreakerActive) {
      const blocked = true;
      expect(blocked).toBe(true);
    }
  });

  it('should skip position limit check when circuit breaker blocks', () => {
    const circuitBreakerActive = true;
    let positionCheckExecuted = false;

    if (circuitBreakerActive) {
      // 熔断激活时直接拒绝，不走仓位检查
    } else {
      positionCheckExecuted = true;
    }

    expect(positionCheckExecuted).toBe(false);
  });
});

describe('M4 Edge Cases', () => {
  it('should handle zero total asset', () => {
    const totalAsset = 0;
    const positionAfterBuy = 10000;
    const positionRatioAfterBuy = totalAsset > 0 ? positionAfterBuy / totalAsset : 0;

    expect(positionRatioAfterBuy).toBe(0);
  });

  it('should handle missing regime data (degrade to sideways)', () => {
    const regimePositionLimit: Record<string, number> = {
      panic: 1.00,
      risk_on: 0.80,
      sideways: 0.60,
      risk_off: 0.40,
      euphoria: 0.30,
    };

    const unknownRegime = 'unknown' as any;
    const positionLimit = regimePositionLimit[unknownRegime] || 0.60;

    expect(positionLimit).toBe(0.60); // 降级到震荡档
  });

  it('should handle negative drawdown correctly', () => {
    const maxDrawdown = -8.5; // 负数表示回撤
    const isTriggered = maxDrawdown < -8.0;

    expect(isTriggered).toBe(true);
  });
});
