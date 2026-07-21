/**
 * Manipulation Detection Tool - 操纵检测工具
 *
 * 检测市场操纵行为（拉高出货等），识别风险和机会
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface ManipulationResult {
  active_manipulations?: Array<{
    symbol?: string;
    name?: string;
    manipulation_type?: string;
    stage?: string;
    confidence?: number;
    signals?: string[];
    fair_value?: number;
    current_price?: number;
    deviation?: string;
    action?: string;
    risk_level?: string;
  }>;
  post_manipulation_opportunities?: Array<{
    symbol?: string;
    stage?: string;
    collapsed_from?: number;
    current_price?: number;
    fair_value?: number;
    upside?: string;
    confidence?: number;
    action?: string;
    entry_trigger?: string;
  }>;
  timestamp?: string;
}

export const manipulationDetectTool: ToolDefinition = {
  name: "manipulation_detect",
  description: `检测市场操纵行为，识别拉高出货陷阱和崩盘后机会

用途：
- 识别被游资操纵的股票（拉高出货）
- 避开操纵陷阱，防止高位接盘
- 发现崩盘后的抄底机会
- 评估股票是否处于操纵风险中

何时使用：
- 看到某只股票连续涨停时
- 评估是否追涨某只热门股票
- 寻找被错杀的抄底机会
- 定期扫描市场风险

返回内容：
- 活跃的操纵事件（应避开）
- 检测到的操纵信号
- 崩盘后的抄底机会
- 风险级别评估`,

  parameters: Type.Object({}),

  execute: async (_toolCallId: string, params: {}) => {
    try {
      // 调用 V2 API
      const result = await runQuantV2('market.manipulation_detect', {});

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "操纵检测失败";
        throw new Error(errorMsg);
      }

      // 提取数据
      const data: ManipulationResult = (result as any).data || {};

      // 构建可读的检测报告
      const report = formatManipulationReport(data);

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
          text: `❌ 操纵检测失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化操纵检测报告
 */
function formatManipulationReport(data: ManipulationResult): string {
  const lines: string[] = [];

  lines.push('# 🚨 市场操纵检测报告\n');

  // 活跃的操纵事件
  const active = data.active_manipulations || [];
  if (active.length > 0) {
    lines.push(`## ⚠️ 发现 ${active.length} 个活跃操纵事件\n`);

    for (const manip of active) {
      const riskEmoji = getRiskEmoji(manip.risk_level || 'medium');
      lines.push(`### ${riskEmoji} ${manip.symbol} - ${manip.name || ''}\n`);

      lines.push(`**操纵类型**: ${translateManipType(manip.manipulation_type || '')}`);
      lines.push(`**当前阶段**: ${translateStage(manip.stage || '')}`);
      lines.push(`**风险级别**: ${translateRiskLevel(manip.risk_level || 'medium')}`);
      lines.push(`**置信度**: ${((manip.confidence || 0) * 100).toFixed(0)}%\n`);

      if (manip.signals && manip.signals.length > 0) {
        lines.push('**检测到的信号**:');
        for (const signal of manip.signals) {
          lines.push(`- ${signal}`);
        }
        lines.push('');
      }

      lines.push(`**价格分析**:`);
      lines.push(`- 当前价格: ¥${manip.current_price?.toFixed(2) || 'N/A'}`);
      lines.push(`- 公允价值: ¥${manip.fair_value?.toFixed(2) || 'N/A'}`);
      lines.push(`- 偏离度: ${manip.deviation || 'N/A'}`);
      lines.push('');

      lines.push(`**建议行动**: ${translateAction(manip.action || '')}`);
      lines.push('');
    }
  } else {
    lines.push('## ✅ 未发现明显的操纵行为\n');
  }

  // 抄底机会
  const opportunities = data.post_manipulation_opportunities || [];
  if (opportunities.length > 0) {
    lines.push(`## 💰 发现 ${opportunities.length} 个抄底机会\n`);

    for (const opp of opportunities) {
      lines.push(`### 📉 ${opp.symbol}\n`);

      lines.push(`**状态**: ${translateStage(opp.stage || '')}`);
      lines.push(`**崩盘前价格**: ¥${opp.collapsed_from?.toFixed(2) || 'N/A'}`);
      lines.push(`**当前价格**: ¥${opp.current_price?.toFixed(2) || 'N/A'}`);
      lines.push(`**公允价值**: ¥${opp.fair_value?.toFixed(2) || 'N/A'}`);
      lines.push(`**潜在收益**: ${opp.upside || 'N/A'}`);
      lines.push(`**置信度**: ${((opp.confidence || 0) * 100).toFixed(0)}%\n`);

      lines.push(`**建议**: ${opp.entry_trigger || '止跌企稳后介入'}`);
      lines.push('');
    }
  }

  if (active.length === 0 && opportunities.length === 0) {
    lines.push('当前市场相对平静，未发现明显的操纵行为或抄底机会。');
  }

  return lines.join('\n');
}

/**
 * 翻译操纵类型
 */
function translateManipType(type: string): string {
  const map: Record<string, string> = {
    'pump_and_dump': '拉高出货',
    'wash_trading': '对敲交易',
    'spoofing': '虚假挂单'
  };
  return map[type] || type;
}

/**
 * 翻译操纵阶段
 */
function translateStage(stage: string): string {
  const map: Record<string, string> = {
    'accumulation': '吸筹阶段',
    'markup': '拉高阶段 ⚠️',
    'distribution': '出货阶段 🚨',
    'collapse': '崩盘阶段',
    'collapse_complete': '崩盘完成，进入合理区间'
  };
  return map[stage] || stage;
}

/**
 * 翻译风险级别
 */
function translateRiskLevel(level: string): string {
  const map: Record<string, string> = {
    'extreme': '极高 🔴',
    'high': '高 🟠',
    'medium': '中等 🟡',
    'low': '低 🟢'
  };
  return map[level] || level;
}

/**
 * 翻译操作建议
 */
function translateAction(action: string): string {
  const map: Record<string, string> = {
    'avoid': '🛑 远离该股，避免接盘',
    'monitor': '👀 密切监控，暂不介入',
    'bottom_fishing': '🎣 可考虑抄底（止跌后）',
    'exit': '🏃 立即退出'
  };
  return map[action] || action;
}

/**
 * 获取风险emoji
 */
function getRiskEmoji(level: string): string {
  const map: Record<string, string> = {
    'extreme': '🔴',
    'high': '🟠',
    'medium': '🟡',
    'low': '🟢'
  };
  return map[level] || '⚠️';
}
