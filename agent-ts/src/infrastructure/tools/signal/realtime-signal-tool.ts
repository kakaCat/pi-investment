import type { ToolDefinition } from "../index.js";
import { Type } from '@sinclair/typebox';
import { logger } from '../../logging/index.js';

// 获取 V2 API 基础地址
const V2_API_BASE = process.env.QUANTSYS_V2_API_URL ?? 'http://127.0.0.1:5001';

/**
 * 通用 HTTP 请求辅助函数
 */
async function fetchV2Api<T>(path: string, options?: {
  method?: 'GET' | 'POST';
  body?: any;
}): Promise<T> {
  const method = options?.method ?? 'GET';
  const url = `${V2_API_BASE}${path}`;

  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return await response.json() as T;
}

/**
 * 实时信号扫描工具 - 解决"看到的都是昨天买点"的问题
 *
 * 三种模式：
 * 1. morning_scan - 早盘扫描（收盘后生成信号，次日开盘前确认）
 * 2. validate - 验证现有信号是否还能执行（检查价格偏离）
 * 3. t1_generate - 生成 T+1 信号（指定股票+策略）
 */
export const realtimeSignalTool: ToolDefinition = {
  name: 'realtime_signal_scan',
  label: '实时信号扫描',
  description: `实时信号扫描和验证工具

解决问题：消除"看到信号时已经涨上去"的困境

三种模式：
1. morning_scan - 早盘扫描（每日 9:00-9:25 使用）
   - 扫描股票池 × 策略组合
   - 过滤价格偏离过大的信号
   - 返回可执行信号列表（含执行建议）

2. validate - 验证现有信号（看到信号后立即验证）
   - 检查信号价格 vs 当前价格偏离度
   - 判断是否还能执行
   - 给出执行建议：立即买入/限价单/放弃

3. t1_generate - 生成 T+1 信号（收盘后使用）
   - 基于今日收盘数据生成信号
   - 标记次日执行
   - 适合中长期策略

使用场景：
- 早上开盘前：用 morning_scan 扫描今日机会
- 看到信号时：用 validate 检查是否还能买
- 收盘后：用 t1_generate 准备明天的执行计划`,

  parameters: Type.Object({
    mode: Type.Union([
      Type.Literal('morning_scan'),
      Type.Literal('validate'),
      Type.Literal('t1_generate')
    ], { description: '模式：morning_scan（早盘扫描）, validate（验证信号）, t1_generate（生成T+1信号）' }),
    strategy_ids: Type.Optional(Type.Array(Type.String(), { description: '策略 ID 列表（morning_scan 和 t1_generate 模式需要）' })),
    symbols: Type.Optional(Type.Array(Type.String(), { description: '股票代码列表' })),
    signals: Type.Optional(Type.Array(Type.Any(), { description: '需要验证的信号列表（validate 模式需要）' })),
    max_gap_pct: Type.Optional(Type.Number({ description: '最大可接受价格偏离（%，默认 3.0）', default: 3.0 })),
    notify: Type.Optional(Type.Boolean({ description: '是否推送通知（早盘扫描模式）', default: false }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    const { mode, strategy_ids, symbols, signals, max_gap_pct = 3.0, notify = false } = params;

    try {
      switch (mode) {
        case 'morning_scan': {
          if (!strategy_ids || !symbols) {
            return {
              content: [{
                type: "text" as const,
                text: JSON.stringify({
                  success: false,
                  error: '早盘扫描需要 strategy_ids 和 symbols 参数'
                }, null, 2)
              }],
              details: null
            };
          }

          const response = await fetchV2Api<any>('/api/realtime-signals/morning-scan', {
            method: 'POST',
            body: {
              strategy_ids,
              stock_pool: symbols,
              notify,
            },
          });

          const { data, summary } = response;

          // 格式化输出
          let output = `📊 早盘扫描完成\n\n`;
          output += `扫描股票数: ${summary!.total_scanned}\n`;
          output += `生成信号数: ${summary!.signals_generated}\n`;
          output += `可执行信号: ${summary!.executable}\n\n`;

          if (data.length > 0) {
            output += `🎯 可执行信号列表：\n\n`;
            data.forEach((signal: any, idx: number) => {
              output += `${idx + 1}. ${signal.symbol} ${signal.name || ''}\n`;
              output += `   入场价: ${signal.entry_price} 元\n`;
              output += `   当前价: ${signal.current_price} 元`;

              if (signal.price_gap_pct !== undefined) {
                const gap = signal.price_gap_pct;
                const gapIcon = gap > 0 ? '📈' : '📉';
                output += ` ${gapIcon} ${gap > 0 ? '+' : ''}${gap.toFixed(2)}%`;
              }
              output += '\n';

              output += `   执行建议: `;
              switch (signal.execution_mode) {
                case 'immediate':
                  output += '✅ 立即买入（价格合适）';
                  break;
                case 'limit_order':
                  output += '⏳ 限价单等待（略有偏离）';
                  break;
                case 'next_day':
                  output += '📅 次日开盘执行';
                  break;
                case 'skip':
                  output += '❌ 放弃（价格偏离过大）';
                  break;
              }
              output += '\n';

              if (signal.reason) {
                output += `   信号原因: ${signal.reason}\n`;
              }

              output += '\n';
            });
          } else {
            output += '暂无可执行信号\n';
          }

          return {
            content: [{ type: "text" as const, text: output }],
            details: { data, summary }
          };
        }

        case 'validate': {
          if (!signals || signals.length === 0) {
            return {
              content: [{
                type: "text" as const,
                text: JSON.stringify({
                  success: false,
                  error: 'validate 模式需要 signals 参数'
                }, null, 2)
              }],
              details: null
            };
          }

          const response = await fetchV2Api<any>('/api/realtime-signals/filter/executable', {
            method: 'POST',
            body: {
              signals,
              max_gap_pct,
              check_realtime: true,
            },
          });

          const { executable, rejected } = (response as any).data;
          const summary = response.summary;

          let output = `🔍 信号验证完成\n\n`;
          output += `总信号数: ${summary!.total}\n`;
          output += `可执行: ${summary!.executable} ✅\n`;
          output += `已拒绝: ${summary!.rejected} ❌\n\n`;

          if (executable.length > 0) {
            output += `✅ 可执行信号：\n\n`;
            executable.forEach((signal: any, idx: number) => {
              output += `${idx + 1}. ${signal.symbol} ${signal.name || ''}\n`;
              output += `   信号价: ${signal.entry_price} → 当前价: ${signal.current_price}\n`;
              output += `   偏离度: ${signal.price_gap_pct?.toFixed(2)}%\n`;
              output += `   建议: ${signal.execution_mode}\n\n`;
            });
          }

          if (rejected.length > 0) {
            output += `❌ 被拒绝的信号：\n\n`;
            rejected.forEach((signal: any, idx: number) => {
              output += `${idx + 1}. ${signal.symbol} ${signal.name || ''}\n`;
              output += `   拒绝原因: ${signal.reject_reason}\n\n`;
            });
          }

          return {
            content: [{ type: "text" as const, text: output }],
            details: { executable, rejected, summary }
          };
        }

        case 't1_generate': {
          if (!strategy_ids || !symbols) {
            return {
              content: [{
                type: "text" as const,
                text: JSON.stringify({
                  success: false,
                  error: 't1_generate 模式需要 strategy_ids 和 symbols 参数'
                }, null, 2)
              }],
              details: null
            };
          }

          const results: any[] = [];

          for (const strategy_id of strategy_ids) {
            const response = await fetchV2Api<any>('/api/realtime-signals/t1/generate', {
              method: 'POST',
              body: {
                strategy_id,
                symbols,
              },
            });

            results.push(...(response as any).data);
          }

          let output = `📅 T+1 信号生成完成\n\n`;
          output += `策略数: ${strategy_ids.length}\n`;
          output += `股票数: ${symbols.length}\n`;
          output += `生成信号: ${results.length}\n\n`;

          if (results.length > 0) {
            output += `信号列表（次日执行）：\n\n`;
            results.forEach((signal: any, idx: number) => {
              output += `${idx + 1}. ${signal.symbol} ${signal.name || ''}\n`;
              output += `   入场价: ${signal.entry_price} 元\n`;
              output += `   执行日期: ${signal.execution_date}\n`;
              output += `   生成时间: ${signal.generated_at}\n\n`;
            });
          } else {
            output += '未生成任何信号\n';
          }

          return {
            content: [{ type: "text" as const, text: output }],
            details: { results, count: results.length }
          };
        }

        default:
          return {
            content: [{
              type: "text" as const,
              text: JSON.stringify({
                success: false,
                error: `未知模式: ${mode}`
              }, null, 2)
            }],
            details: null
          };
      }
    } catch (error: any) {
      logger.error('[realtime_signal_scan] 执行失败', { error: error.message });
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: error.message || String(error)
          }, null, 2)
        }],
        details: { error: error.message }
      };
    }
  },
};
