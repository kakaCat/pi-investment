/**
 * 工具响应数据持久化阈值配置
 *
 * 当工具返回数据超过阈值时，自动保存到本地文件而非直接返回给 Agent
 * 这样可以避免大数据溢出 Agent 上下文窗口
 */

export const TOOL_PERSISTENCE_THRESHOLDS = {
  // 股票池相关
  pool_validate: 50 * 1024,       // 50KB - 股票池策略验证（多策略×多股票回测结果）
  pool_scan_signals: 100 * 1024,  // 100KB - 股票池信号扫描（可能包含大量信号详情）

  // 因子分析相关
  factor_analyze: 80 * 1024,      // 80KB - 因子分析结果
  ic_monitor: 60 * 1024,          // 60KB - IC监控数据
  layering_backtest: 100 * 1024,  // 100KB - 分层回测结果
  batch_layering_backtest: 150 * 1024, // 150KB - 批量分层回测
  correlation: 40 * 1024,         // 40KB - 相关性分析

  // 回测相关
  backtest: 120 * 1024,           // 120KB - 单次回测完整结果
  combo_backtest: 150 * 1024,     // 150KB - 组合策略回测

  // 机会扫描
  opportunity_scan: 80 * 1024,    // 80KB - 机会扫描结果
  opportunity_scan_enhanced: 100 * 1024, // 100KB - 增强型机会扫描

  // 实时数据
  realtime_signal: 30 * 1024,     // 30KB - 实时信号（通常较小）
  market_snapshot: 40 * 1024,     // 40KB - 市场快照

  // 数据质量
  quality_manage: 50 * 1024,      // 50KB - 数据质量管理

  // 默认阈值
  default: 30 * 1024,             // 30KB - 未明确指定的工具使用此阈值
} as const;

/**
 * 根据工具名称获取持久化阈值
 * @param toolName 工具名称
 * @returns 阈值（字节）
 */
export function getThreshold(toolName: string): number {
  return TOOL_PERSISTENCE_THRESHOLDS[toolName as keyof typeof TOOL_PERSISTENCE_THRESHOLDS]
    ?? TOOL_PERSISTENCE_THRESHOLDS.default;
}

/**
 * 格式化阈值为可读字符串
 * @param bytes 字节数
 * @returns 格式化字符串（如 "50KB"）
 */
export function formatThreshold(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }
  return `${(bytes / 1024).toFixed(0)}KB`;
}
