import { describe, it, expect } from '@jest/globals';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator.js';
import type { ToolEfficiency } from '../../types/evolution.js';

describe('Compensator - determineOptimizerStrategy', () => {
  it('应该为小差距返回微调策略', () => {
    const strategy = determineOptimizerStrategy(1.5);

    expect(strategy.level).toBe('minor');
    expect(strategy.actions).toContain('adjust_parameters');
    expect(strategy.actions).toContain('update_experience');
  });

  it('应该为中差距返回中度调整策略', () => {
    const strategy = determineOptimizerStrategy(3);

    expect(strategy.level).toBe('moderate');
    expect(strategy.actions).toContain('add_tools');
    expect(strategy.actions).toContain('remove_tools');
  });

  it('应该为大差距返回重大调整策略', () => {
    const strategy = determineOptimizerStrategy(6);

    expect(strategy.level).toBe('major');
    expect(strategy.actions).toContain('redesign_strategy');
    expect(strategy.actions).toContain('update_algorithms');
  });
});

describe('Compensator - generateOptimizationSuggestions', () => {
  it('应该建议移除低效工具', () => {
    const toolStats: ToolEfficiency[] = [
      {
        tool_name: 'get_stock_news',
        call_count: 45,
        decisions_after_call: 40,
        win_rate: 0.48,
        avg_return: -0.008,
        avg_tokens: 500,
        cost_per_call: 0.005,
        roi: -1.6,
        rating: 1
      }
    ];

    const suggestions = generateOptimizationSuggestions({
      level: 'moderate',
      toolStats,
      weaknesses: []
    });

    const removeSuggestion = suggestions.find(s => s.type === 'remove_tool');
    expect(removeSuggestion).toBeDefined();
    expect(removeSuggestion!.description).toContain('get_stock_news');
    expect(removeSuggestion!.priority).toBe('high');
  });

  it('应该建议新增工具解决弱点', () => {
    const suggestions = generateOptimizationSuggestions({
      level: 'moderate',
      toolStats: [],
      weaknesses: ['风控能力']
    });

    const addSuggestion = suggestions.find(s =>
      s.type === 'add_tool' && s.description.includes('止损')
    );
    expect(addSuggestion).toBeDefined();
    expect(addSuggestion!.priority).toBe('high');
  });

  it('应该建议更新经验库', () => {
    const suggestions = generateOptimizationSuggestions({
      level: 'minor',
      toolStats: [],
      weaknesses: [],
      newPatterns: [
        { pattern: '追涨买入', winRate: 0.25, avgReturn: -0.035 }
      ]
    });

    const expSuggestion = suggestions.find(s => s.type === 'update_experience');
    expect(expSuggestion).toBeDefined();
  });
});
