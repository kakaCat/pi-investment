import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { runWeeklyEvolution } from './evolution-service.js';
import * as fs from 'fs/promises';
import * as path from 'path';

// 服务直连 127.0.0.1:5001（loadPortfolio/loadTrades 走全局 fetch），
// 单元测试 mock 全局 fetch 为空账户/空交易，消除对生产后端的依赖
const realFetch = globalThis.fetch;

function mockV2Fetch() {
  globalThis.fetch = jest.fn(async (input: any) => {
    const url = String(input);
    const body = url.includes('/api/simulation/accounts/')
      ? { success: true, data: { positions: [] } }
      : {
          success: true,
          data: [{
            trade_date: '2026-07-28',
            action: 'buy',
            symbol: '600519',
            name: '贵州茅台',
            quantity: 100,
            price: 1800,
            amount: 180000,
            notes: '测试交易',
          }],
        };
    return { json: async () => body } as Response;
  }) as any;
}

describe('EvolutionService - runWeeklyEvolution', () => {
  const evolutionDir = path.join(process.cwd(), '.pi-invest', 'evolution');

  beforeEach(() => {
    mockV2Fetch();
  });

  afterEach(async () => {
    globalThis.fetch = realFetch;
    // Clean up test files
    try {
      const files = await fs.readdir(evolutionDir);
      for (const file of files) {
        if (file.startsWith('evolution-')) {
          await fs.unlink(path.join(evolutionDir, file));
        }
      }
    } catch (err) {
      // Directory might not exist, ignore
    }
  });

  it('应该完成完整的进化流程', async () => {
    const result = await runWeeklyEvolution();

    expect(result).toHaveProperty('reportPath');
    expect(result).toHaveProperty('report');
    expect(result.reportPath).toContain('.pi-invest/evolution/evolution-');
  });

  it('应该创建进化目录', async () => {
    await runWeeklyEvolution();

    const exists = await fs.access(evolutionDir).then(() => true).catch(() => false);
    expect(exists).toBe(true);
  });

  it('应该保存带时间戳的报告文件', async () => {
    const result = await runWeeklyEvolution();

    // Verify filename format: evolution-YYYY-MM-DD.md
    const filename = path.basename(result.reportPath);
    expect(filename).toMatch(/^evolution-\d{4}-\d{2}-\d{2}(-\d{6})?\.md$/);  // 现行契约带可选 HHmmss 后缀（防同日覆盖）

    // Verify file exists
    const exists = await fs.access(result.reportPath).then(() => true).catch(() => false);
    expect(exists).toBe(true);
  });

  it('应该生成包含关键信息的报告', async () => {
    const result = await runWeeklyEvolution();

    expect(result.report.period).toBeTruthy();
    expect(result.report.performance).toBeDefined();
    expect(result.report.attribution).toBeDefined();
    expect(result.report.suggestions).toBeDefined();
  });

  it('应该计算性能差距', async () => {
    const result = await runWeeklyEvolution();

    expect(result.report.performance.target).toBe(10);
    expect(typeof result.report.performance.actual).toBe('number');
    expect(typeof result.report.performance.gap).toBe('number');
  });

  it('应该包含归因分析', async () => {
    const result = await runWeeklyEvolution();

    expect(result.report.attribution.rootCause).toBeDefined();
    expect(result.report.attribution.confidence).toBeGreaterThan(0);
    expect(result.report.attribution.reasons).toBeInstanceOf(Array);
    expect(result.report.attribution.recommendation).toBeDefined();
  });

  it('应该生成优化建议', async () => {
    const result = await runWeeklyEvolution();

    expect(result.report.suggestions).toBeInstanceOf(Array);
    expect(result.report.suggestions.length).toBeGreaterThan(0);
  });

  it('应该保存 Markdown 格式的报告', async () => {
    const result = await runWeeklyEvolution();

    const content = await fs.readFile(result.reportPath, 'utf-8');
    expect(content).toContain('# 进化报告');
    expect(content).toContain('## 📈 进化历史趋势');  // 报告结构改版后的固定章节
    expect(content).toContain('## 🔍 数据完整性评估');
  });
});
