/**
 * Tool Adapter
 *
 * 将内部简化的 Tool 定义转换为框架要求的 ToolDefinition
 * 处理 execute 签名和返回类型的适配
 */

import type { ToolDefinition, AgentToolResult } from "../../../sdk-facade.js";
import type { InternalToolDefinition } from './types.js';

/**
 * 创建框架兼容的 Tool 定义
 *
 * @param internalTool 内部简化的工具定义
 * @returns 框架要求的 ToolDefinition
 *
 * @example
 * ```typescript
 * const myTool = createTool({
 *   name: 'my_tool',
 *   description: 'Does something',
 *   parameters: { type: 'object', properties: { ... } },
 *   execute: async (params) => {
 *     // 业务逻辑
 *     return "结果字符串";
 *   }
 * });
 * ```
 */
export function createTool<TParams = any>(
  internalTool: InternalToolDefinition<TParams>
): ToolDefinition {
  return {
    name: internalTool.name,
    description: internalTool.description,
    parameters: internalTool.parameters,

    // 适配 execute 签名：
    // 内部: (params) => Promise<string>
    // 框架: (toolCallId, params, signal, onUpdate, ctx) => Promise<AgentToolResult>
    execute: async (
      _toolCallId: string,
      params: TParams,
      _signal?: AbortSignal,
      _onUpdate?: any,
      _ctx?: any
    ): Promise<AgentToolResult<any>> => {
      try {
        // 调用内部简化的 execute
        const result = await internalTool.execute(params);

        // 转换为框架要求的 AgentToolResult 格式
        return {
          content: [{ type: 'text' as const, text: result }],
          details: {}
        };
      } catch (error) {
        // 错误处理
        const errorMessage = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: 'text' as const, text: `❌ 执行失败: ${errorMessage}` }],
          details: { error: errorMessage }
        };
      }
    }
  } as unknown as ToolDefinition;
}

/**
 * 批量创建工具定义
 */
export function createTools(
  internalTools: InternalToolDefinition[]
): ToolDefinition[] {
  return internalTools.map(tool => createTool(tool));
}
