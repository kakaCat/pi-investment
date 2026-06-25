/**
 * 机会扫描工具 - 增强版
 *
 * 用途：扫描股票池，发现符合策略的买入信号
 */

import type { ToolDefinition } from "../index.js";
import { QuantV2Client } from '../../adapters/quant/quant-v2-client.js';

const client = QuantV2Client;

interface OpportunityScanParams {
  strategy_ids?: number[];   // 策略ID列表，默认[272, 273]
  stock_pools?: string[];     // 股票池名称，默认全部
  min_score?: number;         // 最低评分，默认70
  limit?: number;             // 返回数量，默认10
}

export const opportunityScanEnhancedTool: ToolDefinition = {
  name: 'opportunity_scan_enhanced',
  label: '机会扫描',
  description: `扫描股票池，发现买入信号（增强版）

使用场景：
- 每日盘后扫描，发现今日买入机会
- 监控30只股票，不遗漏任何信号
- 自动评分排序，优先推荐高质量信号

功能增强：
- 支持多股票池（新能源、科技、医药）
- 支持多策略组合（272、273）
- 自动评分和排序
- 显示技术指标细节`,

  parameters: {
    type: 'object',
    properties: {
      strategy_ids: {
        type: 'array',
        items: { type: 'number' },
        description: '策略ID列表，例如：[272, 273]，默认两个都用',
        default: [272, 273]
      },
      stock_pools: {
        type: 'array',
        items: { type: 'string' },
        description: '股票池名称，可选：["新能源", "科技", "医药"]，默认全部',
        default: ['新能源', '科技', '医药']
      },
      min_score: {
        type: 'number',
        description: '最低评分（0-100），只返回评分>=此值的信号，默认70',
        default: 70
      },
      limit: {
        type: 'number',
        description: '返回数量限制，默认10',
        default: 10
      }
    }
  },

  execute: async (_toolCallId: string, params: OpportunityScanParams, _signal?: AbortSignal, _onUpdate?: any, _ctx?: any) => {
    try {
      const strategyIds = params.strategy_ids || [272, 273];
      const minScore = params.min_score || 70;
      const limit = params.limit || 10;

      // 股票池定义
      const stockPools: Record<string, string[]> = {
        '新能源': [
          '300750.SZ', '002594.SZ', '601012.SH', '300274.SZ', '300014.SZ',
          '688032.SH', '300763.SZ', '688599.SH', '300438.SZ', '002074.SZ'
        ],
        '科技': [
          '688981.SH', '002475.SZ', '002371.SZ', '688396.SH', '002049.SZ',
          '300782.SZ', '688008.SH', '688012.SH', '002230.SZ', '300059.SZ'
        ],
        '医药': [
          '300015.SZ', '603259.SH', '300122.SZ', '600276.SH', '300760.SZ',
          '688180.SH', '300685.SZ'
        ]
      };

      // 合并所有要扫描的股票
      const poolsToScan = params.stock_pools || ['新能源', '科技', '医药'];
      const allStocks: string[] = [];
      poolsToScan.forEach(poolName => {
        if (stockPools[poolName]) {
          allStocks.push(...stockPools[poolName]);
        }
      });

      let output = `📊 买入信号扫描报告\n`;
      output += `扫描时间: ${new Date().toLocaleString('zh-CN')}\n\n`;
      output += `📌 扫描范围:\n`;
      output += `  股票池: ${poolsToScan.join('、')}\n`;
      output += `  股票数量: ${allStocks.length} 只\n`;
      output += `  使用策略: ${strategyIds.map(id => `策略${id}`).join('、')}\n`;
      output += `  最低评分: ${minScore}\n\n`;

      // TODO: 实际实现时调用 quantsys-v2 API
      // 这里先返回模拟结果
      output += `⚠️ 功能实现中...\n\n`;
      output += `实际使用时，此工具会：\n`;
      output += `1. 调用 quantsys-v2 API 获取每只股票的最新数据\n`;
      output += `2. 检查是否满足策略272/273的买入条件\n`;
      output += `3. 计算技术指标评分\n`;
      output += `4. 返回评分最高的前${limit}个信号\n\n`;

      output += `💡 临时方案：\n`;
      output += `使用现有的 opportunity_scan 工具，或手动调用：\n`;
      output += `\`\`\`\n`;
      output += `curl -X POST http://127.0.0.1:5001/api/signals/opportunities \\\n`;
      output += `  -d '{"limit": ${limit}, "min_score": ${minScore}}'\n`;
      output += `\`\`\`\n`;

      return { details: {} as any, content: [{ type: "text" as const, text: output }] };

    } catch (error: any) {
      return { details: {} as any, content: [{ type: "text" as const, text: `❌ 扫描失败: ${error.message}` }] };
    }
  }
};
