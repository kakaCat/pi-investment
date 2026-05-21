import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getFinancialIndicatorsViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getFinancialStatementsViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const getHkFinancialsViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getHkAnalysisViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();

await jest.unstable_mockModule("../../quant/financial-query-cli-adapter.js", () => ({
  getFinancialIndicatorsViaQuantCli: getFinancialIndicatorsViaQuantCliMock,
  getFinancialStatementsViaQuantCli: getFinancialStatementsViaQuantCliMock,
  getHkFinancialsViaQuantCli: getHkFinancialsViaQuantCliMock,
  getHkAnalysisViaQuantCli: getHkAnalysisViaQuantCliMock,
}));

const {
  getFinancialDataTool,
  getFinancialStatementsTool,
  getHkFinancialsTool,
  getHkAnalysisTool,
} = await import("./financial-tools.js");

describe("financial tools", () => {
  beforeEach(() => {
    getFinancialIndicatorsViaQuantCliMock.mockReset();
    getFinancialStatementsViaQuantCliMock.mockReset();
    getHkFinancialsViaQuantCliMock.mockReset();
    getHkAnalysisViaQuantCliMock.mockReset();
  });

  test("routes financial tool execution through quant CLI adapter", async () => {
    getFinancialIndicatorsViaQuantCliMock.mockResolvedValueOnce("{\"quarters\":[]}");
    getFinancialStatementsViaQuantCliMock.mockResolvedValueOnce("{\"income_statement\":{}}");
    getHkFinancialsViaQuantCliMock.mockResolvedValueOnce("{\"market\":\"HK\"}");
    getHkAnalysisViaQuantCliMock.mockResolvedValueOnce("{\"market\":\"HK\"}");

    await (getFinancialDataTool.execute as any)("call-1", { symbol: "600519" });
    await (getFinancialStatementsTool.execute as any)("call-2", {
      symbol: "600519",
      statement: "income",
      recent_n: 4,
    });
    await (getHkFinancialsTool.execute as any)("call-3", { symbol: "9988" });
    await (getHkAnalysisTool.execute as any)("call-4", { symbol: "9988" });

    expect(getFinancialIndicatorsViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getFinancialStatementsViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      statement: "income",
      recent_n: 4,
    });
    expect(getHkFinancialsViaQuantCliMock).toHaveBeenCalledWith("9988");
    expect(getHkAnalysisViaQuantCliMock).toHaveBeenCalledWith("9988");
  });

  test("rejects invalid market symbols before invoking quant CLI", async () => {
    const result = await (getFinancialDataTool.execute as any)("call-1", {
      symbol: "AAPL.US",
    });

    expect(getFinancialIndicatorsViaQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的股票代码");
  });
});

