/**
 * Market Alert Tool - 市场预警工具
 *
 * 实时监控市场风险信号和投资机会，提供预警通知和行动建议
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

export const marketAlertTool: ToolDefinition = {
  name: "market_alert",
  description: `查询市场预警信息，实时监控风险信号和投资机会

**核心功能**：
1. 风险预警 - 识别市场顶部、机构出货、操纵风险等危险信号
2. 机会预警 - 发现恐慌性抛售后的抄底机会、超跌反弹机会
3. 资金流向监控 - 追踪散户、机构、北向资金的异常行为
4. 市场情绪分析 - 识别极度贪婪或恐慌的市场转折点

**何时使用**：
- 每日盘前/盘后例行检查（建议每天至少2次）
- 做出买卖决策前必查，避免在高风险时段操作
- 发现持仓股票出现异常波动时
- 准备调整仓位或选股时参考市场整体状态

**返回信息**：
- 预警类型：opportunity（机会）/ risk（风险）
- 预警级别：critical（紧急）/ high（高）/ medium（中）/ low（低）
- 相关股票代码和具体描述
- 建议的应对行动（买入/卖出/观望/减仓等）

**典型场景**：
- 散户恐慌抛售 + 机构建仓 = 抄底机会预警
- 散户疯狂追涨 + 机构减仓 = 顶部风险预警
- 成交量暴增 + 股价异常波动 = 操纵风险预警
- 北向资金连续流出 + 市场调整 = 系统性风险预警`,

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
        const apiResult = await runQuantV2('alerts.check');

        if (!apiResult.ok) {
          throw new Error("检查预警失败");
        }

        result.alerts = (apiResult as any).data || [];

      } else {
        // 获取统计
        const apiResult = await runQuantV2('alerts.statistics');

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

    lines.push('# 🚨 市场预警报告\n');
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
