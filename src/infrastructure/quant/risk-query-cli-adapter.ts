import { runQuantCli } from "./quant-cli-client.js";

export interface CheckTradeRiskCliParams {
  symbol: string;
  action: string;
  price: number;
  shares: number;
}

export interface CalculatePositionSizeCliParams {
  symbol: string;
  price: number;
  signal_strength?: number;
}

export interface CalculateStopLossCliParams {
  symbol: string;
  entry_price: number;
  current_price?: number;
  highest_price?: number;
}

export async function checkTradeRiskViaQuantCli(params: CheckTradeRiskCliParams): Promise<string> {
  return runRiskQuery("trade-check", compactParams({ ...params }));
}

export async function calculatePositionSizeViaQuantCli(
  params: CalculatePositionSizeCliParams,
): Promise<string> {
  return runRiskQuery("position-size", compactParams({ ...params }));
}

export async function calculateStopLossViaQuantCli(
  params: CalculateStopLossCliParams,
): Promise<string> {
  return runRiskQuery("stop-loss", compactParams({ ...params }));
}

async function runRiskQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("risk", action, params);
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      symbol: typeof params.symbol === "string" ? params.symbol : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 风控查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
