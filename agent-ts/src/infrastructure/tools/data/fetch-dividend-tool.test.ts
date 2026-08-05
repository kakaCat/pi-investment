import { describe, it, expect } from '@jest/globals';
import { dataFetchDividendTool } from './fetch-dividend-tool.js';
import { getResponseText } from '../testing-utils.js';

describe('dataFetchDividendTool', () => {
  it('should have correct metadata', () => {
    expect(dataFetchDividendTool.name).toBe('data_fetch_dividend');
    expect(dataFetchDividendTool.label).toBe('获取分红数据');
    expect(dataFetchDividendTool.description).toContain('L1 数据管道工具');
  });

  it('should execute single mode successfully', async () => {
    const result = await (dataFetchDividendTool.execute as any)('test-call-id', {
      mode: 'single',
      symbol: '600519.SH',
      years: 5
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    const text = getResponseText(result);
    expect(text).toContain('贵州茅台');
  });

  it('should validate single mode requires symbol', async () => {
    const result = await (dataFetchDividendTool.execute as any)('test-call-id', {
      mode: 'single'
    });

    const text = getResponseText(result);
    expect(text).toContain('single 模式必须提供 symbol 参数');
  });

  it('should execute screen mode successfully', async () => {
    const result = await (dataFetchDividendTool.execute as any)('test-call-id', {
      mode: 'screen',
      min_yield: 3.0,
      limit: 5
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    const text = getResponseText(result);
    expect(text).toContain('高股息股票筛选结果');
  });

  it('should execute calendar mode successfully', async () => {
    const result = await (dataFetchDividendTool.execute as any)('test-call-id', {
      mode: 'calendar',
      start_date: '2026-06-01',
      end_date: '2026-06-30',
      event: 'ex_dividend'
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
    const text = getResponseText(result);
    expect(text).toContain('分红日历');
  });

  it('should validate calendar mode requires dates', async () => {
    const result = await (dataFetchDividendTool.execute as any)('test-call-id', {
      mode: 'calendar'
    });

    const text = getResponseText(result);
    expect(text).toContain('calendar 模式必须提供 start_date 和 end_date 参数');
  });

  it('should handle API errors gracefully', async () => {
    const result = await (dataFetchDividendTool.execute as any)('test-call-id', {
      mode: 'single',
      symbol: 'INVALID'
    });

    const text = getResponseText(result);
    expect(text).toContain('失败');
  });
});
