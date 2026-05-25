/**
 * Algo Execute Tool - L5 执行引擎层
 *
 * 算法交易执行：TWAP/VWAP拆单
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { requireAshare } from "../shared/validators.js";
import { algoExecute } from "../../quant/quant-v2-client.js";
import { formatAlgoOrder } from "../../quant/formatters.js";

export const algoExecuteTool: ToolDefinition = {
  name: "trade_algo_execute",
  label: "算法交易",
  description:
    "L5 执行引擎工具：创建算法交易订单（TWAP/VWAP）。" +
    "TWAP（时间加权平均）：均匀拆分到时间段内，适合流动性好的股票。" +
    "VWAP（成交量加权平均）：根据历史成交量分布加权拆分，减少市场冲击。" +
    "返回订单ID和详细的拆单计划。" +
    "仅支持A股（6位数字代码）。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）"
    }),
    side: Type.Union([
      Type.Literal("buy"),
      Type.Literal("sell")
    ], {
      description: "交易方向：buy=买入, sell=卖出"
    }),
    quantity: Type.Number({
      description: "交易数量（股）"
    }),
    algo: Type.Union([
      Type.Literal("TWAP"),
      Type.Literal("VWAP")
    ], {
      description: "算法类型：TWAP=时间加权, VWAP=成交量加权"
    }),
    durationMinutes: Type.Optional(
      Type.Number({
        description: "执行时长（分钟），默认30分钟"
      })
    ),
    startTime: Type.Optional(
      Type.String({
        description: "开始时间（HH:MM:SS），默认09:30:00"
      })
    )
  }),

  execute: async (_toolCallId, params: {
    symbol: string;
    side: 'buy' | 'sell';
    quantity: number;
    algo: 'TWAP' | 'VWAP';
    durationMinutes?: number;
    startTime?: string;
  }) => {
    const { symbol, side, quantity, algo, durationMinutes, startTime } = params;

    // 验证A股代码
    const validationError = requireAshare(symbol);
    if (validationError) {
      return {
        content: [{
          type: "text" as const,
          text: validationError
        }],
        details: undefined
      };
    }

    // 验证数量
    if (quantity <= 0 || quantity % 100 !== 0) {
      return {
        content: [{
          type: "text" as const,
          text: "交易数量必须是100的整数倍"
        }],
        details: undefined
      };
    }

    try {
      const order = await algoExecute({
        symbol,
        side,
        quantity,
        algo,
        duration_minutes: durationMinutes,
        start_time: startTime
      });

      if (!order.success) {
        return {
          content: [{
            type: "text" as const,
            text: `算法订单创建失败: ${JSON.stringify(order)}`
          }],
          details: undefined
        };
      }

      // Convert AlgoOrder to AlgoOrderResult format for formatting
      const orderResult = {
        order_id: order.order_id,
        symbol: order.symbol,
        name: order.symbol, // Backend should provide name, fallback to symbol
        side: order.side,
        algo_type: order.algo,
        status: order.status,
        target_quantity: order.parent_quantity,
        filled_quantity: 0,
        remaining_quantity: order.parent_quantity,
        created_at: new Date().toISOString(),
        start_time: startTime || "09:30:00",
        end_time: calculateEndTime(startTime || "09:30:00", durationMinutes || 30),
        execution_stats: {
          total_trades: order.execution_stats.total_slices,
          avg_trade_size: order.execution_stats.avg_slice_size,
        },
        algo_params: {
          time_limit: (durationMinutes || 30) * 60,
        }
      };

      const formattedText = formatAlgoOrder(orderResult);

      return {
        content: [{
          type: "text" as const,
          text: formattedText
        }],
        details: {
          order_id: order.order_id,
          symbol: order.symbol,
          side: order.side,
          algo: order.algo,
          quantity: order.parent_quantity,
          child_orders: order.child_orders
        }
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `算法交易执行失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: { error: error instanceof Error ? error.message : String(error) }
      };
    }
  }
};

/**
 * Calculate end time based on start time and duration
 */
function calculateEndTime(startTime: string, durationMinutes: number): string {
  const [hours, minutes, seconds] = startTime.split(':').map(Number);
  const startDate = new Date();
  startDate.setHours(hours, minutes, seconds || 0);

  const endDate = new Date(startDate.getTime() + durationMinutes * 60 * 1000);

  return `${String(endDate.getHours()).padStart(2, '0')}:${String(endDate.getMinutes()).padStart(2, '0')}:${String(endDate.getSeconds()).padStart(2, '0')}`;
}
