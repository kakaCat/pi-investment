/**
 * Framework Adapter Types
 *
 * 定义内部业务类型，与框架类型解耦
 */

// ============================================================================
// Tool 相关类型
// ============================================================================

/**
 * 内部工具参数定义
 */
export interface InternalToolParams {
  [key: string]: any;
}

/**
 * 内部工具执行函数签名（简化版）
 * 业务代码只需返回字符串，由适配器转换为框架要求的格式
 */
export type InternalToolExecute<TParams = any> = (
  params: TParams
) => Promise<string>;

/**
 * 内部工具定义
 */
export interface InternalToolDefinition<TParams = any> {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
  execute: InternalToolExecute<TParams>;
}

// ============================================================================
// API 相关类型
// ============================================================================

/**
 * Quant API 调用参数
 */
export interface QuantAPIParams {
  [key: string]: any;
}

/**
 * Quant API 响应
 */
export interface QuantAPIResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  [key: string]: any;
}

// ============================================================================
// 消息相关类型
// ============================================================================

/**
 * 内部消息类型（简化版）
 * 用于业务逻辑中的消息处理
 */
export interface InternalMessage {
  role: 'user' | 'assistant' | 'system';
  content: string | any[];
  [key: string]: any;
}
