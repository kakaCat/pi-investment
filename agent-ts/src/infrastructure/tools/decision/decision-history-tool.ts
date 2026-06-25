/**
 * Decision History Tool - 决策历史查询工具
 *
 * 查询Agent的历史决策记录，用于学习和改进
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface DecisionHistoryParams {
  entity_type?: string;
  entity_id?: string;
  decision_type?: string;
  limit?: number;
}

interface DecisionHistoryResult {
  decisions?: Array<{
    decision_id?: string;
    decision_type?: string;
    context?: any;
    parameters?: any;
    reasoning?: string;
    related_entity_type?: string;
    related_entity_id?: string;
    evaluation_status?: string;
    success?: boolean;
    learned_lesson?: string;
    created_at?: string;
  }>;
}

export const decisionHistoryTool: ToolDefinition = {
  name: "decision_history",
  description: `查询Agent的历史决策记录，用于回顾和学习

用途：
- 查看某个池子的所有决策历史
- 回顾过去的操作和推理
- 分析决策结果，总结经验
- 了解Agent的决策模式

何时使用：
- 需要回顾某个池子的创建和调整历史
- 分析为什么做了某个决策
- 总结成功和失败的经验
- 评估Agent的决策质量

返回内容：
- 决策列表（按时间倒序）
- 每个决策的完整信息
- 决策推理过程
- 评估结果（如果已评估）`,

  parameters: Type.Object({
    entity_type: Type.Optional(Type.String({
      description: "实体类型（如pool、stock）"
    })),
    entity_id: Type.Optional(Type.String({
      description: "实体ID"
    })),
    decision_type: Type.Optional(Type.String({
      description: "决策类型过滤"
    })),
    limit: Type.Optional(Type.Number({
      description: "返回数量限制",
      default: 20
    }))
  }),

  execute: async (_toolCallId: string, params: DecisionHistoryParams) => {
    try {
      const { entity_type, entity_id, decision_type, limit = 20 } = params;

      // 构建查询参数
      const queryParams = new URLSearchParams();
      if (entity_type) queryParams.append('entity_type', entity_type);
      if (entity_id) queryParams.append('entity_id', entity_id);
      if (decision_type) queryParams.append('decision_type', decision_type);
      queryParams.append('limit', limit.toString());

      // 调用 V2 API
      const result = await runQuantV2(
        `/api/decisions/history?${queryParams.toString()}`,
        'GET'
      );

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "查询决策历史失败";
        throw new Error(errorMsg);
      }

      // 提取数据
      const decisions = (result as any).data || [];

      // 构建可读的历史报告
      const report = formatDecisionHistory(decisions, params);

      return {
        content: [{
          type: "text" as const,
          text: report
        }],
        details: { decisions }
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 查询决策历史失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化决策历史报告
 */
function formatDecisionHistory(decisions: any[], params: DecisionHistoryParams): string {
  const lines: string[] = [];

  lines.push('# 📋 决策历史报告\n');

  // 过滤信息
  if (params.entity_type && params.entity_id) {
    lines.push(`**查询范围**: ${params.entity_type}/${params.entity_id}`);
  }
  if (params.decision_type) {
    lines.push(`**决策类型**: ${translateDecisionType(params.decision_type)}`);
  }
  lines.push(`**找到决策**: ${decisions.length}条\n`);

  if (decisions.length === 0) {
    lines.push('暂无决策记录。');
    return lines.join('\n');
  }

  // 统计信息
  const stats = calculateStats(decisions);
  lines.push('## 📊 统计概览\n');
  lines.push(`- **总决策数**: ${stats.total}`);
  lines.push(`- **已评估**: ${stats.evaluated}条`);
  lines.push(`- **待评估**: ${stats.pending}条`);
  if (stats.evaluated > 0) {
    lines.push(`- **成功率**: ${(stats.success_rate * 100).toFixed(1)}%`);
  }
  lines.push('');

  // 决策列表
  lines.push('## 🕐 决策时间线\n');

  for (const decision of decisions.slice(0, 10)) {  // 只显示最近10条
    const typeEmoji = getDecisionTypeEmoji(decision.decision_type);
    const statusEmoji = getStatusEmoji(decision.evaluation_status, decision.success);

    lines.push(`### ${statusEmoji} ${typeEmoji} ${translateDecisionType(decision.decision_type)}`);
    lines.push(`**决策ID**: ${decision.decision_id}`);
    lines.push(`**时间**: ${formatDate(decision.created_at)}`);

    if (decision.reasoning) {
      lines.push(`**推理**: ${decision.reasoning}`);
    }

    if (decision.evaluation_status === 'evaluated') {
      lines.push(`**结果**: ${decision.success ? '✅ 成功' : '❌ 失败'}`);
      if (decision.learned_lesson) {
        lines.push(`**教训**: ${decision.learned_lesson}`);
      }
    } else {
      lines.push(`**状态**: ⏳ 待评估`);
    }

    lines.push('');
  }

  if (decisions.length > 10) {
    lines.push(`_（还有${decisions.length - 10}条决策未显示）_`);
  }

  return lines.join('\n');
}

/**
 * 计算统计信息
 */
function calculateStats(decisions: any[]) {
  const total = decisions.length;
  let evaluated = 0;
  let success = 0;

  for (const dec of decisions) {
    if (dec.evaluation_status === 'evaluated') {
      evaluated++;
      if (dec.success) {
        success++;
      }
    }
  }

  return {
    total,
    evaluated,
    pending: total - evaluated,
    success_rate: evaluated > 0 ? success / evaluated : 0
  };
}

/**
 * 翻译决策类型
 */
function translateDecisionType(type: string): string {
  const map: Record<string, string> = {
    'create_pool': '创建池子',
    'update_pool': '更新池子',
    'delete_pool': '删除池子',
    'refresh_pool': '刷新池子',
    'add_stock': '添加股票',
    'remove_stock': '移除股票',
    'select_strategy': '选择策略',
    'screening': '筛选',
    'auto_risk_control': '自动风控',
    'auto_capture_opportunity': '自动抓机会'
  };
  return map[type] || type;
}

/**
 * 获取决策类型emoji
 */
function getDecisionTypeEmoji(type: string): string {
  const map: Record<string, string> = {
    'create_pool': '🆕',
    'update_pool': '✏️',
    'delete_pool': '🗑️',
    'refresh_pool': '🔄',
    'add_stock': '➕',
    'remove_stock': '➖',
    'select_strategy': '🎯',
    'screening': '🔍',
    'auto_risk_control': '🛡️',
    'auto_capture_opportunity': '💰'
  };
  return map[type] || '📝';
}

/**
 * 获取状态emoji
 */
function getStatusEmoji(status: string, success?: boolean): string {
  if (status === 'evaluated') {
    return success ? '✅' : '❌';
  }
  return '⏳';
}

/**
 * 格式化日期
 */
function formatDate(dateStr: string): string {
  if (!dateStr) return 'N/A';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}
