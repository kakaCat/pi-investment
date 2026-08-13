import { describe, test, expect } from '@jest/globals';
import { allCustomTools } from './index.js';
import { SHARED_BASE_TOOLS, FIN_TOOLS, EVOLUTION_TOOLS, MEMORY_TOOLS } from './groups.js';

describe('Tool Groups', () => {
  test('四组无交集且并集等于 allCustomTools', () => {
    const groups = [SHARED_BASE_TOOLS, FIN_TOOLS, EVOLUTION_TOOLS, MEMORY_TOOLS];
    const names = groups.flatMap(g => g.map((t: any) => t.name));

    // 无重复
    expect(new Set(names).size).toBe(names.length);

    // 全覆盖
    expect(new Set(names)).toEqual(new Set(allCustomTools.map((t: any) => t.name)));
  });

  test('SHARED_BASE_TOOLS 包含任务和计划工具', () => {
    const names = SHARED_BASE_TOOLS.map((t: any) => t.name);
    expect(names).toContain('plan_task');
    expect(names).toContain('task_create');
    expect(names).toContain('scheduler_manage');
    expect(names).toContain('model_switch');
  });

  test('进程控制工具不共享：restart_agent 只在 FIN_TOOLS（2026-08-13 批次6实证：memory agent 自主调用 restart_agent 试图修复环境）', () => {
    const shared = SHARED_BASE_TOOLS.map((t: any) => t.name);
    const fin = FIN_TOOLS.map((t: any) => t.name);
    expect(shared).not.toContain('restart_agent');
    expect(fin).toContain('restart_agent');
  });

  test('MEMORY_TOOLS 包含记忆工具', () => {
    const names = MEMORY_TOOLS.map((t: any) => t.name);
    expect(names).toContain('memory_write');
    expect(names).toContain('memory_search');
  });

  test('EVOLUTION_TOOLS 包含进化工具', () => {
    const names = EVOLUTION_TOOLS.map((t: any) => t.name);
    expect(names).toContain('evolution_run');
    expect(names).toContain('evolution_leaderboard');
    expect(names).toContain('claude_code');
  });

  test('FIN_TOOLS 包含金融数据和交易工具', () => {
    const names = FIN_TOOLS.map((t: any) => t.name);
    expect(names).toContain('data_fetch_quote');
    expect(names).toContain('portfolio_trade');
    expect(names).toContain('pool_manage');
  });

  test('组数量统计正确', () => {
    const totalCount =
      SHARED_BASE_TOOLS.length +
      FIN_TOOLS.length +
      EVOLUTION_TOOLS.length +
      MEMORY_TOOLS.length;

    expect(totalCount).toBe(allCustomTools.length);
  });
});
