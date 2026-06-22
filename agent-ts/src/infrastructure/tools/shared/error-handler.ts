/**
 * 统一的工具错误处理包装器
 *
 * 为所有 Agent 工具提供一致的错误处理、日志记录和性能监控。
 */

import { formatErrorOutput, formatSuccessOutput } from './output-formatters.js';
import { getStatsManager } from './tool-stats-manager.js';

/**
 * Tool result type - compatible with pi-agent AgentToolResult
 */
export interface ToolResult {
  content: Array<{ type: "text"; text: string }>;
  details: any;  // Required field for SDK compatibility
}

/**
 * 日志记录器接口（可替换为实际的 logger）
 */
interface Logger {
  info(message: string, meta?: any): void;
  warn(message: string, meta?: any): void;
  error(message: string, meta?: any): void;
}

/**
 * 简单的控制台日志实现
 */
const consoleLogger: Logger = {
  info: (msg, meta) => console.log(`[INFO] ${msg}`, meta || ''),
  warn: (msg, meta) => console.warn(`[WARN] ${msg}`, meta || ''),
  error: (msg, meta) => console.error(`[ERROR] ${msg}`, meta || '')
};

let globalLogger: Logger = consoleLogger;

/**
 * 设置全局日志记录器
 */
export function setLogger(logger: Logger): void {
  globalLogger = logger;
}

/**
 * 工具执行选项
 */
export interface ToolExecutionOptions {
  /** 工具名称 */
  toolName: string;
  /** 是否启用性能监控 */
  enablePerformanceMonitoring?: boolean;
  /** 慢工具阈值（毫秒） */
  slowToolThreshold?: number;
  /** 错误建议（自定义错误提示） */
  errorSuggestion?: string;
  /** 是否在错误消息中包含参数 */
  includeParamsInError?: boolean;
}

/**
 * 工具执行统计
 */
interface ToolStats {
  totalCalls: number;
  successCalls: number;
  failureCalls: number;
  totalDuration: number;
  lastCallAt: number;
  lastError?: string;
}

/**
 * 全局工具统计存储
 */
const toolStats = new Map<string, ToolStats>();

/**
 * 获取工具统计
 */
function getStats(toolName: string): ToolStats {
  if (!toolStats.has(toolName)) {
    toolStats.set(toolName, {
      totalCalls: 0,
      successCalls: 0,
      failureCalls: 0,
      totalDuration: 0,
      lastCallAt: 0
    });
  }
  return toolStats.get(toolName)!;
}

/**
 * 导出工具统计报告
 */
export function getToolStatsReport(): Record<string, ToolStats> {
  const report: Record<string, ToolStats> = {};
  toolStats.forEach((stats, toolName) => {
    report[toolName] = { ...stats };
  });
  return report;
}

/**
 * 重置工具统计
 */
export function resetToolStats(toolName?: string): void {
  if (toolName) {
    toolStats.delete(toolName);
  } else {
    toolStats.clear();
  }
}

/**
 * 包装工具执行，提供统一的错误处理、日志和性能监控
 *
 * @param fn 工具执行函数
 * @param options 执行选项
 * @returns 包装后的工具结果
 *
 * @example
 * ```typescript
 * export const myTool = {
 *   name: "my_tool",
 *   execute: async (toolCallId, params) => {
 *     return wrapToolExecution(
 *       async () => {
 *         // 工具逻辑
 *         const result = await doSomething(params);
 *         return result;
 *       },
 *       {
 *         toolName: "my_tool",
 *         enablePerformanceMonitoring: true,
 *         errorSuggestion: "请检查参数格式是否正确"
 *       }
 *     );
 *   }
 * };
 * ```
 */
export async function wrapToolExecution<T = any>(
  fn: () => Promise<T>,
  options: ToolExecutionOptions
): Promise<ToolResult> {
  const {
    toolName,
    enablePerformanceMonitoring = true,
    slowToolThreshold = 5000,
    errorSuggestion,
    includeParamsInError = false
  } = options;

  const stats = getStats(toolName);
  stats.totalCalls++;
  stats.lastCallAt = Date.now();

  const startTime = Date.now();

  try {
    // 执行工具逻辑
    const result = await fn();

    // 记录成功
    const duration = Date.now() - startTime;
    stats.successCalls++;
    stats.totalDuration += duration;

    // 持久化统计
    getStatsManager().recordCall(toolName, true, duration);

    // 性能监控
    if (enablePerformanceMonitoring) {
      globalLogger.info(`[Performance] ${toolName}: ${duration}ms`);

      // 慢工具告警
      if (duration > slowToolThreshold) {
        globalLogger.warn(`[SlowTool] ${toolName} took ${duration}ms (threshold: ${slowToolThreshold}ms)`);
      }
    }

    // 返回成功结果
    return formatToolResult(result);

  } catch (error) {
    // 记录失败
    const duration = Date.now() - startTime;
    stats.failureCalls++;
    stats.totalDuration += duration;
    stats.lastError = error instanceof Error ? error.message : String(error);

    // 持久化统计（包含错误信息）
    getStatsManager().recordCall(toolName, false, duration, stats.lastError);

    // 记录错误日志
    globalLogger.error(`[${toolName}] 执行失败`, {
      error: stats.lastError,
      duration: `${duration}ms`
    });

    // 格式化错误消息
    const errorMessage = formatErrorOutput(error instanceof Error ? error : new Error(String(error)), {
      toolName,
      suggestion: errorSuggestion
    });

    return {
      content: [{ type: "text" as const, text: errorMessage }],
      details: {
        success: false,
        error: stats.lastError,
        toolName,
        duration
      }
    };
  }
}

/**
 * 格式化工具执行结果
 * 智能检测结果类型并返回适当的 ToolResult 格式
 */
function formatToolResult(result: any): ToolResult {
  // 如果结果已经是 ToolResult 格式，直接返回
  if (result && typeof result === 'object' && 'content' in result) {
    return result as ToolResult;
  }

  // 如果结果是字符串，包装为 ToolResult
  if (typeof result === 'string') {
    return {
      content: [{ type: "text" as const, text: result }],
      details: null
    };
  }

  // 如果结果是对象，提取 text 或序列化
  if (typeof result === 'object' && result !== null) {
    const text = result.text || result.message || JSON.stringify(result, null, 2);
    return {
      content: [{ type: "text" as const, text }],
      details: result
    };
  }

  // 其他类型，转为字符串
  return {
    content: [{ type: "text" as const, text: String(result) }],
    details: null
  };
}

/**
 * 验证必填参数
 * @param params 参数对象
 * @param requiredFields 必填字段列表
 * @throws Error 如果缺少必填参数
 */
export function validateRequiredParams(
  params: Record<string, any>,
  requiredFields: string[]
): void {
  const missingFields = requiredFields.filter(field => {
    const value = params[field];
    return value === undefined || value === null || value === '';
  });

  if (missingFields.length > 0) {
    throw new Error(
      `缺少必填参数: ${missingFields.join(', ')}。` +
      `原因：这些参数是命令执行的必要条件，不能为空。`
    );
  }
}

/**
 * 验证参数类型
 * @param params 参数对象
 * @param fieldTypes 字段类型映射
 * @throws Error 如果类型不匹配
 */
export function validateParamTypes(
  params: Record<string, any>,
  fieldTypes: Record<string, 'string' | 'number' | 'boolean' | 'array' | 'object'>
): void {
  for (const [field, expectedType] of Object.entries(fieldTypes)) {
    const value = params[field];

    if (value === undefined || value === null) {
      continue; // 跳过未提供的参数
    }

    let actualType: string;

    if (Array.isArray(value)) {
      actualType = 'array';
    } else {
      actualType = typeof value;
    }

    if (actualType !== expectedType) {
      throw new Error(
        `参数 ${field} 类型错误: 期望 ${expectedType}，实际 ${actualType}。` +
        `原因：参数类型不匹配会导致执行失败。`
      );
    }
  }
}

/**
 * 验证枚举值
 * @param params 参数对象
 * @param field 字段名
 * @param allowedValues 允许的值列表
 * @throws Error 如果值不在允许列表中
 */
export function validateEnum(
  params: Record<string, any>,
  field: string,
  allowedValues: any[]
): void {
  const value = params[field];

  if (value === undefined || value === null) {
    return; // 跳过未提供的参数
  }

  if (!allowedValues.includes(value)) {
    throw new Error(
      `参数 ${field} 的值 "${value}" 不合法。` +
      `允许的值: ${allowedValues.join(', ')}。` +
      `原因：该参数只接受预定义的枚举值。`
    );
  }
}

/**
 * 验证数值范围
 * @param params 参数对象
 * @param field 字段名
 * @param min 最小值
 * @param max 最大值
 * @throws Error 如果值超出范围
 */
export function validateRange(
  params: Record<string, any>,
  field: string,
  min?: number,
  max?: number
): void {
  const value = params[field];

  if (value === undefined || value === null) {
    return; // 跳过未提供的参数
  }

  if (typeof value !== 'number') {
    throw new Error(
      `参数 ${field} 必须是数字。原因：范围验证需要数值类型。`
    );
  }

  if (min !== undefined && value < min) {
    throw new Error(
      `参数 ${field} 的值 ${value} 小于最小值 ${min}。` +
      `原因：参数值超出有效范围，可能导致计算错误或数据异常。`
    );
  }

  if (max !== undefined && value > max) {
    throw new Error(
      `参数 ${field} 的值 ${value} 大于最大值 ${max}。` +
      `原因：参数值超出有效范围，可能导致计算错误或数据异常。`
    );
  }
}

/**
 * 组合验证器 - 链式调用多个验证
 *
 * @example
 * ```typescript
 * validateParams(params)
 *   .required(['symbol', 'strategy_id'])
 *   .types({ symbol: 'string', limit: 'number' })
 *   .enum('action', ['single', 'batch', 'pipeline'])
 *   .range('limit', 1, 100)
 *   .validate();
 * ```
 */
export class ParamsValidator {
  private params: Record<string, any>;
  private errors: string[] = [];

  constructor(params: Record<string, any>) {
    this.params = params;
  }

  required(fields: string[]): this {
    try {
      validateRequiredParams(this.params, fields);
    } catch (error) {
      this.errors.push(error instanceof Error ? error.message : String(error));
    }
    return this;
  }

  types(fieldTypes: Record<string, 'string' | 'number' | 'boolean' | 'array' | 'object'>): this {
    try {
      validateParamTypes(this.params, fieldTypes);
    } catch (error) {
      this.errors.push(error instanceof Error ? error.message : String(error));
    }
    return this;
  }

  enum(field: string, allowedValues: any[]): this {
    try {
      validateEnum(this.params, field, allowedValues);
    } catch (error) {
      this.errors.push(error instanceof Error ? error.message : String(error));
    }
    return this;
  }

  range(field: string, min?: number, max?: number): this {
    try {
      validateRange(this.params, field, min, max);
    } catch (error) {
      this.errors.push(error instanceof Error ? error.message : String(error));
    }
    return this;
  }

  /**
   * 执行验证，如果有错误则抛出异常
   */
  validate(): void {
    if (this.errors.length > 0) {
      throw new Error(this.errors.join('\n'));
    }
  }

  /**
   * 获取所有验证错误（不抛出异常）
   */
  getErrors(): string[] {
    return [...this.errors];
  }
}

/**
 * 创建参数验证器
 */
export function validateParams(params: Record<string, any>): ParamsValidator {
  return new ParamsValidator(params);
}
