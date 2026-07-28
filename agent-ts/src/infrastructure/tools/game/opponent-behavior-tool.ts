/**
 * Opponent Behavior Tool - 对手行为分析工具
 *
 * 分析市场参与者（散户、机构、游资）的行为，识别博弈机会
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { snakeize } from "../utils/index.js";

interface OpponentBehaviorParams {
  // 无参数，分析当前市场状态
}

interface OpponentBehaviorResult {
  retail?: {
    behavior?: string;
    net_flow?: number | null;
    emotion_index?: number | null;
    common_mistakes?: string[];
    degraded?: boolean;
    reason?: string;
    description?: string;
  };
  institution?: {
    behavior?: string;
    net_flow?: number | null;
    target_sectors?: string[];
    position_change?: string;
    degraded?: boolean;
    reason?: string;
    description?: string;
  };
  hot_money?: {
    behavior?: string;
    target_stocks?: string[];
    stage?: string | null;
    activity_level?: string;
    estimated?: boolean;
    description?: string;
  };
  market_phase?: string;
  risk_appetite?: string;
  opportunity_map?: Record<string, any[]>;
  timestamp?: string;
}

export const opponentBehaviorTool: ToolDefinition = {
  name: "opponent_behavior",
  description: `分析市场参与者行为，识别博弈机会

用途：
- 了解散户、机构、游资当前在做什么
- 判断市场所处阶段（吸筹/派发/上涨/下跌）
- 发现博弈机会（收割散户恐慌、避开机构出货等）

何时使用：
- 需要了解市场整体情绪和资金流向时
- 寻找抄底或逃顶机会时
- 判断当前市场环境是否适合建仓/出货时
- 分析池子或股票时，想了解对手行为

返回内容：
- 散户行为（恐慌抛售/追涨买入/中性）
- 机构行为（建仓/出货/中性）
- 游资行为（拉高出货/不活跃）
- 市场阶段（吸筹/派发/上涨/下跌/震荡）
- 博弈机会地图（具体的策略建议）`,

  parameters: Type.Object({}),

  execute: async (_toolCallId: string, params: OpponentBehaviorParams) => {
    try {
      // 调用 V2 API（使用命令格式）
      const result = await runQuantV2('market.opponent_behavior', {});

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "对手行为分析失败";
        throw new Error(errorMsg);
      }

      // 提取数据（snakeize：后端部分路由经 api_response 转 camelCase）
      const data: OpponentBehaviorResult = snakeize<OpponentBehaviorResult>((result as any).data || {});

      // 构建可读的分析报告
      const report = formatOpponentBehaviorReport(data);

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
          text: `❌ 对手行为分析失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化对手行为报告
 */
function formatOpponentBehaviorReport(data: OpponentBehaviorResult): string {
  const lines: string[] = [];

  lines.push('# 📊 市场对手行为分析报告\n');

  // 散户行为
  if (data.retail) {
    lines.push('## 💰 散户行为');
    if (data.retail.degraded) {
      lines.push(`- ⚠️ **数据不可用**: ${data.retail.reason || '资金流数据缺失'}`);
    } else {
      lines.push(`- **行为模式**: ${translateBehavior(data.retail.behavior || '', 'retail')}`);
      lines.push(`- **资金流向**: ${formatFlow(data.retail.net_flow)}`);
      lines.push(`- **情绪指数**: ${data.retail.emotion_index != null ? `${data.retail.emotion_index.toFixed(1)}/100 ${getEmotionLabel(data.retail.emotion_index)}` : '数据不可用'}`);
    }
    lines.push(`- **说明**: ${data.retail.description || ''}`);
    if (data.retail.common_mistakes && data.retail.common_mistakes.length > 0) {
      lines.push(`- **常见错误**: ${data.retail.common_mistakes.join('、')}`);
    }
    lines.push('');
  }

  // 机构行为
  if (data.institution) {
    lines.push('## 🏛️ 机构行为');
    if (data.institution.degraded) {
      lines.push(`- ⚠️ **数据不可用**: ${data.institution.reason || '资金流数据缺失'}`);
    } else {
      lines.push(`- **行为模式**: ${translateBehavior(data.institution.behavior || '', 'institution')}`);
      lines.push(`- **资金流向**: ${formatFlow(data.institution.net_flow)}`);
      lines.push(`- **仓位变化**: ${translatePositionChange(data.institution.position_change || '')}`);
      if (data.institution.target_sectors && data.institution.target_sectors.length > 0) {
        lines.push(`- **目标板块**: ${data.institution.target_sectors.join('、')}`);
      }
    }
    lines.push(`- **说明**: ${data.institution.description || ''}`);
    lines.push('');
  }

  // 游资行为
  if (data.hot_money) {
    lines.push('## 🔥 游资行为');
    lines.push(`- **活跃度**: ${translateActivityLevel(data.hot_money.activity_level || 'low')}`);
    lines.push(`- **说明**: ${data.hot_money.description || ''}`);
    if (data.hot_money.target_stocks && data.hot_money.target_stocks.length > 0) {
      lines.push(`- **目标股票**: ${data.hot_money.target_stocks.join('、')}`);
    }
    lines.push('');
  }

  // 市场整体
  lines.push('## 🌍 市场状态');
  lines.push(`- **市场阶段**: ${translateMarketPhase(data.market_phase || 'consolidation')}`);
  lines.push(`- **风险偏好**: ${translateRiskAppetite(data.risk_appetite || 'medium')}`);
  lines.push('');

  // 博弈机会
  if (data.opportunity_map && Object.keys(data.opportunity_map).length > 0) {
    lines.push('## 🎯 博弈机会');
    for (const [key, opportunities] of Object.entries(data.opportunity_map)) {
      lines.push(`\n### ${translateOpportunityKey(key)}`);
      for (const opp of opportunities) {
        if (opp.strategy) {
          lines.push(`- **策略**: ${opp.strategy}`);
          lines.push(`  - 置信度: ${opp.confidence || 'N/A'}`);
          lines.push(`  - 预期收益: ${opp.expected_return || 'N/A'}`);
          lines.push(`  - 时间周期: ${opp.time_horizon || 'N/A'}`);
          lines.push(`  - 原因: ${opp.reason}`);
          lines.push(`  - 行动: ${opp.action}`);
        } else if (opp.risk) {
          lines.push(`- **风险级别**: ${opp.risk}`);
          lines.push(`  - 原因: ${opp.reason}`);
          lines.push(`  - 行动: ${opp.action}`);
          lines.push(`  - 紧急度: ${opp.urgency || 'N/A'}`);
        }
      }
    }
  } else {
    lines.push('## 🎯 博弈机会\n暂无明显机会');
  }

  return lines.join('\n');
}

/**
 * 生成简短摘要
 */
function generateSummary(data: OpponentBehaviorResult): string {
  const parts: string[] = [];

  parts.push(`市场阶段: ${translateMarketPhase(data.market_phase || 'consolidation')}`);

  if (data.retail?.behavior) {
    parts.push(`散户${translateBehavior(data.retail.behavior, 'retail')}`);
  }

  if (data.institution?.behavior) {
    parts.push(`机构${translateBehavior(data.institution.behavior, 'institution')}`);
  }

  const oppCount = data.opportunity_map ? Object.keys(data.opportunity_map).length : 0;
  if (oppCount > 0) {
    parts.push(`发现${oppCount}个博弈机会`);
  }

  return parts.join('，');
}

// ==================== 辅助函数 ====================

function translateBehavior(behavior: string, participant: string): string {
  const map: Record<string, string> = {
    'panic_selling': '恐慌抛售',
    'fomo_buying': '追涨买入',
    'neutral': '观望',
    'accumulating': '建仓',
    'distributing': '出货',
    'pump_and_dump': '拉高出货',
    'inactive': '不活跃'
  };
  return map[behavior] || behavior;
}

function formatFlow(flow?: number | null): string {
  if (flow === null || flow === undefined) {
    return '数据不可用';
  }
  const yi = flow / 100000000;
  const sign = yi >= 0 ? '+' : '';
  return `${sign}${yi.toFixed(2)}亿元`;
}

function getEmotionLabel(index: number): string {
  if (index < 20) return '(极度恐慌)';
  if (index < 40) return '(恐慌)';
  if (index < 60) return '(中性)';
  if (index < 80) return '(贪婪)';
  return '(极度贪婪)';
}

function translatePositionChange(change: string): string {
  const map: Record<string, string> = {
    'increasing': '增仓',
    'decreasing': '减仓',
    'stable': '维持'
  };
  return map[change] || change;
}

function translateActivityLevel(level: string): string {
  const map: Record<string, string> = {
    'high': '高',
    'medium': '中',
    'low': '低'
  };
  return map[level] || level;
}

function translateMarketPhase(phase: string): string {
  const map: Record<string, string> = {
    'accumulation': '吸筹阶段（底部）',
    'markup': '上涨阶段',
    'distribution': '派发阶段（顶部）',
    'markdown': '下跌阶段',
    'consolidation': '震荡整理'
  };
  return map[phase] || phase;
}

function translateRiskAppetite(appetite: string): string {
  const map: Record<string, string> = {
    'high': '高风险偏好',
    'medium': '中性',
    'low': '低风险偏好'
  };
  return map[appetite] || appetite;
}

function translateOpportunityKey(key: string): string {
  const map: Record<string, string> = {
    'take_from_retail': '收割散户恐慌',
    'avoid_institution': '避开机构出货',
    'follow_institution': '跟随机构建仓',
    'post_manipulation': '游资炒作后抄底'
  };
  return map[key] || key;
}
