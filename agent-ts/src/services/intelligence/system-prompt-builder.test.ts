import { describe, test, expect } from '@jest/globals';
import { buildSystemPrompt } from './system-prompt-builder.js';

describe('System Prompt Builder - Channel Differentiation', () => {
  const baseOptions = {
    bootstrap: {
      'IDENTITY.md': '测试身份',
      'SOUL.md': '测试灵魂',
    },
    date: '2026-08-13',
    cwd: '/tmp/test',
    model: 'deepseek-v4-flash',
    mode: 'full' as const,
  };

  test('三渠道输出仅 Channel 段不同——Channel 段之前的内容逐字节相等', () => {
    const feishu = buildSystemPrompt({ ...baseOptions, channel: 'feishu' });
    const tui = buildSystemPrompt({ ...baseOptions, channel: 'tui' });
    const web = buildSystemPrompt({ ...baseOptions, channel: 'web' });

    // 提取 Channel 段之前的内容（Channel 段以 "## Channel" 开头）
    const extractBeforeChannel = (prompt: string): string => {
      const channelIndex = prompt.lastIndexOf('## Channel');
      if (channelIndex === -1) {
        throw new Error('Channel section not found in prompt');
      }
      return prompt.substring(0, channelIndex);
    };

    const feishuBefore = extractBeforeChannel(feishu);
    const tuiBefore = extractBeforeChannel(tui);
    const webBefore = extractBeforeChannel(web);

    // Channel 段之前的内容必须逐字节相等
    expect(feishuBefore).toEqual(tuiBefore);
    expect(feishuBefore).toEqual(webBefore);
  });

  test('feishu 变体含简短约束文案', () => {
    const feishu = buildSystemPrompt({ ...baseOptions, channel: 'feishu' });

    // feishu 必须包含简短、简洁相关的约束
    expect(feishu).toMatch(/concise|简短/i);
    // feishu 必须提到避免表格
    expect(feishu).toMatch(/Avoid.*table|避免.*表格/i);
  });

  test('web 变体含 markdown 相关文案', () => {
    const web = buildSystemPrompt({ ...baseOptions, channel: 'web' });

    // web 必须提到 markdown
    expect(web).toMatch(/markdown/i);
    // web 必须提到格式化或富文本
    expect(web).toMatch(/format|rich|table/i);
  });

  test('tui 变体含完整分析文案', () => {
    const tui = buildSystemPrompt({ ...baseOptions, channel: 'tui' });

    // tui 必须支持完整内容
    expect(tui).toMatch(/complete|full|完整/i);
    // tui 必须提到 markdown 支持
    expect(tui).toMatch(/markdown/i);
  });

  test('Channel 段仅包含格式/语气约束，不含业务规则', () => {
    const feishu = buildSystemPrompt({ ...baseOptions, channel: 'feishu' });
    const tui = buildSystemPrompt({ ...baseOptions, channel: 'tui' });
    const web = buildSystemPrompt({ ...baseOptions, channel: 'web' });

    // 提取 Channel 段内容
    const extractChannelSection = (prompt: string): string => {
      const channelIndex = prompt.lastIndexOf('## Channel');
      if (channelIndex === -1) {
        throw new Error('Channel section not found in prompt');
      }
      return prompt.substring(channelIndex);
    };

    const feishuChannel = extractChannelSection(feishu);
    const tuiChannel = extractChannelSection(tui);
    const webChannel = extractChannelSection(web);

    // Channel 段禁止包含业务词汇
    const businessTerms = ['买', '卖', '止损', '仓位', 'buy', 'sell', 'stop', 'position', 'trade', 'portfolio'];

    for (const term of businessTerms) {
      expect(feishuChannel.toLowerCase()).not.toContain(term.toLowerCase());
      expect(tuiChannel.toLowerCase()).not.toContain(term.toLowerCase());
      expect(webChannel.toLowerCase()).not.toContain(term.toLowerCase());
    }
  });

  test('缺省 channel 等价于 terminal（现状默认不变）', () => {
    const explicit = buildSystemPrompt({ ...baseOptions, channel: 'terminal' });
    const implicit = buildSystemPrompt({ ...baseOptions });
    expect(implicit).toEqual(explicit);
  });

  test('既有渠道 terminal/api 保留原文案（防再次误删）', () => {
    const terminal = buildSystemPrompt({ ...baseOptions, channel: 'terminal' });
    const api = buildSystemPrompt({ ...baseOptions, channel: 'api' });
    expect(terminal).toContain('terminal REPL');
    expect(api).toContain('via API');
    expect(terminal).not.toEqual(api);
  });

  test('Channel 段差异快照：三渠道内容各不相同', () => {
    const feishu = buildSystemPrompt({ ...baseOptions, channel: 'feishu' });
    const tui = buildSystemPrompt({ ...baseOptions, channel: 'tui' });
    const web = buildSystemPrompt({ ...baseOptions, channel: 'web' });

    // 提取 Channel 段
    const extractChannelSection = (prompt: string): string => {
      const channelIndex = prompt.lastIndexOf('## Channel');
      return prompt.substring(channelIndex);
    };

    const feishuChannel = extractChannelSection(feishu);
    const tuiChannel = extractChannelSection(tui);
    const webChannel = extractChannelSection(web);

    // 三个 Channel 段必须各不相同
    expect(feishuChannel).not.toEqual(tuiChannel);
    expect(feishuChannel).not.toEqual(webChannel);
    expect(tuiChannel).not.toEqual(webChannel);
  });
});
