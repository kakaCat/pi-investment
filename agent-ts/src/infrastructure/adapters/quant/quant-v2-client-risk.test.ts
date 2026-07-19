/**
 * Risk Metrics 响应归一化测试
 *
 * 后端 /api/risk/metrics 返回 camelCase（sharpeRatio, maxDrawdown...），
 * 而 RiskMetrics 接口为 snake_case —— 历史 bug：工具直接读 snake_case
 * 字段导致 undefined.toFixed 崩溃。
 */
import { describe, expect, test } from "@jest/globals";
import { normalizeRiskMetrics } from "./quant-v2-client.js";

const apiResponse = {
  annualReturn: 0.7297,
  annualVolatility: 0.2006,
  calmarRatio: 36.48,
  cumulativeReturn: 0.0264,
  cvar95: -0.02,
  maxDrawdown: -0.02,
  sharpeRatio: 1.25,
  sortinoRatio: -13.12,
  var95: -0.01725,
  alpha: 0.03,
  beta: 1.1,
};

describe("normalizeRiskMetrics", () => {
  test("camelCase API 响应映射为 snake_case 接口", () => {
    const m = normalizeRiskMetrics(apiResponse);

    expect(m.sharpe_ratio).toBe(1.25);
    expect(m.sortino_ratio).toBe(-13.12);
    expect(m.calmar_ratio).toBe(36.48);
    expect(m.max_drawdown).toBe(-0.02);
    expect(m.var_95).toBe(-0.01725);
    expect(m.cvar_95).toBe(-0.02);
    expect(m.annual_return).toBe(0.7297);
    expect(m.annual_volatility).toBe(0.2006);
    expect(m.alpha).toBe(0.03);
    expect(m.beta).toBe(1.1);
  });

  test("snake_case 响应（旧后端）保持兼容", () => {
    const m = normalizeRiskMetrics({
      sharpe_ratio: 0.9,
      sortino_ratio: 0.8,
      calmar_ratio: 0.7,
      max_drawdown: -0.1,
      var_95: -0.03,
      cvar_95: -0.04,
      annual_return: 0.2,
      annual_volatility: 0.15,
    });

    expect(m.sharpe_ratio).toBe(0.9);
    expect(m.max_drawdown).toBe(-0.1);
    expect(m.alpha).toBeUndefined();
  });

  test("缺失字段不产生 NaN", () => {
    const m = normalizeRiskMetrics({});
    expect(Number.isNaN(m.sharpe_ratio)).toBe(false);
  });
});
