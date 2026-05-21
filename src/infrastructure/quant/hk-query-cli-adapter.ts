import { runQuantCli } from "./quant-cli-client.js";

export async function getHkMarketOverviewViaQuantCli(): Promise<string> {
  return runHkQuery("market-overview", {});
}

export async function getHkSouthFlowViaQuantCli(): Promise<string> {
  return runHkQuery("south-flow", {});
}

export async function getHkTechnicalViaQuantCli(symbol: string): Promise<string> {
  return runHkQuery("technical", { symbol });
}

export async function getHkHotRankViaQuantCli(): Promise<string> {
  return runHkQuery("hot-rank", {});
}

async function runHkQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("hk", action, compactParams(params));
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      symbol: typeof params.symbol === "string" ? params.symbol : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 港股查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
