import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getBatchStockPricesViaQuantCliMock = jest.fn<(symbols: string[]) => Promise<string>>();
const getStockPriceViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getBatchStockPricesViaQuantCli: getBatchStockPricesViaQuantCliMock,
  getStockPriceViaQuantCli: getStockPriceViaQuantCliMock,
}));

const { PriceService } = await import("./price-service.js");

describe("PriceService", () => {
  beforeEach(() => {
    getBatchStockPricesViaQuantCliMock.mockReset();
    getStockPriceViaQuantCliMock.mockReset();
  });

  test("fetches missing batch prices through quant CLI", async () => {
    const db = { getKlines: jest.fn(() => []) };
    getBatchStockPricesViaQuantCliMock.mockResolvedValueOnce(JSON.stringify({
      prices: {
        "600519": 100.5,
        "000001": 12.3,
      },
    }));

    const prices = await new PriceService(db as any).getBatchPrices(["600519", "000001"]);

    expect(getBatchStockPricesViaQuantCliMock).toHaveBeenCalledWith(["600519", "000001"]);
    expect(prices.get("600519")).toBe(100.5);
    expect(prices.get("000001")).toBe(12.3);
  });

  test("falls back to single quant CLI quote when batch quote fails", async () => {
    const db = { getKlines: jest.fn(() => []) };
    getBatchStockPricesViaQuantCliMock.mockRejectedValueOnce(new Error("offline"));
    getStockPriceViaQuantCliMock.mockResolvedValueOnce(JSON.stringify({ price: 100.5 }));

    const prices = await new PriceService(db as any).getBatchPrices(["600519"]);

    expect(getStockPriceViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(prices.get("600519")).toBe(100.5);
  });
});
