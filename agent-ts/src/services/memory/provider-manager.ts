/**
 * Memory Provider Manager - 单例管理和降级策略
 *
 * 设计要点：
 * - 优先使用 AgentOSMemoryProvider（走 agent 侧 agent-os 记忆通道）
 * - agent-os 不可用时降级到 FileFallbackProvider
 * - 全局单例，会话开始时初始化一次
 *
 * 2026-10-05 · REQ-261004202231-bb99：原首选 V2MemoryProvider（quantsys-v2 记忆端点）
 * 已随 v2 记忆子系统下线一并删除；记忆统一走 agent-os。
 */

import type { MemoryProvider } from './port.js';
import { AgentOSMemoryProvider } from './agent-os-provider.js';
import { FileFallbackProvider } from './file-fallback.js';
import { join } from 'path';

let memoryProvider: MemoryProvider | null = null;
let initialized = false;

/**
 * 初始化 Memory Provider（会话开始时调用一次）
 *
 * 降级策略：
 * 1. 尝试 AgentOSMemoryProvider（走 agent-os）
 * 2. 不可用时降级到 FileFallbackProvider
 *
 * `forceFallback` 是**测试用接缝**：置 true 时跳过首选 provider，直接验证文件降级路径。
 */
export async function initMemoryProvider(options: {
  sessionId: string;
  sessionKind?: string;
  channel?: string;
  workspace?: string;
  piDir?: string;
  forceFallback?: boolean;
}): Promise<MemoryProvider> {
  if (initialized && memoryProvider) {
    return memoryProvider;
  }

  const { sessionId, sessionKind, channel, workspace, piDir, forceFallback } = options;

  // 尝试 AgentOSMemoryProvider
  if (!forceFallback) {
    const aosProvider = new AgentOSMemoryProvider();
    if (aosProvider.isAvailable()) {
      try {
        await aosProvider.initialize(sessionId, { sessionKind, channel, workspace });

        // 健康检查：测试一次搜索
        await aosProvider.query('_health_check_', { limit: 1 });

        memoryProvider = aosProvider;
        initialized = true;
        console.log('✅ Memory Provider: agent-os');
        return memoryProvider;
      } catch (error) {
        console.warn(`⚠️  AgentOSMemoryProvider 不可用，降级到文件存储: ${error}`);
      }
    }
  }

  // 降级到 FileFallbackProvider
  const piDirPath = piDir || join(process.cwd(), '.pi-invest');
  const fileProvider = new FileFallbackProvider(piDirPath);
  await fileProvider.initialize(sessionId, { sessionKind, channel, workspace });

  memoryProvider = fileProvider;
  initialized = true;
  console.log('✅ Memory Provider: file-fallback (local storage)');
  return memoryProvider;
}

/**
 * 获取当前 Memory Provider（必须先调用 initMemoryProvider）
 */
export function getMemoryProvider(): MemoryProvider {
  if (!memoryProvider) {
    throw new Error('MemoryProvider not initialized. Call initMemoryProvider() first.');
  }
  return memoryProvider;
}

/**
 * 重置 Memory Provider（测试用）
 */
export function resetMemoryProvider(): void {
  memoryProvider = null;
  initialized = false;
}
