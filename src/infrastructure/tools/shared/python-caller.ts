/**
 * Python bridge with TypeScript fallback and caching
 *
 * 现在使用弹性调用层，带超时优化和降级策略
 */
import { callPythonResilient } from "./python-caller-resilient.js";

/**
 * 调用 Python 函数（带弹性处理）
 *
 * 特性：
 * - 分级超时（10s/30s/60s）
 * - 降级缓存（数据源失败时使用旧数据）
 * - TypeScript 原生优先
 */
export async function callPython(func: string, args: Record<string, unknown> = {}): Promise<string> {
  return callPythonResilient(func, args);
}
