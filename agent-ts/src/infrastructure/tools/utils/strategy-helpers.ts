/**
 * Strategy Helper Utilities
 *
 * 策略工具的共享辅助函数，避免代码重复
 */

/**
 * 解析策略ID或名称，自动转换数字ID为策略名称
 *
 * @param strategyIdOrName - 策略ID（数字字符串如"53"）或策略名称（如"多因子波段策略v9"）
 * @returns 策略名称
 * @throws Error 如果策略不存在
 *
 * @example
 * // 数字ID自动转换
 * const name = await resolveStrategyId("53");  // → "多因子波段策略v9"
 *
 * // 策略名称直接返回
 * const name = await resolveStrategyId("多因子波段策略v9");  // → "多因子波段策略v9"
 */
export async function resolveStrategyId(strategyIdOrName: string): Promise<string> {
  // 如果不是纯数字，直接返回（已经是策略名称）
  if (!/^\d+$/.test(strategyIdOrName)) {
    return strategyIdOrName;
  }

  // 数字ID，需要查询转换为策略名称
  try {
    const baseUrl = process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";
    const response = await fetch(`${baseUrl}/api/strategies/${strategyIdOrName}`, {
      signal: AbortSignal.timeout(5_000),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`策略ID ${strategyIdOrName} 不存在。请使用 strategy_list 查看可用策略。`);
      }
      throw new Error(`查询策略失败: HTTP ${response.status}`);
    }

    const data = (await response.json()) as any;

    if (!data.success) {
      throw new Error(data.message || data.error || "查询策略失败");
    }

    // 尝试多个字段获取策略名称
    const strategyName =
      data.data?.name ||
      data.data?.strategy_name ||
      data.data?.strategy_type ||
      data.data?.strategyType;

    if (!strategyName) {
      throw new Error(`策略ID ${strategyIdOrName} 缺少名称字段`);
    }

    console.log(`[resolveStrategyId] ID ${strategyIdOrName} → 名称 ${strategyName}`);
    return strategyName;

  } catch (error) {
    // 如果是我们抛出的错误，直接传递
    if (error instanceof Error && error.message.includes('策略ID')) {
      throw error;
    }

    // 网络或超时错误，提供友好提示
    console.warn(`[resolveStrategyId] ID转换失败: ${error}`);

    // 如果是超时错误
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new Error('查询策略超时，请检查 quantsys-v2 服务是否运行');
    }

    // 降级：继续使用原值（可能是内置策略名称恰好全是数字）
    console.warn(`[resolveStrategyId] 降级使用原始值: ${strategyIdOrName}`);
    return strategyIdOrName;
  }
}

/**
 * 批量解析策略ID列表
 *
 * @param strategyIds - 策略ID或名称列表
 * @returns 策略名称列表
 */
export async function resolveStrategyIds(strategyIds: string[]): Promise<string[]> {
  const results = await Promise.allSettled(
    strategyIds.map(id => resolveStrategyId(id))
  );

  return results.map((result, index) => {
    if (result.status === 'fulfilled') {
      return result.value;
    } else {
      console.error(`解析策略ID ${strategyIds[index]} 失败:`, result.reason);
      return strategyIds[index]; // 降级使用原值
    }
  });
}

/**
 * 获取 quantsys-v2 API 基础URL
 */
export function getQuantV2BaseUrl(): string {
  return process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";
}
