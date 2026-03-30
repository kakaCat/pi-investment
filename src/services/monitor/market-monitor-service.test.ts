import { describe, expect, test } from "@jest/globals";
import { AlertDeduper, isWithinTradingHours } from "./market-monitor-service.js";

describe("market monitor guards", () => {
  test("allows trading time in weekday 09:30-15:00 Asia/Shanghai", () => {
    expect(isWithinTradingHours(new Date("2026-03-31T01:30:00.000Z"))).toBe(true); // 09:30 CST
    expect(isWithinTradingHours(new Date("2026-03-31T07:00:00.000Z"))).toBe(true); // 15:00 CST
  });

  test("blocks time outside trading window or weekend", () => {
    expect(isWithinTradingHours(new Date("2026-03-31T01:29:00.000Z"))).toBe(false); // 09:29 CST
    expect(isWithinTradingHours(new Date("2026-03-31T07:01:00.000Z"))).toBe(false); // 15:01 CST
    expect(isWithinTradingHours(new Date("2026-04-04T02:00:00.000Z"))).toBe(false); // Saturday
  });
});

describe("AlertDeduper", () => {
  test("deduplicates same symbol within 30 minutes", () => {
    const deduper = new AlertDeduper();
    const t0 = 1000;
    const t20m = t0 + 20 * 60 * 1000;
    const t31m = t0 + 31 * 60 * 1000;

    expect(deduper.shouldNotify("600519", t0)).toBe(true);
    deduper.markSent("600519", t0);

    expect(deduper.shouldNotify("600519", t20m)).toBe(false);
    expect(deduper.shouldNotify("600519", t31m)).toBe(true);
  });
});
