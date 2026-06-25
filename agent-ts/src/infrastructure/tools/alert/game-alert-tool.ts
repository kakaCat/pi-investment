/**
 * Game Alert Tool - 博弈预警工具
 *
 * 查询实时博弈预警，获取风险和机会通知
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface AlertQueryParams {
  action?: 'check' | 'statistics';
}

interface AlertResult {
  alerts?: Array<{
    alert_id?: string;
    type?: string;
    level?: string;
    title?: string;
    message?: string;
    action?: string;
    symbols?: string[];
    details?: any;
    created_at?: string;
  }>;
  statistics?: {
    total_alerts?: number;
    by_type?: Record<string, number>;
    by_level?: Record<string, number>;
    recent_alerts?: any[];
  };
}

export const gameAlertTool: ToolDefinition = {
  name: "game_alert",
  description: `查询实时博弈预警，获取市场风险和机会通知

用途：
- 检查当前市场预警
- 发现抄底机会（散户恐慌+机构建仓）
- 发现风险信号（散户追涨+机构出货）
- 识别操纵风险（拉高出货预警）

何时使用：
- 定期检查市场状态（建议每小时一次）
- 做决策前查看是否有重要预警
- 了解当前市场风险和机会

返回内容：
- 机会预警（抄底机会、崩盘后机会）
- 风险预警（顶部风险、操纵风险、机构出货）
- 预警级别（critical/high/medium/low）
- 具体行动建议`,

  parameters: Type.Object({
    action: Type.Optional(Type.Union([
      Type.Literal('check'),
      Type.Literal('statistics')
    ], {
      description: "操作类型",
      default: 'check'
    }))
  }),

  execute: async (_toolCallId: string, params: AlertQueryParams) => {
    try {
      const { action = 'check' } = params;

      let result: AlertResult = {};

      if (action === 'check') {
        // 检查预警
        const apiResult = await runQuantV2(
          '/api/alerts/check',
          'GET'
        );

        if (!apiResult.ok) {
          throw new Error("检查预警失败");
        }

        result.alerts = (apiResult as any).data || [];

      } else {
        // 获取统计
        const apiResult = await runQuantV2(
          '/api/alerts/statistics',
          'GET'
        );

        if (!apiResult.ok) {
          throw new Error("获取预警统计失败");
        }

        result.statistics = (apiResult as any).data || {};
      }

      // 格式化报告
      const report = formatAlertReport(result, action);

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
          text: `❌ 预警查询失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化预警报告
 */
function formatAlertReport(result: AlertResult, action: string): string {
  const lines: string[] = [];

  if (action === 'check') {
    // 预警列表
    const alerts = result.alerts || [];

    lines.push('# 🚨 博弈预警报告\n');
    lines.push(`**检查时间**: ${new Date().toLocaleString('zh-CN')}`);
    lines.push(`**预警数量**: ${alerts.length}条\n`);

    if (alerts.length === 0) {
      lines.push('✅ 当前无预警，市场相对平静。');
      return lines.join('\n');
    }

    // 按类型分组
    const opportunities = alerts.filter(a => a.type === 'opportunity');
    const risks = alerts.filter(a => a.type === 'risk');

    // 机会预警
    if (opportunities.length > 0) {
      lines.push('## 💰 机会预警\n');
      for (const alert of opportunities) {
        const levelEmoji = getLevelEmoji(alert.level || 'medium');
        lines.push(`### ${levelEmoji} ${alert.title}\n`);
        lines.push(`**级别**: ${translateLevel(alert.level || 'medium')}`);
        lines.push(`**消息**: ${alert.message}`);
        lines.push(`**建议**: ${alert.action}`);

        if (alert.symbols && alert.symbols.length > 0) {
          lines.push(`**相关股票**: ${alert.symbols.join(', ')}`);
        }

        lines.push('');
      }
    }

    // 风险预警
    if (risks.length > 0) {
      lines.push('## ⚠️ 风险预警\n');
      for (const alert of risks) {
        const levelEmoji = getLevelEmoji(alert.level || 'medium');
        lines.push(`### ${levelEmoji} ${alert.title}\n`);
        lines.push(`**级别**: ${translateLevel(alert.level || 'medium')}`);
        lines.push(`**消息**: ${alert.message}`);
        lines.push(`**建议**: ${alert.action}`);

        if (alert.symbols && alert.symbols.length > 0) {
          lines.push(`**相关股票**: ${alert.symbols.join(', ')}`);
        }

        lines.push('');
      }
    }

  } else {
    // 统计信息
    const stats = result.statistics || {};

    lines.push('# 📊 预警统计\n');

    lines.push(`**总预警数**: ${stats.total_alerts || 0}条\n`);

    // 按类型
    const by_type = stats.by_type || {};
    if (Object.keys(by_type).length > 0) {
      lines.push('## 按类型分布\n');
      for (const [type, count] of Object.entries(by_type)) {
        lines.push(`- ${translateType(type)}: ${count}条`);
      }
      lines.push('');
    }

    // 按级别
    const by_level = stats.by_level || {};
    if (Object.keys(by_level).length > 0) {
      lines.push('## 按级别分布\n');
      for (const [level, count] of Object.entries(by_level)) {
        const emoji = getLevelEmoji(level);
        lines.push(`- ${emoji} ${translateLevel(level)}: ${count}条`);
      }
    }
  }

  return lines.join('\n');
}

/**
 * 获取级别emoji
 */
function getLevelEmoji(level: string): string {
  const map: Record<string, string> = {
    'critical': '🔴',
    'high': '🟠',
    'medium': '🟡',
    'low': '🟢'
  };
  return map[level] || '⚪';
}

/**
 * 翻译级别
 */
function translateLevel(level: string): string {
  const map: Record<string, string> = {
    'critical': '紧急',
    'high': '高',
    'medium': '中',
    'low': '低'
  };
  return map[level] || level;
}

/**
 * 翻译类型
 */
function translateType(type: string): string {
  const map: Record<string, string> = {
    'opportunity': '机会',
    'risk': '风险'
  };
  return map[type] || type;
}
