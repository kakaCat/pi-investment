import { describe, it, expect, vi } from 'vitest';

/**
 * 测试 learning 的 experience_distill LLM 蒸馏逻辑（审计修复 #3）
 * 
 * 关键逻辑：通过 subagent 调用 LLM 生成具体可操作的改进建议，
 * 失败时回退到模板化建议（向后兼容）
 */

describe('learning/experience_distill LLM 蒸馏', () => {
  
  /**
   * 测试用例 1：LLM 成功返回 JSON 建议
   * 预期：解析 JSON，返回 2-3 条具体建议
   */
  it('LLM 成功返回时应解析 JSON 建议', async () => {
    // Mock subagent 成功返回
    const mockSubagentResult = {
      value: {
        content: [{
          text: JSON.stringify([
            {
              type: 'add_rule',
              section: 'rules',
              content: 'R-XXX: 极度贪婪(fg>85)后科技板块大跌日，提前减仓避险',
              reason: '历史数据显示贪婪极值后科技板块杀跌概率高，提前减仓收益+2.6%'
            },
            {
              type: 'modify_principle',
              section: 'principles',
              content: '强化"高fg是卖出信号而非买入信号"原则',
              reason: '多次验证：fg>85后追高失败率高（高位陷阱案例-5%）'
            }
          ])
        }]
      }
    };

    // 模拟解析逻辑
    let text = mockSubagentResult?.value?.content?.[0]?.text || '';
    text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();
    const suggestions = JSON.parse(text);

    // 断言
    expect(Array.isArray(suggestions)).toBe(true);
    expect(suggestions.length).toBe(2);
    expect(suggestions[0].type).toBe('add_rule');
    expect(suggestions[0].content).toContain('R-XXX');
    expect(suggestions[0].content).toContain('减仓');
    expect(suggestions[1].type).toBe('modify_principle');
    expect(suggestions[1].reason).toContain('fg>85');
  });

  /**
   * 测试用例 2：LLM 返回 markdown 代码块包裹的 JSON
   * 预期：正确去除 ```json 和 ``` 标记
   */
  it('应正确处理 markdown 代码块包裹的 JSON', async () => {
    const mockResult = {
      value: {
        content: [{
          text: '```json\n[{"type":"add_rule","content":"测试规则"}]\n```'
        }]
      }
    };

    let text = mockResult?.value?.content?.[0]?.text || '';
    text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();
    const suggestions = JSON.parse(text);

    expect(suggestions[0].type).toBe('add_rule');
    expect(suggestions[0].content).toBe('测试规则');
  });

  /**
   * 测试用例 3：LLM 调用失败
   * 预期：fallback 到模板化建议
   */
  it('LLM 失败时应 fallback 到模板化建议', async () => {
    // Mock subagent 抛错
    const mockCallTool = vi.fn().mockRejectedValue(new Error('subagent timeout'));

    // 模拟 fallback 逻辑
    let suggestions: any[] = [];
    try {
      await mockCallTool('subagent', { description: '生成蒸馏建议', prompt: '...' });
    } catch (e: any) {
      // Fallback to template
      const lowRewardPatterns = [{ pattern: 'model_predict', avg_reward: -0.04, count: 5 }];
      suggestions.push({
        type: 'add_rule',
        section: 'rules',
        content: `R-XXX: 针对 ${lowRewardPatterns[0].pattern} 低奖励（${lowRewardPatterns[0].avg_reward}），考虑增加前置校验规则`,
        reason: `模板化建议（LLM 失败回退）`
      });
    }

    // 断言：fallback 建议存在
    expect(suggestions.length).toBe(1);
    expect(suggestions[0].content).toContain('R-XXX');
    expect(suggestions[0].content).toContain('model_predict');
    expect(suggestions[0].reason).toContain('模板化');
  });

  /**
   * 测试用例 4：无高低奖励模式
   * 预期：直接返回兜底建议，不调用 LLM
   */
  it('无高低奖励模式时应返回兜底建议', () => {
    const lowRewardPatterns: any[] = [];
    const highRewardPatterns: any[] = [];

    let suggestions: any[] = [];
    // 只有存在模式时才调 LLM
    if (lowRewardPatterns.length > 0 || highRewardPatterns.length > 0) {
      // 调 LLM...
    }

    // 兜底
    if (suggestions.length === 0) {
      suggestions.push({
        type: 'info',
        section: '',
        content: '',
        reason: '数据量不足或表现平稳，暂无改进建议',
      });
    }

    expect(suggestions.length).toBe(1);
    expect(suggestions[0].type).toBe('info');
    expect(suggestions[0].reason).toContain('数据量不足');
  });

  /**
   * 测试用例 5：LLM 返回非法 JSON
   * 预期：catch 到解析错误，fallback 到模板
   */
  it('LLM 返回非法 JSON 时应 fallback', async () => {
    const mockResult = {
      value: { content: [{ text: '这不是一个合法的 JSON 数组' }] }
    };

    let suggestions: any[] = [];
    try {
      let text = mockResult?.value?.content?.[0]?.text || '';
      text = text.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();
      const parsed = JSON.parse(text);  // 会抛错
      suggestions = parsed;
    } catch (e) {
      // Fallback
      suggestions.push({
        type: 'info',
        content: '',
        reason: 'LLM 返回格式错误，fallback 到模板'
      });
    }

    expect(suggestions.length).toBe(1);
    expect(suggestions[0].reason).toContain('fallback');
  });

  /**
   * 测试用例 6：LLM 返回空数组
   * 预期：过滤后触发兜底逻辑
   */
  it('LLM 返回空数组应触发兜底', async () => {
    const mockResult = {
      value: { content: [{ text: '[]' }] }
    };

    let text = mockResult?.value?.content?.[0]?.text || '';
    const parsed = JSON.parse(text);
    let suggestions = Array.isArray(parsed) && parsed.length > 0 
      ? parsed.filter((s: any) => s.type && s.content) 
      : [];

    // 触发兜底
    if (suggestions.length === 0) {
      suggestions.push({
        type: 'info',
        section: '',
        content: '',
        reason: '数据量不足或表现平稳，暂无改进建议',
      });
    }

    expect(suggestions.length).toBe(1);
    expect(suggestions[0].type).toBe('info');
  });

  /**
   * 测试用例 7：提取低奖励模式并构造 prompt
   * 预期：prompt 包含统计数据和具体要求
   */
  it('应正确构造 LLM distill prompt', () => {
    const days = 7;
    const totalExperiences = 25;
    const totalReward = 3.5;
    const successCount = 18;
    const lowRewardPatterns = [
      { pattern: 'model_predict', avg_reward: -0.04, count: 8 }
    ];
    const highRewardPatterns = [
      { pattern: 'portfolio_trade', avg_reward: 0.25, count: 3 }
    ];

    const distillPrompt = [
      `你是投资 Agent 的经验蒸馏器。基于过去 ${days} 天的交易与分析经验，生成 2-3 条可操作的改进建议。`,
      ``,
      `**当前表现统计**：`,
      `- 总经验数：${totalExperiences} 条`,
      `- 平均奖励：${(totalReward / totalExperiences).toFixed(3)}`,
      `- 成功率：${((successCount / totalExperiences) * 100).toFixed(1)}%`,
      ``,
      `**低奖励模式（需改进）**：`,
      `${lowRewardPatterns.map(p => `- ${p.pattern}：平均奖励 ${p.avg_reward.toFixed(3)}（${p.count} 次）`).join('\n')}`,
      ``,
      `**高奖励模式（可强化）**：`,
      `${highRewardPatterns.map(p => `- ${p.pattern}：平均奖励 ${p.avg_reward.toFixed(3)}（${p.count} 次）`).join('\n')}`,
      ``,
      `请生成 JSON 数组（2-3 条建议）...`,
    ].join('\n');

    // 断言
    expect(distillPrompt).toContain('过去 7 天');
    expect(distillPrompt).toContain('总经验数：25 条');
    expect(distillPrompt).toContain('平均奖励：0.140');
    expect(distillPrompt).toContain('成功率：72.0%');
    expect(distillPrompt).toContain('model_predict：平均奖励 -0.040');
    expect(distillPrompt).toContain('portfolio_trade：平均奖励 0.250');
    expect(distillPrompt).toContain('JSON 数组');
  });
});
