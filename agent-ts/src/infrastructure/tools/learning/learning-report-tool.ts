/**
 * Learning Report Tool - 学习报告工具
 *
 * 触发Agent学习，查看学习成果和优化建议
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface LearningParams {
  action: 'analyze' | 'optimize' | 'report';
  domain?: string;
  parameter?: string;
}

interface LearningResult {
  analyze_result?: {
    domain?: string;
    sample_size?: number;
    success_rate?: number;
    lessons_learned?: Array<{
      rule?: string;
      reason?: string;
      confidence?: number;
      sample_size?: number;
    }>;
    failed_patterns?: Array<{
      pattern?: string;
      failure_rate?: number;
      lesson?: string;
    }>;
    optimizations?: Array<{
      parameter?: string;
      old_value?: number;
      new_value?: number;
      improvement?: string;
    }>;
  };
  optimize_result?: {
    parameter?: string;
    current_value?: number;
    optimal_value?: number;
    improvement?: any;
    confidence?: number;
    sample_size?: number;
  };
  report?: {
    total_decisions?: number;
    evaluated_decisions?: number;
    overall_success_rate?: number;
    by_domain?: Record<string, any>;
    knowledge_growth?: any;
  };
}

export const learningReportTool: ToolDefinition = {
  name: "learning_report",
  description: `触发Agent学习，查看学习成果和优化建议

用途：
- 从历史决策中学习规律
- 分析成功和失败的模式
- 获取参数优化建议
- 查看学习进展报告

何时使用：
- 积累了一定数量的决策后（建议>=10条）
- 想了解哪些策略有效、哪些无效
- 需要优化参数（如min_roe阈值）
- 查看知识库的增长情况

返回内容：
- 成功规律（如"白酒股ROE>18%胜率85%"）
- 失败模式（如"避免在distribution阶段建仓"）
- 参数优化建议（如"min_roe: 15→18"）
- 学习报告（总体成功率、知识增长等）`,

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('analyze'),
      Type.Literal('optimize'),
      Type.Literal('report')
    ], {
      description: "操作类型：analyze=学习分析, optimize=参数优化, report=学习报告"
    }),
    domain: Type.Optional(Type.String({
      description: "学习领域（如sector:白酒）"
    })),
    parameter: Type.Optional(Type.String({
      description: "要优化的参数名（action=optimize时需要）"
    }))
  }),

  execute: async (_toolCallId: string, params: LearningParams) => {
    try {
      const { action, domain, parameter } = params;

      let result: LearningResult = {};

      if (action === 'analyze') {
        // 学习分析
        const apiResult = await runQuantV2(
          '/api/learning/analyze',
          'POST',
          { domain }
        );

        if (!apiResult.ok) {
          throw new Error("学习分析失败");
        }

        result.analyze_result = (apiResult as any).data || {};

      } else if (action === 'optimize') {
        // 参数优化
        if (!domain || !parameter) {
          throw new Error("参数优化需要提供domain和parameter");
        }

        const apiResult = await runQuantV2(
          '/api/learning/optimize',
          'POST',
          { domain, parameter }
        );

        if (!apiResult.ok) {
          throw new Error("参数优化失败");
        }

        result.optimize_result = (apiResult as any).data || {};

      } else {
        // 学习报告
        const apiResult = await runQuantV2(
          '/api/learning/report',
          'GET'
        );

        if (!apiResult.ok) {
          throw new Error("获取学习报告失败");
        }

        result.report = (apiResult as any).data || {};
      }

      // 格式化报告
      const report = formatLearningReport(result, action);

      return {
        content: [{
          type: "text" as const,
          text: report
        }],
        details: result
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 学习操作失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化学习报告
 */
function formatLearningReport(result: LearningResult, action: string): string {
  const lines: string[] = [];

  if (action === 'analyze') {
    // 学习分析
    const data = result.analyze_result || {};

    lines.push('# 🎓 学习分析报告\n');

    if (data.domain) {
      lines.push(`**学习领域**: ${data.domain}`);
    }

    lines.push(`**样本数量**: ${data.sample_size || 0}条决策`);
    lines.push(`**总体成功率**: ${((data.success_rate || 0) * 100).toFixed(1)}%\n`);

    // 成功规律
    const lessons = data.lessons_learned || [];
    if (lessons.length > 0) {
      lines.push('## ✅ 发现的成功规律\n');
      for (const lesson of lessons) {
        lines.push(`### ${lesson.rule}\n`);
        lines.push(`**原因**: ${lesson.reason}`);
        lines.push(`**置信度**: ${((lesson.confidence || 0) * 100).toFixed(0)}%`);
        lines.push(`**样本**: ${lesson.sample_size}条\n`);
      }
    } else {
      lines.push('## ✅ 成功规律\n暂未发现明显规律（样本量可能不足）\n');
    }

    // 失败模式
    const failures = data.failed_patterns || [];
    if (failures.length > 0) {
      lines.push('## ❌ 发现的失败模式\n');
      for (const failure of failures) {
        lines.push(`### ${failure.pattern}\n`);
        lines.push(`**失败率**: ${((failure.failure_rate || 0) * 100).toFixed(1)}%`);
        lines.push(`**经验教训**: ${failure.lesson}\n`);
      }
    } else {
      lines.push('## ❌ 失败模式\n暂未发现明显失败模式\n');
    }

    // 优化建议
    const opts = data.optimizations || [];
    if (opts.length > 0) {
      lines.push('## 🔧 参数优化建议\n');
      for (const opt of opts) {
        lines.push(`### ${opt.parameter}\n`);
        lines.push(`**当前值**: ${opt.old_value}`);
        lines.push(`**建议值**: ${opt.new_value}`);
        lines.push(`**预期改进**: ${opt.improvement}\n`);
      }
    }

  } else if (action === 'optimize') {
    // 参数优化
    const data = result.optimize_result || {};

    lines.push('# 🔧 参数优化报告\n');

    lines.push(`**参数**: ${data.parameter}`);
    lines.push(`**当前值**: ${data.current_value}`);
    lines.push(`**最优值**: ${data.optimal_value}`);
    lines.push(`**样本量**: ${data.sample_size}条\n`);

    lines.push('## 预期改进\n');
    const improvement = data.improvement || {};
    for (const [key, value] of Object.entries(improvement)) {
      lines.push(`- ${key}: ${value}`);
    }

    lines.push(`\n**置信度**: ${((data.confidence || 0) * 100).toFixed(0)}%`);

  } else {
    // 学习报告
    const data = result.report || {};

    lines.push('# 📊 学习系统报告\n');

    lines.push(`**总决策数**: ${data.total_decisions || 0}条`);
    lines.push(`**已评估**: ${data.evaluated_decisions || 0}条`);
    lines.push(`**总体成功率**: ${((data.overall_success_rate || 0) * 100).toFixed(1)}%\n`);

    // 按领域统计
    const by_domain = data.by_domain || {};
    if (Object.keys(by_domain).length > 0) {
      lines.push('## 各领域表现\n');
      for (const [domain, stats] of Object.entries(by_domain)) {
        const s = stats as any;
        lines.push(`### ${domain}\n`);
        lines.push(`- 决策数: ${s.decisions}条`);
        lines.push(`- 成功率: ${(s.success_rate * 100).toFixed(1)}%`);

        if (s.top_lessons && s.top_lessons.length > 0) {
          lines.push(`- 关键规律: ${s.top_lessons[0].rule}`);
        }

        lines.push('');
      }
    }

    // 知识增长
    const growth = data.knowledge_growth || {};
    lines.push('## 📈 知识库增长\n');
    lines.push(`- 最近7天: 新增${growth.last_week || 0}条知识`);
    lines.push(`- 最近30天: 新增${growth.last_month || 0}条知识`);
  }

  return lines.join('\n');
}
