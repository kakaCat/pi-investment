import { describe, it, expect, vi, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { alignByTradingDate } from '../../../packages/tools/risk/src/tools/RiskMetricsTool/attributionAlignment';
import {
  RiskMetricsTool,
  buildNavCoverage,
  NAV_COVERAGE_UNAVAILABLE_BASIS,
} from '../../../packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool';

// 按交易日对齐的回归测试（2026-09-11，w-f4aa1f6a）
// 关键场景：净值序列缺交易日时，旧的 length-based 对齐会错位一天以上；
// 按日期对齐必须让两侧跨同一段区间，并在基准缺端点时如实降级。
describe('alignByTradingDate', () => {
  const bench = [
    { date: '2026-06-19', trade_date: '2026-06-19', close: 100 },
    { date: '2026-06-22', close: 105 }, // 周一（净值缺这天）
    { date: '2026-06-23', close: 110 },
    { date: '2026-06-24', close: 99 },
  ];

  it('净值缺日：区间收益跨同一段，不错位', () => {
    const nav = ['2026-06-19', '2026-06-23', '2026-06-24'];
    const r = alignByTradingDate(nav, bench, 10);
    expect(r.complete).toBe(true);   // 端点完整
    expect(r.sufficient).toBe(false); // 仅 2 对，样本不足（与 ok 分离，语义不含混）
    expect(r.pairs).toBe(2);
    // 06-19→06-23 = 110/100-1 = 0.10；06-23→06-24 = 99/110-1
    expect(r.benchmarkReturns[0]).toBeCloseTo(0.1, 6);
    expect(r.benchmarkReturns[1]).toBeCloseTo(99 / 110 - 1, 6);
    expect(r.benchmarkReturnPct).toBeCloseTo(-1.0, 6);
  });

  it('基准缺端点：如实降级，不假装可用', () => {
    const nav = ['2026-06-19', '2026-06-23', '2026-06-24'];
    const partial = [bench[0], bench[3]];
    const r = alignByTradingDate(nav, partial, 10);
    expect(r.ok).toBe(false);
    expect(r.complete).toBe(false);   // 端点不完整（与"样本不足"分开断言）
    expect(r.missingDates).toContain('2026-06-23');
    expect(r.note).toContain('基准缺端点');
  });

  it('基准多出交易日不影响配对（只按净值日期对取数）', () => {
    const nav = ['2026-06-23', '2026-06-24'];
    const withExtra = bench.concat([{ date: '2026-06-25', close: 50 }]);
    const r = alignByTradingDate(nav, withExtra, 10);
    expect(r.pairs).toBe(1);
    expect(r.benchmarkReturns).toEqual([99 / 110 - 1]);
  });

  it('端点完整且 >=5 对时 ok=true', () => {
    // 7 个净值交易日 → 6 对，满足 sufficient（>=5）
    const nav = ['2026-06-19', '2026-06-22', '2026-06-23', '2026-06-24',
                 '2026-06-25', '2026-06-26', '2026-06-29'];
    const b2 = bench.concat([
      { date: '2026-06-25', close: 101 }, { date: '2026-06-26', close: 102 },
      { date: '2026-06-29', close: 103 }, { date: '2026-06-30', close: 104 },
    ]);
    const r = alignByTradingDate(nav, b2, 10);
    expect(r.complete).toBe(true);
    expect(r.pairs).toBe(6);
    expect(r.sufficient).toBe(true);
    expect(r.ok).toBe(true);
  });

  it('基准滞后于组合（实证：CSI300 冻结在 08-27）→ stale=true 且区间收益为 null，而不是算出一个错数', () => {
    const nav = ['2026-08-26', '2026-08-27', '2026-08-28'];
    const bStale = [{ date: '2026-08-26', close: 100 }, { date: '2026-08-27', close: 99 }];
    const r = alignByTradingDate(nav, bStale, 10);
    expect(r.stale).toBe(true);
    expect(r.benchmarkLatest).toBe('2026-08-27');
    expect(r.navLatest).toBe('2026-08-28');
    expect(r.benchmarkReturnPct).toBeNull();
    expect(r.note).toContain('基准滞后');
  });

  it('navPoints 只取尾部窗口', () => {
    const nav = ['2026-06-19', '2026-06-22', '2026-06-23', '2026-06-24'];
    const r = alignByTradingDate(nav, bench, 2);
    expect(r.dates).toEqual(['2026-06-23', '2026-06-24']);
  });
});

// ============================================================================
// nav_coverage 交易日口径（2026-10-06 · REQ-261006190953-fc43 卡 E）
//
// 背景：v2 的 `GET /api/simulation/performance`（与 POST /api/risk/metrics）现在返回
// snake_case 的 `data.nav_coverage`，缺口**只按交易日**算——国庆整段与周末不算缺口，
// 日历不可得时 verified=false 且 missing_count=0（不是"全缺失"）。
// 本工具改为**消费**该结果：旧实现按「相邻快照间隔 + 跳过周末」自算，
// 会把国庆 2026-10-01~10-07 误报成缺口，并据此建议补数。
// ============================================================================

const CALENDAR_BASIS =
  '按交易日历逐日核对（来源 calendar_table，共 243 个交易日）：周末与法定节假日不计入缺口';

/** v2 给 nav_coverage 时的样本：09-30 → 10-08 只含两个交易日，国庆整段无缺口 */
const NC_HOLIDAY = {
  verified: true,
  points: 2,
  from: '2026-09-30',
  to: '2026-10-08',
  missing_trading_days: [] as string[],
  missing_count: 0,
  basis: CALENDAR_BASIS,
  trading_day_source: 'trading-calendar',
};

/** v2 给 nav_coverage 且**真缺一个交易日**（2026-09-25 是周五，真交易日） */
const NC_GAP_0925 = {
  ...NC_HOLIDAY,
  points: 3,
  from: '2026-09-24',
  to: '2026-09-30',
  missing_trading_days: ['2026-09-25'],
  missing_count: 1,
};

/** v2 响应体（envelope：data 段含 equity_curve，可选含 nav_coverage） */
const v2Body = (navCoverage: any, dates: string[]) => ({
  success: true,
  data: {
    equity_curve: dates.map((d, i) => ({ date: d, total_value: 100000 + i })),
    ...(navCoverage ? { nav_coverage: navCoverage } : {}),
  },
});

describe('nav_coverage 交易日口径：消费 v2，不再自算', () => {
  it('① v2 给 nav_coverage → 原样透出（含 basis 与 trading_day_source）', () => {
    const out = buildNavCoverage(v2Body({ ...NC_HOLIDAY, calendar_size: 243 }, ['2026-09-30', '2026-10-08']));
    expect(out.verified).toBe(true);
    expect(out.basis).toBe(CALENDAR_BASIS);          // basis 逐字透出，不加不改
    expect(out.trading_day_source).toBe('trading-calendar');
    expect(out.missing_trading_days).toEqual([]);
    expect(out.missing_count).toBe(0);
    expect(out.points).toBe(2);
    expect(out.from).toBe('2026-09-30');
    expect(out.to).toBe('2026-10-08');
    expect((out as any).calendar_size).toBe(243);     // v2 将来新增的字段照样透出
  });

  it('② v2 缺 nav_coverage → verified=false 的「未做交易日校验」，且不产生补跑建议', () => {
    const out = buildNavCoverage(v2Body(null, ['2026-09-30', '2026-10-08']));
    expect(out.verified).toBe(false);
    expect(out.basis).toBe(NAV_COVERAGE_UNAVAILABLE_BASIS);
    expect(out.basis).toContain('未做交易日校验');
    expect(out.trading_day_source).toBe('unavailable');
    // 不得回退 weekday 自算：缺口数未知（0 只是"未校验"，不是"已核对为 0"）
    expect(out.missing_trading_days).toEqual([]);
    expect(out.missing_count).toBe(0);
    expect(out.impact).toContain('未做交易日校验');
    expect(JSON.stringify(out)).not.toMatch(/补跑|建议补|补数据|backfill/i);
  });

  it('③ 序列覆盖 2026-09-30 → 2026-10-08：缺口为 0（国庆整段不算缺口）', () => {
    // 交易日历：09-30（周三）与 10-08（周四）都是交易日；10-01~10-07 为法定休市。
    // 旧实现按「相邻快照间隔 + 跳过周末」会在这段里数出 5 个假缺口
    // （10-01/10-02/10-05/10-06/10-07）并要求补数据——本用例锁死这个误报不再发生。
    const out = buildNavCoverage(v2Body(NC_HOLIDAY, ['2026-09-30', '2026-10-08']));
    expect(out.missing_count).toBe(0);
    expect(out.missing_trading_days).toEqual([]);
    expect(out.missing_trading_days.join(',')).not.toContain('2026-10-0');
    expect(out.impact).toContain('序列连续');
  });

  it('④ 缺 2026-09-25（真交易日）→ 仍报缺口（判据是活的，不是常驻 0）', () => {
    const out = buildNavCoverage(v2Body(NC_GAP_0925, ['2026-09-24', '2026-09-30']));
    expect(out.verified).toBe(true);
    expect(out.missing_count).toBe(1);
    expect(out.missing_trading_days).toEqual(['2026-09-25']);
    expect(out.impact).toContain('缺口');
  });
});

describe('risk_metrics 端到端：nav_coverage 透出与降级（含 window_note 文案）', () => {
  const ctx = {} as any;
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const stubFetch = (impl: any) => vi.stubGlobal('fetch', vi.fn(impl));

  const mkTool = (): any =>
    new RiskMetricsTool({
      getRiskMetrics: vi.fn().mockResolvedValue({
        navPoints: 2,
        returnsSource: 'account_nav',
        annualVolatility: 0.2213,
        maxDrawdown: -0.0512,
      }),
    } as any);

  it('① v2 给 nav_coverage → 工具结果原样透出，window_note 不加降级提示', async () => {
    stubFetch(async () => ({ ok: true, status: 200, json: async () => v2Body(NC_HOLIDAY, ['2026-09-30', '2026-10-08']) }));
    const r: any = await mkTool().execute({ days: 60 }, ctx);
    expect(r.nav_coverage.verified).toBe(true);
    expect(r.nav_coverage.basis).toBe(CALENDAR_BASIS);
    expect(r.nav_coverage.trading_day_source).toBe('trading-calendar');
    expect(r.nav_coverage.missing_count).toBe(0);
    expect(r.window_note).not.toContain('[交易日覆盖率]');
    expect(r.window_note).not.toContain('[缺口]');
  });

  it('② v2 缺 nav_coverage → 工具输出去校验降级文案，且整条结果无补跑建议', async () => {
    stubFetch(async () => ({ ok: true, status: 200, json: async () => v2Body(null, ['2026-09-30', '2026-10-08']) }));
    const r: any = await mkTool().execute({ days: 60 }, ctx);
    expect(r.nav_coverage.verified).toBe(false);
    expect(r.nav_coverage.basis).toBe(NAV_COVERAGE_UNAVAILABLE_BASIS);
    expect(r.window_note).toContain('未做交易日校验');
    expect(r.window_note).not.toContain('[缺口]');
    expect(JSON.stringify(r)).not.toMatch(/补跑|建议补|补数据|backfill/i);
  });

  it('② v2 非 2xx（如 503）→ 同样标未做交易日校验，而不是回退自算', async () => {
    stubFetch(async () => ({ ok: false, status: 503, json: async () => ({}) }));
    const r: any = await mkTool().execute({ days: 60 }, ctx);
    expect(r.nav_coverage.verified).toBe(false);
    expect(r.nav_coverage.basis).toContain('未做交易日校验');
    expect(r.nav_coverage.trading_day_source).toBe('unavailable');
  });

  it('④ 真缺交易日时 window_note 报「个交易日」缺口（措辞不再是工作日）', async () => {
    stubFetch(async () => ({ ok: true, status: 200, json: async () => v2Body(NC_GAP_0925, ['2026-09-24', '2026-09-30']) }));
    const r: any = await mkTool().execute({ days: 60 }, ctx);
    expect(r.nav_coverage.missing_count).toBe(1);
    expect(r.window_note).toContain('[缺口]');
    expect(r.window_note).toContain('1 个交易日');
    expect(r.window_note).not.toContain('个工作日');
  });
});

describe('⑤ 交易日判定的唯一来源（源码锁）', () => {
  // 拼装 needle：本测试文件自身也在被扫描范围内，不能出现该字面量
  const forbiddenCall = 'getUTC' + 'Day';
  const forbiddenCallShort = 'get' + 'Day(';
  const forbiddenField = 'missing_' + 'weekdays';

  it('RiskMetricsTool.ts 与测试文件都不含 UTC 星期自算，也不含旧的 weekday 缺口字段', () => {
    const files = [
      fileURLToPath(new URL('../../../packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts', import.meta.url)),
      fileURLToPath(import.meta.url), // 测试文件自己
    ];
    for (const p of files) {
      const src = readFileSync(p, 'utf-8');
      expect(src.includes(forbiddenCall)).toBe(false);
      expect(src.includes(forbiddenCallShort)).toBe(false);
      expect(src.includes(forbiddenField)).toBe(false);
    }
  });
});
