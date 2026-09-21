import { describe, it, expect } from 'vitest';
import { serializeSuggestion } from '../src/serializeSuggestion';
import { LearningAnalyzeTool } from '../src/tools/LearningAnalyzeTool/LearningAnalyzeTool';

/**
 * 蒸馏建议序列化回归（2026-09-12，w-adb088f2）
 *
 * 真实缺陷：后端返回对象型 suggestions，工具层 String(s) → 全部变成 "[object Object]"，
 * 该字面量经 daily_distill 灌进 prompt_evolver 的 suggestion.content（2026-09-11 污染实证）。
 * 契约：**任何输入都不得产出裸 "[object Object]"**。
 */

describe('serializeSuggestion', () => {
  it('字符串原样返回', () => {
    expect(serializeSuggestion('样本不足时不下结论')).toBe('样本不足时不下结论');
  });

  it('对象按文本字段提取（不再产出 [object Object]）', () => {
    const s = serializeSuggestion({ suggestion: '提高熔断检查频率', confidence: 0.8 });
    expect(s).toBe('提高熔断检查频率');
    expect(s).not.toContain('[object Object]');
  });

  it('多字段对象取主字段（不再把异质字段拼成一句话）', () => {
    // 2026-09-13 第三批审阅 A9：TEXT_KEYS 优先级里 content 高于 title
    const s = serializeSuggestion({ title: '止损纪律', content: '跌破 -8% 必须止损' });
    expect(s).toBe('跌破 -8% 必须止损');
    expect(s).not.toContain('；');
  });

  it('只有次级字段时仍取该字段（不是空串）', () => {
    expect(serializeSuggestion({ reason: '样本不足', confidence: 0.9 })).toBe('样本不足');
  });

  it('无文本字段的对象回退为 JSON（保留信息而非丢失）', () => {
    const s = serializeSuggestion({ foo: 'bar', n: 1 });
    expect(s).toContain('foo');
    expect(s).toContain('bar');
    expect(s).not.toBe('[object Object]');
  });

  it('null/undefined/空对象 → 空串', () => {
    expect(serializeSuggestion(null)).toBe('');
    expect(serializeSuggestion(undefined)).toBe('');
    expect(serializeSuggestion({})).toBe('');
  });

  it('数组逐项序列化', () => {
    expect(serializeSuggestion(['a', { message: 'b' }])).toBe('a; b');
  });

  it('契约：任意形态输入都不产出裸 [object Object]', () => {
    const shapes: unknown[] = [
      { suggestion: 'x' }, { a: 1 }, { a: { b: 2 } }, ['x', { y: 1 }], 42, true,
      { insight: 'i', extra: { deep: true } },
    ];
    for (const s of shapes) expect(serializeSuggestion(s)).not.toBe('[object Object]');
  });
});

describe('LearningAnalyzeTool 建议通道（驱动真实工具）', () => {
  it('对象型建议被转成可读文本，且空项被过滤', async () => {
    const tool: any = new LearningAnalyzeTool(async () => ({
      patterns: [{ pattern_type: 'opportunity_scan', sample_size: 8 }],
      suggestions: [{ suggestion: '蒸馏样本≥7 才出结论' }, null, '直接给的字符串建议'],
      sample_count: 8,
    }));
    const res: any = await tool.call({ scope: 'recent', focus: 'all', min_samples: 5 });
    expect(res.success).toBe(true);
    const s = res.data.suggestions;
    expect(s.length).toBe(2);
    expect(s).toContain('蒸馏样本≥7 才出结论');
    expect(s).toContain('直接给的字符串建议');
    for (const x of s) expect(x).not.toContain('[object Object]');
  });
});
