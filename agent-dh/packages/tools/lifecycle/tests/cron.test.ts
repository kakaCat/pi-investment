import { describe, it, expect } from 'vitest';
import { parseCron, matchesCron, nextRunAfter } from '../src/cron.js';

describe('cron 解析器', () => {
  it('解析简单表达式', () => {
    const c = parseCron('0 30 11 * * 0'); // meta-learning-weekly：周日 11:30
    expect(c.minute.has(30)).toBe(true);
    expect(c.hour.has(11)).toBe(true);
    expect(c.dow.has(0)).toBe(true);
    expect(c.dowRestricted).toBe(true);
    expect(c.domRestricted).toBe(false);
  });

  it('匹配周日 11:30', () => {
    const c = parseCron('0 30 11 * * 0');
    // 2026-09-06 是周日
    const sun1130 = new Date(2026, 8, 6, 11, 30, 0);
    expect(matchesCron(c, sun1130)).toBe(true);
    // 周一 11:30 不匹配
    const mon1130 = new Date(2026, 8, 7, 11, 30, 0);
    expect(matchesCron(c, mon1130)).toBe(false);
  });

  it('工作日范围 1-5', () => {
    const c = parseCron('0 25 9 * * 1-5'); // pre-market-routine：工作日 9:25
    const wed = new Date(2026, 8, 2, 9, 25, 0); // 周三
    const sat = new Date(2026, 8, 5, 9, 25, 0); // 周六
    expect(matchesCron(c, wed)).toBe(true);
    expect(matchesCron(c, sat)).toBe(false);
  });

  it('DOW 7 也是周日', () => {
    const c = parseCron('0 0 12 * * 7'); // weekly-report-m6：周日 12:00
    const sun = new Date(2026, 8, 6, 12, 0, 0);
    expect(matchesCron(c, sun)).toBe(true);
  });

  it('每日任务', () => {
    const c = parseCron('0 0 21 * * *'); // 每天 21:00
    expect(matchesCron(c, new Date(2026, 8, 1, 21, 0, 0))).toBe(true);
    expect(matchesCron(c, new Date(2026, 8, 1, 21, 1, 0))).toBe(false);
  });

  it('nextRunAfter 找下次触发', () => {
    const c = parseCron('0 35 9 * * 1-5'); // 工作日 9:35
    // 周二 2026-09-01 18:00 → 下次是周三 9/2 9:35
    const from = new Date(2026, 8, 1, 18, 0, 0);
    const next = nextRunAfter(c, from);
    expect(next).not.toBeNull();
    expect(next!.getFullYear()).toBe(2026);
    expect(next!.getMonth()).toBe(8);
    expect(next!.getDate()).toBe(2);
    expect(next!.getHours()).toBe(9);
    expect(next!.getMinutes()).toBe(35);
  });

  it('nextRunAfter 当天未来时刻', () => {
    const c = parseCron('0 30 11 * * 0');
    // 周日 9/6 08:00 → 当天 11:30
    const from = new Date(2026, 8, 6, 8, 0, 0);
    const next = nextRunAfter(c, from);
    expect(next!.getDate()).toBe(6);
    expect(next!.getHours()).toBe(11);
  });

  it('非法表达式抛错', () => {
    expect(() => parseCron('0 30 11')).toThrow();
    expect(() => parseCron('99 * * * *')).toThrow();
    expect(() => parseCron('*/0 * * * *')).toThrow();
  });

  it('逗号列表', () => {
    const c = parseCron('0 0 9,15 * * *');
    expect(matchesCron(c, new Date(2026, 8, 1, 9, 0, 0))).toBe(true);
    expect(matchesCron(c, new Date(2026, 8, 1, 15, 0, 0))).toBe(true);
    expect(matchesCron(c, new Date(2026, 8, 1, 12, 0, 0))).toBe(false);
  });

  it('步长 */n', () => {
    const c = parseCron('*/15 * * * *');
    expect(matchesCron(c, new Date(2026, 8, 1, 10, 0, 0))).toBe(true);
    expect(matchesCron(c, new Date(2026, 8, 1, 10, 15, 0))).toBe(true);
    expect(matchesCron(c, new Date(2026, 8, 1, 10, 7, 0))).toBe(false);
  });
});
