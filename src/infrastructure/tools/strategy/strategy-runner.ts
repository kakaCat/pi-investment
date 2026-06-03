/**
 * 策略执行工具 — TypeScript 调用层
 *
 * 调用 quantsys-v2 /api/strategy/run 执行三层流水线，
 * 返回调仓建议供 portfolio_rebalance 使用。
 */
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import type { QuantCliResponse } from "../../adapters/quant/types.js";

export interface StrategyRunRequest {
  market: "A" | "HK";
  sectorData?: {
    momentum: Record<string, number>;
    flow: Record<string, number>;
    strength: Record<string, number>;
  };
  stockData?: Record<string, unknown>[];
  mlPredictions?: Record<
    string,
    {
      xgb_signal: string;
      xgb_confidence: number;
      lgb_signal?: string;
      lgb_confidence?: number;
    }
  >;
  totalCapital?: number;
}

export interface AllocationItem {
  capital: number;
  pct: number;
  sector: string;
}

export interface StrategyRunData {
  market: string;
  sectors: string[];
  sectorScores: Record<string, unknown>[];
  candidates: Record<string, string[]>;
  finalPortfolio: string[];
  allocation: Record<string, AllocationItem>;
  mlPassRate: number;
  warnings: string[];
}

export interface StrategyRunResult {
  success: boolean;
  data?: StrategyRunData;
  error?: string;
}

export interface StrategyStatus {
  success: boolean;
  data?: {
    a_consecutive_counts: Record<string, number>;
    hk_consecutive_counts: Record<string, number>;
  };
}

interface V2StrategyResponse {
  success: boolean;
  data?: {
    market: string;
    sectors: string[];
    sector_scores?: Record<string, unknown>[];
    candidates?: Record<string, string[]>;
    final_portfolio?: string[];
    allocation?: Record<string, AllocationItem>;
    ml_pass_rate?: number;
    warnings?: string[];
  };
  error?: string;
}

interface V2StatusResponse {
  success: boolean;
  data?: {
    a_consecutive_counts: Record<string, number>;
    hk_consecutive_counts: Record<string, number>;
  };
}

export async function runStrategy(
  params: StrategyRunRequest
): Promise<StrategyRunResult> {
  const resp: QuantCliResponse<V2StrategyResponse> = await runQuantV2(
    "strategy.run",
    {
      market: params.market,
      sector_data: params.sectorData,
      stock_data: params.stockData,
      ml_predictions: params.mlPredictions,
      total_capital: params.totalCapital ?? 100000,
    }
  );

  if (!resp.ok || !resp.data) {
    return {
      success: false,
      error: resp.error?.message ?? "Strategy execution failed",
    };
  }

  const d = resp.data;
  if (!d.success) {
    return { success: false, error: d.error ?? "Strategy execution failed" };
  }

  return {
    success: true,
    data: {
      market: d.data?.market ?? "",
      sectors: d.data?.sectors ?? [],
      sectorScores: d.data?.sector_scores ?? [],
      candidates: d.data?.candidates ?? {},
      finalPortfolio: d.data?.final_portfolio ?? [],
      allocation: d.data?.allocation ?? {},
      mlPassRate: d.data?.ml_pass_rate ?? 0,
      warnings: d.data?.warnings ?? [],
    },
  };
}

export async function getStrategyStatus(): Promise<StrategyStatus> {
  const resp: QuantCliResponse<V2StatusResponse> = await runQuantV2(
    "strategy.status",
    {}
  );

  if (!resp.ok || !resp.data?.success) {
    return { success: false };
  }

  return {
    success: true,
    data: {
      a_consecutive_counts: resp.data.data?.a_consecutive_counts ?? {},
      hk_consecutive_counts: resp.data.data?.hk_consecutive_counts ?? {},
    },
  };
}
