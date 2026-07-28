/**
 * 工具结果持久化和响应处理模块
 *
 * 提供统一的数据持久化接口和工具响应处理器
 */

// 持久化相关
export {
  ToolResultPersister,
  toolResultPersister,
  saveToolResult,
  readToolResult,
  cleanupOldResults,
  listToolResults,
  type PersistedResult,
  type SaveOptions,
} from './result-persister.js';

// 响应处理相关
export {
  handleToolResponse,
  createErrorResponse,
  wrapToolExecution,
  type ToolResponseOptions,
  type ToolResponse,
} from './tool-response-handler.js';

/**
 * 深度转换对象键名 camelCase → snake_case。
 *
 * quantsys-v2 的 api_response 统一用 convert_keys_to_camel 序列化响应，
 * 而多数工具 formatter 按 snake_case 契约编写——在 formatter 入口处
 * 对 rawData 调用一次本函数即可两侧兼容（已是 snake 的键不受影响）。
 */
export function snakeize<T = any>(input: any): T {
  if (Array.isArray(input)) {
    return input.map((item) => snakeize(item)) as unknown as T;
  }
  if (input !== null && typeof input === 'object') {
    const out: Record<string, any> = {};
    for (const [key, value] of Object.entries(input)) {
      const snakeKey = key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
      out[snakeKey] = snakeize(value);
    }
    return out as T;
  }
  return input as T;
}
