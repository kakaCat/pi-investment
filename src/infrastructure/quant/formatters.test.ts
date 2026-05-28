import { formatDividendData } from './formatters.js';
import type { DividendResponse } from './types.js';

describe('formatDividendData', () => {
  it('should format single mode data', () => {
    const data: DividendResponse = {
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      dividends: [
        {
          symbol: '600519.SH',
          name: '贵州茅台',
          fiscal_year: '2024',
          dividend_type: '年度分红',
          cash_dividend: 21.0,
          cash_per_share: 2.10,
          stock_dividend: 0,
          bonus_shares: 0,
          dividend_yield: 3.45,
          payout_ratio: 65.5,
          announce_date: '2025-03-28',
          shareholder_meeting_date: '2025-05-15',
          ex_dividend_date: '2025-06-20',
          record_date: '2025-06-19',
          pay_date: '2025-06-21',
          status: '已实施',
          total_dividend: 2520000000,
          is_implemented: true
        }
      ],
      summary: {
        consecutive_years: 10,
        avg_yield: 3.2,
        total_cash_dividend: 18.50
      }
    };

    const result = formatDividendData(data, 'single');

    expect(result).toContain('贵州茅台');
    expect(result).toContain('连续分红: 10年');
    expect(result).toContain('平均股息率: 3.20%');
    expect(result).toContain('2024年');
  });

  it('should format screen mode data', () => {
    const data: DividendResponse = {
      success: true,
      total: 2,
      stocks: [
        {
          symbol: '600519.SH',
          name: '贵州茅台',
          latest_yield: 3.45,
          consecutive_years: 10,
          avg_payout_ratio: 65.5
        },
        {
          symbol: '601318.SH',
          name: '中国平安',
          latest_yield: 4.20,
          consecutive_years: 8,
          avg_payout_ratio: 55.0
        }
      ]
    };

    const result = formatDividendData(data, 'screen');

    expect(result).toContain('高股息股票筛选结果');
    expect(result).toContain('共 2 只');
    expect(result).toContain('贵州茅台');
    expect(result).toContain('中国平安');
  });

  it('should format calendar mode data', () => {
    const data: DividendResponse = {
      success: true,
      period: '2026-06-01 至 2026-06-30',
      event_type: '除权除息日',
      total: 1,
      events: [
        {
          date: '2026-06-20',
          symbol: '600519.SH',
          name: '贵州茅台',
          cash_per_share: 2.10,
          dividend_yield: 3.45
        }
      ]
    };

    const result = formatDividendData(data, 'calendar');

    expect(result).toContain('分红日历');
    expect(result).toContain('除权除息日');
    expect(result).toContain('2026-06-20');
    expect(result).toContain('贵州茅台');
  });

  it('should handle error response', () => {
    const data: DividendResponse = {
      success: false,
      error: '股票代码不存在'
    };

    const result = formatDividendData(data, 'single');

    expect(result).toContain('查询失败');
    expect(result).toContain('股票代码不存在');
  });
});
