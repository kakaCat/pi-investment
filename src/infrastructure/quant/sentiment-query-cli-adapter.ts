import { runQuantCli } from "./quant-cli-client.js";

export interface StockFundFlowCliParams {
  symbol: string;
  days?: number;
}

export interface LhbCliParams {
  symbol?: string;
  date?: string;
}

export async function getStockFundFlowViaQuantCli(params: StockFundFlowCliParams): Promise<string> {
  return runSentimentQuery("stock-fund-flow", compactParams({ ...params }));
}

export async function getLhbViaQuantCli(params: LhbCliParams = {}): Promise<string> {
  return runSentimentQuery("lhb", compactParams({ ...params }));
}

export async function getInsiderTradesViaQuantCli(symbol: string): Promise<string> {
  return runSentimentQuery("insider-trades", { symbol });
}

export async function getFundHoldingsViaQuantCli(symbol: string): Promise<string> {
  return runSentimentQuery("fund-holdings", { symbol });
}

export async function getTopFundStocksViaQuantCli(): Promise<string> {
  return runSentimentQuery("top-fund-stocks", {});
}

export async function getTopHoldersViaQuantCli(symbol: string): Promise<string> {
  return runSentimentQuery("top-holders", { symbol });
}

export async function getHolderChangesViaQuantCli(symbol: string): Promise<string> {
  return runSentimentQuery("holder-changes", { symbol });
}

export async function getMarginDataViaQuantCli(symbol: string): Promise<string> {
  return runSentimentQuery("margin-data", { symbol });
}

async function runSentimentQuery(action: string, params: Record<string, unknown>): Promise<string> {
  try {
    const response = await runQuantCli("sentiment", action, compactParams(params));
    return JSON.stringify(response.data ?? {});
  } catch (error) {
    return JSON.stringify({
      error: error instanceof Error ? error.message : String(error),
      symbol: typeof params.symbol === "string" ? params.symbol : undefined,
      _source: "quant_cli",
      _no_operation_performed: true,
      _suggestion: "量化 CLI 情绪/资金/股东查询失败，请检查 quant 后端环境或稍后重试",
    });
  }
}

function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

