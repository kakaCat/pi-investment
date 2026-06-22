/**
 * Agent Error Handler - 统一错误处理策略
 *
 * 职责：
 * - 定义统一的错误严重级别
 * - 提供一致的错误处理方法
 * - 支持错误日志记录和上报
 */

export enum ErrorSeverity {
  /** 静默处理，不输出日志，返回默认值 */
  SILENT = 'silent',
  /** 打印警告，继续执行 */
  WARNING = 'warning',
  /** 打印错误，记录日志，但尝试恢复 */
  RECOVERABLE = 'recoverable',
  /** 严重错误，打印并重新抛出 */
  FATAL = 'fatal'
}

export interface ErrorContext {
  /** 错误发生的上下文描述 */
  context: string;
  /** 错误严重级别 */
  severity: ErrorSeverity;
  /** 是否记录完整堆栈 */
  logStack?: boolean;
  /** 额外的元数据 */
  metadata?: Record<string, any>;
}

/**
 * 统一的错误处理函数
 */
export function handleAgentError(
  error: unknown,
  options: ErrorContext
): void {
  const { context, severity, logStack = false, metadata } = options;
  const message = error instanceof Error ? error.message : String(error);
  const stack = error instanceof Error ? error.stack : undefined;

  const prefix = getErrorPrefix(severity);
  const fullMessage = `${prefix} [${context}] ${message}`;

  switch (severity) {
    case ErrorSeverity.SILENT:
      // 不输出任何内容
      break;

    case ErrorSeverity.WARNING:
      console.warn(fullMessage);
      if (metadata) {
        console.warn('  Metadata:', metadata);
      }
      break;

    case ErrorSeverity.RECOVERABLE:
      console.error(fullMessage);
      if (metadata) {
        console.error('  Metadata:', metadata);
      }
      if (logStack && stack) {
        console.error('  Stack:', stack);
      }
      // 可以在这里添加错误上报逻辑
      break;

    case ErrorSeverity.FATAL:
      console.error(fullMessage);
      if (metadata) {
        console.error('  Metadata:', metadata);
      }
      if (stack) {
        console.error('  Stack:', stack);
      }
      throw error;
  }
}

/**
 * 获取错误前缀
 */
function getErrorPrefix(severity: ErrorSeverity): string {
  switch (severity) {
    case ErrorSeverity.SILENT:
      return '';
    case ErrorSeverity.WARNING:
      return '⚠️';
    case ErrorSeverity.RECOVERABLE:
      return '❌';
    case ErrorSeverity.FATAL:
      return '💥';
  }
}

/**
 * 错误处理装饰器（用于函数）
 */
export function withErrorHandling<T extends (...args: any[]) => any>(
  fn: T,
  context: string,
  severity: ErrorSeverity = ErrorSeverity.RECOVERABLE,
  defaultValue?: ReturnType<T>
): T {
  return ((...args: Parameters<T>) => {
    try {
      return fn(...args);
    } catch (error) {
      handleAgentError(error, { context, severity });
      return defaultValue;
    }
  }) as T;
}

/**
 * 异步错误处理装饰器
 */
export function withAsyncErrorHandling<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context: string,
  severity: ErrorSeverity = ErrorSeverity.RECOVERABLE,
  defaultValue?: Awaited<ReturnType<T>>
): T {
  return (async (...args: Parameters<T>) => {
    try {
      return await fn(...args);
    } catch (error) {
      handleAgentError(error, { context, severity });
      return defaultValue;
    }
  }) as T;
}

/**
 * 常用错误处理快捷方法
 */
export const ErrorHandlers = {
  /** 静默处理，返回默认值 */
  silent: <T>(error: unknown, context: string, defaultValue: T): T => {
    handleAgentError(error, { context, severity: ErrorSeverity.SILENT });
    return defaultValue;
  },

  /** 打印警告，返回默认值 */
  warn: <T>(error: unknown, context: string, defaultValue: T): T => {
    handleAgentError(error, { context, severity: ErrorSeverity.WARNING });
    return defaultValue;
  },

  /** 打印错误，返回默认值 */
  recover: <T>(error: unknown, context: string, defaultValue: T): T => {
    handleAgentError(error, { context, severity: ErrorSeverity.RECOVERABLE, logStack: true });
    return defaultValue;
  },

  /** 打印错误并重新抛出 */
  fatal: (error: unknown, context: string): never => {
    handleAgentError(error, { context, severity: ErrorSeverity.FATAL });
    throw error; // TypeScript 需要这个，虽然永远不会执行到
  }
};
