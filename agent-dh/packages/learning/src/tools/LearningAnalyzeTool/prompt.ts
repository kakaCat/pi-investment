/**
 * LearningAnalyzeTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface LearningAnalyzeParams {
  scope?: string;
  focus?: 'failures' | 'successes' | 'patterns' | 'all';
  min_samples?: number;
}

export interface LearningAnalyzeResult {
  success: boolean;
  patterns: any[];
  suggestions: string[];
  sample_count: number;
}

export const learningAnalyzePrompt: ToolPrompt<LearningAnalyzeParams, LearningAnalyzeResult> = {
  description: '分析经验库，挖掘成功/失败模式，生成改进建议。适用于：定期分析学习机会、策略表现下滑后寻找原因、识别可优化的决策模式。',
  useCases: ['定期分析学习机会', '寻找策略失败原因', '识别决策优化点'],
  examples: [
    {
      title: '分析最近的失败案例',
      params: { scope: 'recent', focus: 'failures', min_samples: 5 },
      expectedResult: '返回失败模式和改进建议',
    },
  ],
  params: {
    scope: { type: 'string', required: false, description: '分析范围：recent（最近）、all（全部）、strategy:{id}' },
    focus: { type: 'string', required: false, description: '关注点：failures、successes、patterns、all' },
    min_samples: { type: 'number', required: false, description: '最小样本数' },
  },
  output: {
    render: (args, data) => {
      let output = '## 📊 学习分析结果\n\n';
      output += `- **样本数**: ${data.sample_count}\n`;
      output += `- **发现模式**: ${data.patterns.length} 个\n`;
      output += `- **改进建议**: ${data.suggestions.length} 条\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
