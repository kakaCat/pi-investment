/**
 * Knowledge Query Tool - 知识查询工具
 *
 * 查询Agent积累的经验知识，用于指导决策
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface KnowledgeQueryParams {
  domain?: string;
  action?: 'query' | 'apply' | 'summary';
  context?: any;
}

interface KnowledgeResult {
  knowledge_list?: Array<{
    id?: string;
    domain?: string;
    knowledge_type?: string;
    content?: any;
    confidence?: number;
    validation_count?: number;
    success_count?: number;
  }>;
  recommendations?: Array<{
    knowledge_id?: string;
    rule?: string;
    confidence?: number;
    suggestions?: string[];
  }>;
  summary?: {
    total_knowledge?: number;
    by_domain?: Record<string, number>;
    by_type?: Record<string, number>;
    high_confidence?: number;
    medium_confidence?: number;
    low_confidence?: number;
  };
}

export const knowledgeQueryTool: ToolDefinition = {
  name: "knowledge_query",
  description: `查询Agent积累的经验知识，用于指导决策

用途：
- 查询某个领域的历史经验
- 应用知识到当前决策
- 了解知识库的积累情况

何时使用：
- 需要了解过去的成功经验
- 做决策前想参考历史数据
- 评估某个策略的可靠性
- 查看知识库的积累进度

返回内容：
- 相关知识列表
- 置信度（基于历史验证）
- 具体建议（参数、预期收益等）
- 知识库统计信息`,

  parameters: Type.Object({
    domain: Type.Optional(Type.String({
      description: "知识领域（如sector:白酒）"
    })),
    action: Type.Optional(Type.Union([
      Type.Literal('query'),
      Type.Literal('apply'),
      Type.Literal('summary')
    ], {
      description: "操作类型",
      default: 'query'
    })),
    context: Type.Optional(Type.Any({
      description: "决策上下文（action=apply时需要）"
    }))
  }),

  execute: async (_toolCallId: string, params: KnowledgeQueryParams) => {
    try {
      const { domain, action = 'query', context } = params;

      let result;

      if (action === 'query') {
        // 查询知识
        const queryParams = new URLSearchParams();
        if (domain) queryParams.append('domain', domain);

        const apiResult = await runQuantV2(
          `/api/knowledge/active?${queryParams.toString()}`,
          'GET'
        );

        if (!apiResult.ok) {
          throw new Error("查询知识失败");
        }

        result = {
          knowledge_list: (apiResult as any).data || []
        };

      } else if (action === 'apply') {
        // 应用知识
        if (!context) {
          throw new Error("应用知识需要提供context参数");
        }

        const apiResult = await runQuantV2(
          '/api/knowledge/apply',
          'POST',
          context
        );

        if (!apiResult.ok) {
          throw new Error("应用知识失败");
        }

        result = {
          recommendations: (apiResult as any).data || []
        };

      } else {
        // 获取摘要
        const apiResult = await runQuantV2(
          '/api/knowledge/summary',
          'GET'
        );

        if (!apiResult.ok) {
          throw new Error("获取知识摘要失败");
        }

        result = {
          summary: (apiResult as any).data || {}
        };
      }

      // 格式化报告
      const report = formatKnowledgeReport(result, action);

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
          text: `❌ 知识查询失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化知识报告
 */
function formatKnowledgeReport(result: KnowledgeResult, action: string): string {
  const lines: string[] = [];

  if (action === 'query') {
    // 查询知识
    const knowledge_list = result.knowledge_list || [];

    lines.push('# 📚 知识库查询报告\n');
    lines.push(`**找到知识**: ${knowledge_list.length}条\n`);

    if (knowledge_list.length === 0) {
      lines.push('暂无相关知识。');
    } else {
      for (const k of knowledge_list) {
        const confidenceEmoji = getConfidenceEmoji(k.confidence || 0);

        lines.push(`## ${confidenceEmoji} ${k.domain || ''}\n`);
        lines.push(`**类型**: ${translateKnowledgeType(k.knowledge_type || '')}`);
        lines.push(`**置信度**: ${((k.confidence || 0) * 100).toFixed(0)}%`);
        lines.push(`**验证次数**: ${k.validation_count || 0}次（成功${k.success_count || 0}次）`);

        const content = k.content || {};
        if (content.rule) {
          lines.push(`**规则**: ${content.rule}`);
        }

        if (content.expected_return) {
          lines.push(`**预期收益**: ${content.expected_return}%`);
        }

        if (content.time_horizon) {
          lines.push(`**持有周期**: ${content.time_horizon}天`);
        }

        lines.push('');
      }
    }

  } else if (action === 'apply') {
    // 应用知识
    const recommendations = result.recommendations || [];

    lines.push('# 💡 知识应用建议\n');
    lines.push(`**找到匹配知识**: ${recommendations.length}条\n`);

    if (recommendations.length === 0) {
      lines.push('暂无可应用的知识。建议根据当前市场情况自主决策。');
    } else {
      for (const rec of recommendations) {
        const confidenceEmoji = getConfidenceEmoji(rec.confidence || 0);

        lines.push(`## ${confidenceEmoji} ${rec.rule}\n`);
        lines.push(`**置信度**: ${((rec.confidence || 0) * 100).toFixed(0)}%`);

        if (rec.suggestions && rec.suggestions.length > 0) {
          lines.push(`**建议**:`);
          for (const suggestion of rec.suggestions) {
            lines.push(`- ${suggestion}`);
          }
        }

        lines.push('');
      }
    }

  } else {
    // 知识摘要
    const summary = result.summary || {};

    lines.push('# 📊 知识库统计\n');
    lines.push(`**总知识数**: ${summary.total_knowledge || 0}条\n`);

    lines.push('## 按置信度分布\n');
    lines.push(`- 🟢 高置信度（≥80%）: ${summary.high_confidence || 0}条`);
    lines.push(`- 🟡 中等置信度（50-80%）: ${summary.medium_confidence || 0}条`);
    lines.push(`- 🔴 低置信度（<50%）: ${summary.low_confidence || 0}条\n`);

    if (summary.by_domain && Object.keys(summary.by_domain).length > 0) {
      lines.push('## 按领域分布\n');
      for (const [domain, count] of Object.entries(summary.by_domain)) {
        lines.push(`- ${domain}: ${count}条`);
      }
      lines.push('');
    }

    if (summary.by_type && Object.keys(summary.by_type).length > 0) {
      lines.push('## 按类型分布\n');
      for (const [type, count] of Object.entries(summary.by_type)) {
        lines.push(`- ${translateKnowledgeType(type)}: ${count}条`);
      }
    }
  }

  return lines.join('\n');
}

/**
 * 获取置信度emoji
 */
function getConfidenceEmoji(confidence: number): string {
  if (confidence >= 0.8) return '🟢';
  if (confidence >= 0.5) return '🟡';
  return '🔴';
}

/**
 * 翻译知识类型
 */
function translateKnowledgeType(type: string): string {
  const map: Record<string, string> = {
    'timing_rule': '择时规则',
    'filter_rule': '筛选规则',
    'strategy_param': '策略参数',
    'general': '通用经验'
  };
  return map[type] || type;
}
