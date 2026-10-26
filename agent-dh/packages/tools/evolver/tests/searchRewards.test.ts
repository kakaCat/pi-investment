import { describe, expect, it, vi } from 'vitest';
import { ValidationGateTool } from '../src/tools/ValidationGateTool/ValidationGateTool';

function experience(tool: string | undefined, action: string | undefined, reward: number, genomeVersion = 'g14') {
  return {
    payload: { genome_context: { genome_version: genomeVersion } },
    content: JSON.stringify({
      action: { tool, args: action ? { action } : {} },
      reward,
    }),
  };
}

function makeGate(items: any[]) {
  const osMemory = { searchMemory: vi.fn().mockResolvedValue({ items }) };
  const tool = new ValidationGateTool({} as any, osMemory as any, 5);
  return { tool: tool as any, osMemory };
}

describe('validation_gate/searchRewards 真实实现', () => {
  it('只统计同 genome 的 portfolio_trade SELL 已实现盈亏', async () => {
    const { tool } = makeGate([
      experience('portfolio_trade', 'SELL', 0.25),
      experience('portfolio_trade', 'SELL', -0.15),
      experience('portfolio_trade', 'BUY', 0.1),
      experience('algo_execute', 'SELL', 0.1),
      experience('model_predict', undefined, 0.5),
      experience(undefined, undefined, 0.3),
      experience('portfolio_trade', 'SELL', 1, 'g13'),
    ]);

    await expect(tool.searchRewards('g14')).resolves.toEqual({ count: 2, avg: 0.05 });
  });

  it('无真实卖出样本时返回零样本', async () => {
    const { tool } = makeGate([experience('portfolio_trade', 'BUY', 0.1)]);
    await expect(tool.searchRewards('g14')).resolves.toEqual({ count: 0, avg: 0 });
  });

  it('记忆查询失败向上抛出，不伪装成零样本', async () => {
    const osMemory = { searchMemory: vi.fn().mockRejectedValue(new Error('memory unavailable')) };
    const tool = new ValidationGateTool({} as any, osMemory as any, 5) as any;
    await expect(tool.searchRewards('g14')).rejects.toThrow('memory unavailable');
  });

  it('忽略非有限奖励和损坏的单条记忆', async () => {
    const { tool } = makeGate([
      experience('portfolio_trade', 'SELL', Number.NaN),
      experience('portfolio_trade', 'SELL', 0.2),
      { payload: { genome_context: { genome_version: 'g14' } }, content: '{broken' },
    ]);
    await expect(tool.searchRewards('g14')).resolves.toEqual({ count: 1, avg: 0.2 });
  });
});
