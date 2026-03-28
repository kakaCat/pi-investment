import { describe, expect, test } from "@jest/globals";
import { formatMarketOverviewSection, formatReviewNewsSection } from "./daily-review-service.js";

describe("DailyReviewService helpers", () => {
  test("formats market overview from object-shaped indices", () => {
    const result = formatMarketOverviewSection({
      indices: {
        上证指数: { price: 3200.12, change_pct: 1.23 },
        深证成指: { price: 10100.55, change_pct: -0.45 },
      },
    });

    expect(result).toContain("上证指数：3200.12 （+1.23%）");
    expect(result).toContain("深证成指：10100.55 （-0.45%）");
  });

  test("formats news from data field used by python bridge", () => {
    const result = formatReviewNewsSection({
      data: [
        { title: "公告一", date: "2026-03-21 09:00:00" },
        { title: "公告二", date: "2026-03-21 10:00:00" },
      ],
    });

    expect(result).toContain("公告一");
    expect(result).toContain("公告二");
  });
});
