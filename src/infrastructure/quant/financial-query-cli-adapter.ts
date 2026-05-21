import { runQuantCli } from "./quant-cli-client.js";

export interface FinancialStatementsCliParams {
  symbol: string;
  statement?: string;
  recent_n?: number;
}

export async function getFinancialIndicatorsViaQuantCli(symbol: string): Promise<string> {
  return runFinancialQuery("indicators", { symbol });
}

export async function getFinancialStatementsViaQuantCli(
  params: FinancialStatementsCliParams,
): Promise<string> {
  return runFinancialQuery("statements", compactParams({ ...params }));
}

export async function getHkFinancialsViaQuantCli(symbol: string): Promise<string> {
  return runFinancialQuery("hk-financials", { symbol });
}

export async function getHkAnalysisViaQuantCli(symbol: string): Promise<string> {
  return runFinancialQuery("hk-analysis", { symbol });
}

async function runFinancialQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("financial", action, compactParams(params));
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      symbol: typeof params.symbol === "string" ? params.symbol : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 财务查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
