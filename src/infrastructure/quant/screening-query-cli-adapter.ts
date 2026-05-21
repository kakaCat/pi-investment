import { runQuantCli } from "./quant-cli-client.js";

export interface ScreenStocksBySectorCliParams {
  sector: string;
  min_roe?: number;
  max_pe?: number;
  limit?: number;
}

export interface ScreenStocksQualityCliParams {
  sector: string;
  min_score?: number;
  max_pe?: number;
  limit?: number;
}

export async function screenStocksBySectorViaQuantCli(
  params: ScreenStocksBySectorCliParams,
): Promise<string> {
  return runScreeningQuery("sector", compactParams({ ...params }));
}

export async function screenStocksQualityViaQuantCli(
  params: ScreenStocksQualityCliParams,
): Promise<string> {
  return runScreeningQuery("quality", compactParams({ ...params }));
}

async function runScreeningQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("screening", action, params);
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      sector: typeof params.sector === "string" ? params.sector : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 选股查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
