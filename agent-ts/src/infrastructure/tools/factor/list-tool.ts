/**
 * Factor List Tool - 查看所有可用因子
 *
 * 功能：列出系统中所有163个可用因子及分类
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorListParams {
  category?: string;
  show_count_only?: boolean;
}

export const factorListTool: ToolDefinition = {
  name: "factor_list",
  label: "因子列表",
  description:
    "查看系统中所有可用因子及分类。" +
    "\n\n📊 **功能**：" +
    "\n  • 列出所有163个可用因子" +
    "\n  • 按分类展示（动量、趋势、波动率等10大类）" +
    "\n  • 可筛选特定分类" +
    "\n  • 显示因子统计信息" +
    "\n\n💡 **使用场景**：" +
    "\n  • 策略开发前查看可用因子" +
    "\n  • 探索特定类别的因子" +
    "\n  • 了解因子总数和分布" +
    "\n\n📁 **因子分类**：" +
    "\n  • momentum - 动量因子（15个）" +
    "\n  • trend - 趋势因子（8个）" +
    "\n  • volatility - 波动率因子（9个）" +
    "\n  • volume - 成交量因子（7个）" +
    "\n  • moving_average - 移动平均因子（10个）" +
    "\n  • reversal - 反转因子（3个）" +
    "\n  • advanced - 高级因子（23个）" +
    "\n  • cycle - 周期因子（5个）" +
    "\n  • pattern - 形态识别因子（61个）" +
    "\n  • other - 其他因子（22个）",

  parameters: Type.Object({
    category: Type.Optional(
      Type.String({
        description: "筛选特定分类（可选）。可选值: momentum, trend, volatility, volume, moving_average, reversal, advanced, cycle, pattern, other"
      })
    ),
    show_count_only: Type.Optional(
      Type.Boolean({
        description: "是否只显示统计信息（可选，默认 false）。设为 true 时只返回各类别的因子数量"
      })
    )
  }),

  execute: async (_toolCallId, params: FactorListParams) => {
    const { category, show_count_only } = params;

    try {
      // 调用 quantsys-v2 API
      const QUANTSYS_API_URL = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = `${QUANTSYS_API_URL}/api/factors/list`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`API 请求失败: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();

      if (!result.success) {
        throw new Error(result.error || '获取因子列表失败');
      }

      const data = result.data;

      // 如果指定了分类，只返回该分类
      if (category) {
        const categoryData = data.categories[category];
        if (!categoryData) {
          return {
            content: [{
              type: "text" as const,
              text: `❌ 分类不存在: ${category}\n\n可用分类: ${Object.keys(data.categories).join(', ')}`
            }],
            details: null
          };
        }

        if (show_count_only) {
          return {
            content: [{
              type: "text" as const,
              text: `📊 ${categoryData.name}: ${categoryData.count} 个因子`
            }],
            details: { category, count: categoryData.count }
          };
        }

        return {
          content: [{
            type: "text" as const,
            text: `📁 ${categoryData.name} (${categoryData.count}个)\n\n` +
                  `因子列表:\n${categoryData.factors.map((f: string, i: number) => `${i + 1}. ${f}`).join('\n')}`
          }],
          details: categoryData
        };
      }

      // 返回全部因子
      if (show_count_only) {
        const summary = Object.entries(data.categories)
          .map(([key, value]: [string, any]) => `  • ${value.name}: ${value.count} 个`)
          .join('\n');

        return {
          content: [{
            type: "text" as const,
            text: `📊 因子统计 (总计 ${data.total} 个)\n\n${summary}`
          }],
          details: {
            total: data.total,
            counts: Object.fromEntries(
              Object.entries(data.categories).map(([k, v]: [string, any]) => [k, v.count])
            )
          }
        };
      }

      // 返回完整列表（格式化输出）
      const categorySummary = Object.entries(data.categories)
        .sort((a: any, b: any) => b[1].count - a[1].count)
        .map(([key, value]: [string, any]) => 
          `  • ${value.name}: ${value.count} 个因子\n    示例: ${value.factors.slice(0, 3).join(', ')}`
        )
        .join('\n\n');

      return {
        content: [{
          type: "text" as const,
          text: `📊 系统可用因子 (总计 ${data.total} 个)\n\n` +
                `📁 因子分类:\n\n${categorySummary}\n\n` +
                `💡 使用方式:\n` +
                `  • 查看特定分类: factor_list({ category: "momentum" })\n` +
                `  • 在策略中直接使用: df["rsi14"], df["macd"] 等`
        }],
        details: data
      };

    } catch (error) {
      return createErrorResponse(error);
    }
  }
};
