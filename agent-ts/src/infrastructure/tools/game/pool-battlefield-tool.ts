/**
 * Pool Battlefield Assessment Tool - 池子战场评估工具
 *
 * 评估股票池在市场博弈中的竞争优势
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface PoolBattlefieldParams {
  pool_id: number;
}

interface BattlefieldResult {
  pool_id?: number;
  battlefield_score?: number;
  opponent_strength?: {
    retail_pressure?: string;
    institution_interest?: string;
    hot_money_risk?: string;
  };
  game_phase?: string;
  advantages?: string[];
  disadvantages?: string[];
  recommendation?: string;
  urgency?: string;
  confidence?: number;
}

export const poolBattlefieldTool: ToolDefinition = {
  name: "pool_battlefield",
  description: `评估股票池的战场优势和博弈竞争力

用途：
- 评估池子在市场博弈中的竞争位置
- 分析对手（散户/机构/游资）对池子的态度
- 识别池子的优势和劣势
- 获取具体的仓位建议

何时使用：
- 评估现有池子是否值得继续持有
- 决定是否增仓、减仓或退出
- 了解池子在当前市场环境下的竞争力
- 对比多个池子的战场优势

返回内容：
- 战场评分（0-100）
- 对手强度分析
- 博弈阶段判断
- 优势和劣势列表
- 操作建议（建仓/持有/减仓/退出）`,

  parameters: Type.Object({
    pool_id: Type.Number({
      description: "股票池ID"
    })
  }),

  execute: async (_toolCallId: string, params: PoolBattlefieldParams) => {
    try {
      const { pool_id } = params;

      // 调用 V2 API
      const result = await runQuantV2(
        `/api/game/pools/${pool_id}/battlefield-assessment`,
        'GET'
      );

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "战场评估失败";
        throw new Error(errorMsg);
      }

      // 提取数据
      const data: BattlefieldResult = (result as any).data || {};

      // 构建可读的评估报告
      const report = formatBattlefieldReport(data);

      return {
        content: [{
          type: "text" as const,
          text: report
        }],
        details: data
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 池子战场评估失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化战场评估报告
 */
function formatBattlefieldReport(data: BattlefieldResult): string {
  const lines: string[] = [];

  lines.push('# 🎯 池子战场评估报告\n');

  // 综合评分
  const score = data.battlefield_score || 0;
  const scoreEmoji = score > 80 ? '🟢' : score > 60 ? '🟡' : score > 40 ? '🟠' : '🔴';
  lines.push(`## ${scoreEmoji} 综合评分: ${score.toFixed(1)}/100\n`);

  // 博弈阶段
  if (data.game_phase) {
    lines.push(`**博弈阶段**: ${translateGamePhase(data.game_phase)}\n`);
  }

  // 对手强度
  if (data.opponent_strength) {
    lines.push('## 🎭 对手强度分析\n');
    const strength = data.opponent_strength;
    lines.push(`- **散户压力**: ${translateStrength(strength.retail_pressure || 'medium')}`);
    lines.push(`- **机构兴趣**: ${translateStrength(strength.institution_interest || 'medium')}`);
    lines.push(`- **游资风险**: ${translateStrength(strength.hot_money_risk || 'low')}`);
    lines.push('');
  }

  // 优势
  if (data.advantages && data.advantages.length > 0) {
    lines.push('## ✅ 竞争优势\n');
    for (const advantage of data.advantages) {
      lines.push(`- ${advantage}`);
    }
    lines.push('');
  }

  // 劣势
  if (data.disadvantages && data.disadvantages.length > 0) {
    lines.push('## ⚠️ 竞争劣势\n');
    for (const disadvantage of data.disadvantages) {
      lines.push(`- ${disadvantage}`);
    }
    lines.push('');
  }

  // 操作建议
  if (data.recommendation) {
    lines.push('## 💡 操作建议\n');
    const actionEmoji = getActionEmoji(data.recommendation);
    lines.push(`${actionEmoji} **${translateRecommendation(data.recommendation)}**`);

    if (data.urgency) {
      lines.push(`- 紧急度: ${translateUrgency(data.urgency)}`);
    }

    if (data.confidence) {
      lines.push(`- 置信度: ${(data.confidence * 100).toFixed(0)}%`);
    }
  }

  return lines.join('\n');
}

/**
 * 翻译博弈阶段
 */
function translateGamePhase(phase: string): string {
  const map: Record<string, string> = {
    'early_accumulation': '早期吸筹（底部机会）',
    'late_accumulation': '后期吸筹',
    'rising': '上涨阶段',
    'early_distribution': '早期派发',
    'topping': '顶部区域（警惕风险）',
    'declining': '下跌阶段',
    'consolidation': '震荡整理'
  };
  return map[phase] || phase;
}

/**
 * 翻译强度级别
 */
function translateStrength(level: string): string {
  const map: Record<string, string> = {
    'low': '低 ✅',
    'medium': '中等 ⚠️',
    'high': '高 🚨'
  };
  return map[level] || level;
}

/**
 * 翻译操作建议
 */
function translateRecommendation(rec: string): string {
  const map: Record<string, string> = {
    'accumulate': '积极建仓',
    'hold': '持有观望',
    'reduce': '减仓控制风险',
    'exit': '退出止损'
  };
  return map[rec] || rec;
}

/**
 * 翻译紧急度
 */
function translateUrgency(urgency: string): string {
  const map: Record<string, string> = {
    'high': '高（建议立即行动）',
    'medium': '中等',
    'low': '低（可观察）'
  };
  return map[urgency] || urgency;
}

/**
 * 获取操作emoji
 */
function getActionEmoji(rec: string): string {
  const map: Record<string, string> = {
    'accumulate': '🚀',
    'hold': '✋',
    'reduce': '⚠️',
    'exit': '🛑'
  };
  return map[rec] || '💡';
}
