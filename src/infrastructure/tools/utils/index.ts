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
