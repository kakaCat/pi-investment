import { describe, expect, test } from "@jest/globals";
import { detectMarket, requireAshare } from "./invest-tools.js";

describe("invest tool market guards", () => {
  test("detects A-share and HK symbols", () => {
    expect(detectMarket("600519")).toBe("ashare");
    expect(detectMarket("sz300750")).toBe("ashare");
    expect(detectMarket("9988")).toBe("hk");
    expect(detectMarket("9988.HK")).toBe("hk");
  });

  test("rejects unsupported non-cn markets", () => {
    expect(detectMarket("AAPL.US")).toBe("invalid");
  });

  test("requireAshare returns hk-specific error for hk symbol", () => {
    const result = requireAshare("9988");
    expect(result).not.toBeNull();
    expect(result).toContain("暂不支持港股");
  });
});
