import { runQuantCli } from "./quant-cli-client.js";

export interface StockHistoryCliParams {
  symbol: string;
  period?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export async function getStockInfoViaQuantCli(symbol: string): Promise<string> {
  return runStockQuery("info", { symbol });
}

export async function getStockPriceViaQuantCli(symbol: string): Promise<string> {
  return runStockQuery("quote", { symbol });
}

export async function getStockHistoryViaQuantCli(params: StockHistoryCliParams): Promise<string> {
  return runStockQuery("history", compactParams({
    symbol: params.symbol,
    period: params.period,
    start_date: params.start_date,
    end_date: params.end_date,
    limit: params.limit,
  }));
}

export async function getStockNewsViaQuantCli(symbol: string, num?: number): Promise<string> {
  return runStockQuery("news", compactParams({ symbol, num }));
}

export async function getAnnouncementsViaQuantCli(symbol: string): Promise<string> {
  return runStockQuery("announcements", { symbol });
}

async function runStockQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("stock", action, params);
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      symbol: typeof params.symbol === "string" ? params.symbol : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}
