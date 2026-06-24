/**
 * 统一工具响应处理器
 *
 * 整合格式化 + 持久化逻辑，提供统一的工具返回处理
 */

import { saveToolResult, type PersistedResult } from './result-persister.js';

/**
 * 工具响应选项
 */
export interface ToolResponseOptions {
  toolName: string;
  data: any;
  formatter?: (data: any) => string;
  metadata?: Record<string, any>;
  threshold?: number; // 数据大小阈值（字节），超过此值自动持久化
}

/**
 * 标准工具响应格式
 */
export interface ToolResponse {
  content: Array<{ type: 'text'; text: string }>;
  details: any; // 必须存在，但可以为 null
}

/**
 * 统一处理工具响应
 *
 * 根据数据大小自动决定：
 * - 小数据：格式化后直接返回
 * - 大数据：保存到文件，返回文件路径 + 摘要
 *
 * @param options 响应选项
 * @returns 标准工具响应
 */
export async function handleToolResponse(
  options: ToolResponseOptions
): Promise<ToolResponse> {
  const {
    toolName,
    data,
    formatter,
    metadata,
    threshold = 30 * 1024, // 默认 30KB
  } = options;

  // 计算数据大小
  const dataSize = JSON.stringify(data).length;

  if (dataSize > threshold) {
    // 大数据：持久化
    const formattedSummary = formatter ? formatter(data) : undefined;
    const persisted = await saveToolResult({
      toolName,
      data,
      summary: formattedSummary,
      metadata,
    });

    return {
      content: [{ type: 'text', text: persisted.message }],
      details: { ...data, _persisted: true, _filePath: persisted.filePath },
    };
  } else {
    // 小数据：格式化后直接返回
    const formattedText = formatter
      ? formatter(data)
      : JSON.stringify(data, null, 2);

    return {
      content: [{ type: 'text', text: formattedText }],
      details: data,
    };
  }
}

/**
 * 创建错误响应
 */
export function createErrorResponse(error: unknown): ToolResponse {
  const errorMsg = error instanceof Error ? error.message : String(error);
  return {
    content: [{ type: 'text', text: `执行失败: ${errorMsg}` }],
    details: null,
  };
}

/**
 * 工具执行包装器
 *
 * 统一处理工具执行、错误捕获、响应格式化和持久化
 *
 * @example
 * ```ts
 * export const myTool: ToolDefinition = {
 *   name: 'my_tool',
 *   execute: wrapToolExecution({
 *     toolName: 'my_tool',
 *     formatter: formatMyData,
 *     threshold: 50 * 1024, // 50KB
 *   }, async (params) => {
 *     const data = await fetchData(params);
 *     return { data, metadata: { param1: params.param1 } };
 *   })
 * };
 * ```
 */
export function wrapToolExecution<TParams, TData>(
  options: Omit<ToolResponseOptions, 'data' | 'metadata'>,
  executor: (
    params: TParams
  ) => Promise<{ data: TData; metadata?: Record<string, any> }>
) {
  return async (
    _toolCallId: string,
    params: TParams
  ): Promise<ToolResponse> => {
    try {
      const result = await executor(params);
      return handleToolResponse({
        ...options,
        data: (result as any).data,
        metadata: result.metadata,
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  };
}
