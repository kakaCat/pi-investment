import { afterEach, describe, expect, jest, test } from "@jest/globals";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const getStockListViaQuantCliMock = jest.fn<(market?: string) => Promise<string>>();

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getStockListViaQuantCli: getStockListViaQuantCliMock,
}));

const { StockDBService } = await import("./stock-db-service.js");

describe("StockDBService", () => {
  const tempDirs: string[] = [];

  afterEach(() => {
    for (const dir of tempDirs.splice(0)) {
      rmSync(dir, { recursive: true, force: true });
    }
    getStockListViaQuantCliMock.mockReset();
  });

  test("updates A-share list through quant CLI stock list", async () => {
    const piDir = mkdtempSync(join(tmpdir(), "stock-db-service-"));
    tempDirs.push(piDir);
    getStockListViaQuantCliMock.mockResolvedValueOnce(JSON.stringify({
      stocks: [
        {
          code: "600519",
          name: "贵州茅台",
          industry: "白酒",
          market_cap: 22000,
          pe: 25,
          pb: 8,
        },
      ],
    }));

    const service = StockDBService.getInstance(piDir);
    const count = await service.updateAStocks();

    expect(count).toBe(1);
    expect(getStockListViaQuantCliMock).toHaveBeenCalledWith("A");
    expect(service.getStock("600519")).toMatchObject({
      symbol: "600519",
      name: "贵州茅台",
      market: "A",
    });
    service.close();
  });
});
