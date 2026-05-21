import { runQuantCli } from "./quant-cli-client.js";

export interface IndexHistoryCliParams {
  symbol: string;
  start_date: string;
  end_date: string;
}

export async function getMarketOverviewViaQuantCli(): Promise<string> {
  return runMarketQuery("overview", {});
}

export async function getIndexHistoryViaQuantCli(params: IndexHistoryCliParams): Promise<string> {
  return runMarketQuery("index-history", { ...params });
}

export async function getSectorListViaQuantCli(): Promise<string> {
  return runMarketQuery("sectors", {});
}

export async function getConceptStocksViaQuantCli(concept: string): Promise<string> {
  return runMarketQuery("concept-stocks", { concept });
}

export async function getConceptListViaQuantCli(): Promise<string> {
  return runMarketQuery("concepts", {});
}

export async function getMacroDataViaQuantCli(indicators?: string[]): Promise<string> {
  return runMarketQuery("macro", compactParams({ indicators }));
}

export async function getNorthFlowViaQuantCli(): Promise<string> {
  return runMarketQuery("north-flow", {});
}

export async function getSectorFundFlowViaQuantCli(): Promise<string> {
  return runMarketQuery("sector-flow", {});
}

export async function getMarketMarginViaQuantCli(): Promise<string> {
  return runMarketQuery("margin", {});
}

export async function getMarketNewsViaQuantCli(num?: number): Promise<string> {
  return runMarketQuery("news", compactParams({ num }));
}

export async function getHotStocksViaQuantCli(market?: string): Promise<string> {
  return runMarketQuery("hot-stocks", compactParams({ market }));
}

async function runMarketQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("market", action, params);
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 市场查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => {
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      return value !== undefined && value !== null && value !== "";
    })
  );
}
