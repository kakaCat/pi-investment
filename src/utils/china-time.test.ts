import { describe, expect, test } from "@jest/globals";
import { chinaDate, chinaDateTime, chinaTime, chinaWeekday } from "./china-time.js";

describe("china-time", () => {
  test("uses Asia/Shanghai calendar date instead of UTC date boundary", () => {
    const date = new Date("2026-03-20T16:30:00.000Z");
    expect(chinaDate(date)).toBe("2026-03-21");
    expect(chinaTime(date)).toBe("00:30:00");
    expect(chinaDateTime(date, false)).toBe("2026-03-21 00:30");
  });

  test("returns weekday in China timezone", () => {
    const date = new Date("2026-03-20T16:30:00.000Z");
    expect(chinaWeekday(date)).toBe(6);
  });
});
