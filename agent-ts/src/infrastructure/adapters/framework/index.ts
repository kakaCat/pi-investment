/**
 * Framework Adapter Layer
 *
 * 统一导出框架适配层的所有功能
 * 隔离框架依赖，便于未来框架升级时集中修改
 */

// 类型定义
export type {
  InternalToolParams,
  InternalToolExecute,
  InternalToolDefinition,
  QuantAPIParams,
  QuantAPIResponse,
  InternalMessage
} from './types.js';

// Tool 适配器
export {
  createTool,
  createTools
} from './tool-adapter.js';

// API 适配器
export {
  callQuantAPI,
  callQuantCommand
} from './api-adapter.js';

// 消息适配器
export {
  toAgentMessage,
  fromAgentMessage,
  toAgentMessages,
  fromAgentMessages,
  isValidMessageArray,
  ensureAgentMessages
} from './message-adapter.js';
