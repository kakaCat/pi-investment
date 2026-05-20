import { runQuantCli } from "./quant-cli-client.js";

export async function analyzeTechnicalViaQuantCli(symbol: string): Promise<string> {
  return runAnalysisQuery("technical", { symbol });
}

export async function analyzePriceActionViaQuantCli(symbol: string, period?: number): Promise<string> {
  return runAnalysisQuery("price-action", compactParams({ symbol, period }));
}

export async function analyzeCandlestickViaQuantCli(symbol: string): Promise<string> {
  return runAnalysisQuery("candlestick", { symbol });
}

export async function getBuyRangeViaQuantCli(symbol: string, currentPrice?: number): Promise<string> {
  return runAnalysisQuery("buy-range", compactParams({ symbol, current_price: currentPrice }));
}

export async function getValuationViaQuantCli(symbol: string): Promise<string> {
  return runAnalysisQuery("valuation", { symbol });
}

export async function getPePercentileViaQuantCli(symbol: string, years?: number): Promise<string> {
  return runAnalysisQuery("pe-percentile", compactParams({ symbol, years }));
}

export async function getQualityScoreViaQuantCli(symbol: string): Promise<string> {
  return runAnalysisQuery("quality", { symbol });
}

export async function getExitPlanViaQuantCli(
  symbol: string,
  buyPrice: number,
  shares?: number,
): Promise<string> {
  return runAnalysisQuery("exit-plan", compactParams({
    symbol,
    buy_price: buyPrice,
    shares,
  }));
}

export async function comparePeersViaQuantCli(symbol: string): Promise<string> {
  return runAnalysisQuery("peers", { symbol });
}

async function runAnalysisQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("analysis", action, params);
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      symbol: typeof params.symbol === "string" ? params.symbol : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 分析查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
