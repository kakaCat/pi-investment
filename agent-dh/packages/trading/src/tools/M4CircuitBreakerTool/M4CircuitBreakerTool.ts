/**
 * M4CircuitBreakerTool - M4-2 熔断检查工具
 *
 * 继承 BaseTool，实现三个必须方法：
 * 1. validate - 校验参数
 * 2. execute - 检查熔断状态并执行相应动作
 * 3. wrap - 包装返回数据
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import {
  circuitBreakerPrompt,
  CircuitBreakerCheckParams,
  CircuitBreakerCheckResult,
  CircuitBreakerStatus,
} from './prompt';

export class M4CircuitBreakerTool extends BaseTool<CircuitBreakerCheckParams, CircuitBreakerCheckResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'm4_circuit_breaker_check',
    category: 'risk',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = circuitBreakerPrompt;

  constructor(
    private qv2: QuantsysV2Client,
    private osMemory: any
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: CircuitBreakerCheckParams): ValidationResult {
    // account_name 可选，但如果提供必须是字符串
    if (args.account_name !== undefined && args.account_name !== null) {
      if (typeof args.account_name !== 'string') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'account_name',
          issue: 'account_name 必须是字符串',
          received: typeof args.account_name,
          expected: 'string',
          example: 'agent_virtual',
          guide: '请提供正确的账户名称字符串',
        };
      }

      if (args.account_name.trim() === '') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'account_name',
          issue: 'account_name 不能为空字符串',
          received: '""',
          expected: '非空字符串',
          example: 'agent_virtual',
          guide: '请提供有效的账户名称，或省略此参数使用默认账户',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(
    args: CircuitBreakerCheckParams,
    context: ToolContext
  ): Promise<CircuitBreakerCheckResult> {
    const accountName = args.account_name || 'agent_virtual';
    const now = new Date().toISOString();

    // 1. 计算 60 日最大回撤（错误兜底：API 不可用时降级为 0 不触发熔断）
    let maxDrawdown = 0;
    try {
      const riskMetrics: any = await this.qv2.getRiskMetrics({ account_name: accountName, days: 60 });
      // 2026-09-04 修复：后端 /api/risk/metrics 返回 camelCase maxDrawdown 且为小数比率
      // （-0.0772 = -7.72%）。原代码①只读 snake_case max_drawdown → undefined → 恒 0；
      // ②未做小数→百分数换算，-0.12 < -8 永不成立，熔断实际从未触发。
      // 现按 RegimePositionLimitTool 2026-08-21 E2E 规范：小数比率 ×100 → 百分数再与 -8% 阈值比较
      const raw = Number(riskMetrics?.maxDrawdown ?? riskMetrics?.max_drawdown ?? 0);
      maxDrawdown = Math.abs(raw) <= 1 ? +(raw * 100).toFixed(2) : raw;
    } catch (e: any) {
      // API 调用失败：记录错误并降级（返回 0 回撤 = 不触发熔断，避免误杀）
      const errorMsg = e.message || String(e);
      console.error(`[m4_circuit_breaker_check] getRiskMetrics 失败: ${errorMsg}`);

      // 记录故障到 osMemory 供后续排查
      try {
        await this.osMemory.write({
          title: 'M4-2 熔断检查故障',
          content: JSON.stringify({
            error: errorMsg,
            timestamp: now,
            fallback: 'max_drawdown=0（不触发熔断）',
            hint: 'quantsys-v2 后端 /api/risk/metrics 不可用，检查后端日志或用 quantsys_v2_status 诊断',
          }),
          namespace: 'risk',
          tags: ['m4', 'circuit_breaker_error', 'api_failure'],
        });
      } catch {
        /* 落库失败不再抛出，避免二次错误 */
      }

      // 返回降级结果（不触发熔断逻辑）
      return {
        checked_at: now,
        max_drawdown: 0,
        triggered: false,
        unblocked: false,
        error: errorMsg,
        actions: ['检查失败（API 不可用），降级跳过本次熔断判定'],
        circuit_breaker_status: undefined,
      };
    }

    // 2. 读取熔断状态
    let breakerStatus: CircuitBreakerStatus | null = null;
    try {
      const memResult: any = await this.osMemory.search({
        query: 'circuit_breaker_status',
        namespace: 'risk',
        top_k: 1,
      });
      if (memResult?.memories?.length > 0) {
        breakerStatus = JSON.parse(memResult.memories[0].content || '{}');
      }
    } catch {
      breakerStatus = null;
    }

    const isActive = breakerStatus?.active === true;
    const actions: string[] = [];

    // 3. 判断是否触发熔断
    if (!isActive && maxDrawdown < -8.0) {
      // 触发熔断：减仓一半 + 禁止开仓
      const positions: any[] = await this.qv2.getPositions(accountName);
      const sellActions: string[] = [];

      for (const pos of positions) {
        const sellQty = Math.floor(Number(pos.sharesAvailable ?? pos.shares_available ?? 0) / 2 / 100) * 100; // 一半数量取整到百股（client mapPosition 字段为 camelCase sharesAvailable）
        if (sellQty >= 100) {
          try {
            await this.qv2.executeTrade({
              account_name: accountName,
              action: 'sell',
              symbol: pos.symbol,
              quantity: sellQty,
              reason: `M4-2 熔断自动减仓：60日回撤 ${maxDrawdown.toFixed(2)}%`,
            });
            sellActions.push(`卖出 ${pos.symbol} ${sellQty}股`);
          } catch (e: any) {
            sellActions.push(`卖出 ${pos.symbol} 失败: ${e.message}`);
          }
        }
      }

      // 更新熔断状态
      breakerStatus = {
        active: true,
        triggered_at: now,
        triggered_drawdown: maxDrawdown,
        actions_taken: sellActions,
        unblock_condition: '60日回撤修复到 <8%',
        checked_at: now,
      };

      await this.osMemory.write({
        title: 'M4-2 熔断状态',
        content: JSON.stringify(breakerStatus),
        namespace: 'risk',
        tags: ['m4', 'circuit_breaker_status', 'active'],
      });

      actions.push(...sellActions, '熔断激活：禁止新开仓');

      // 飞书高优告警（记录到 osMemory）
      await this.osMemory.write({
        title: 'M4-2 熔断触发告警',
        content:
          `⚠️ 组合回撤熔断已触发\n\n` +
          `- 60日最大回撤: ${maxDrawdown.toFixed(2)}%\n` +
          `- 触发时间: ${now}\n` +
          `- 执行动作: 减仓一半\n` +
          `- 减仓明细: ${sellActions.join(', ')}\n` +
          `- 状态: 禁止新开仓\n` +
          `- 解除条件: 60日回撤修复到 <8%`,
        namespace: 'notification',
        tags: ['m4', 'circuit_breaker_alert', 'high_priority'],
      });

      return {
        checked_at: now,
        max_drawdown: maxDrawdown,
        triggered: true,
        unblocked: false,
        actions,
        circuit_breaker_status: breakerStatus ?? undefined,
      };
    }

    // 4. 判断是否解除熔断
    if (isActive && maxDrawdown >= -8.0) {
      // 解除熔断
      breakerStatus = {
        ...breakerStatus!,
        active: false,
        unblocked_at: now,
        checked_at: now,
      };

      await this.osMemory.write({
        title: 'M4-2 熔断状态（已解除）',
        content: JSON.stringify(breakerStatus),
        namespace: 'risk',
        tags: ['m4', 'circuit_breaker_status', 'unblocked'],
      });

      actions.push('熔断解除：恢复允许开仓');

      return {
        checked_at: now,
        max_drawdown: maxDrawdown,
        triggered: false,
        unblocked: true,
        actions,
        circuit_breaker_status: breakerStatus ?? undefined,
      };
    }

    // 5. 无变化
    return {
      checked_at: now,
      max_drawdown: maxDrawdown,
      triggered: false,
      unblocked: false,
      actions: [
        '无变化：' +
          (isActive
            ? `熔断激活中（${maxDrawdown.toFixed(2)}%，仍需修复）`
            : `无熔断（${maxDrawdown.toFixed(2)}%）`),
      ],
      circuit_breaker_status: breakerStatus ?? undefined,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: CircuitBreakerCheckResult, context: ToolContext): ToolResponse<CircuitBreakerCheckResult> {
    // 检查必需字段
    const requiredFields = ['checked_at', 'max_drawdown', 'triggered', 'unblocked', 'actions'];
    const missingFields: string[] = [];

    for (const field of requiredFields) {
      if (result[field as keyof CircuitBreakerCheckResult] === undefined) {
        missingFields.push(field);
      }
    }

    if (missingFields.length > 0) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: missingFields.join(', '),
          issue: `返回数据缺少必需字段`,
          expected: `包含所有必需字段: ${requiredFields.join(', ')}`,
          guide: '这是内部错误，请联系开发者检查返回值',
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}
