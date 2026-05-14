/**
 * Storage Service - 统一存储层
 *
 * 合并了原 cache/ 和 memory/ 的功能：
 * - cache-service: 股票静态数据缓存
 * - memory-store: 跨会话持久化记忆（TF-IDF + 向量搜索）
 * - stock-memory-service: 股票静态信息记忆
 * - stock-decision-memory-service: 股票决策记忆
 */

export { MemoryService, memoryService } from "./cache-service.js";
export { MemoryStore, initMemoryStore, getMemoryStore } from "./memory-store.js";
export type { MemoryChunk, MemoryResult } from "./memory-store.js";
export { StockMemoryService, stockMemoryService } from "./stock-memory-service.js";
export { StockDecisionMemoryService, stockDecisionMemoryService } from "./stock-decision-memory-service.js";
