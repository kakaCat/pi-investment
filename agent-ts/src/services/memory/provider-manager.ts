/**
 * Memory Provider Manager - 单例管理和降级策略
 *
 * 设计要点：
 * - 优先使用 V2MemoryProvider（走 quantsys-v2 API）
 * - v2 不可用时降级到 FileFallbackProvider
 * - 全局单例，会话开始时初始化一次
 */

import type { MemoryProvider } from './port.js';
import { V2MemoryProvider } from './v2-client.js';
import { FileFallbackProvider } from './file-fallback.js';
import { join } from 'path';

let memoryProvider: MemoryProvider | null = null;
let initialized = false;

/**
 * 初始化 Memory Provider（会话开始时调用一次）
 *
 * 降级策略：
 * 1. 尝试 V2MemoryProvider（走 quantsys-v2 API）
 * 2. v2 不可用时降级到 FileFallbackProvider
 */
export async function initMemoryProvider(options: {
  sessionId: string;
  sessionKind?: string;
  channel?: string;
  workspace?: string;
  piDir?: string;
  v2BaseUrl?: string;
}): Promise<MemoryProvider> {
  if (initialized && memoryProvider) {
    return memoryProvider;
  }

  const { sessionId, sessionKind, channel, workspace, piDir, v2BaseUrl } = options;

  // 尝试 V2MemoryProvider
  const v2Provider = new V2MemoryProvider(v2BaseUrl);
  if (v2Provider.isAvailable()) {
    try {
      await v2Provider.initialize(sessionId, { sessionKind, channel, workspace });

      // 健康检查：测试一次搜索
      await v2Provider.query('_health_check_', { limit: 1 });

      memoryProvider = v2Provider;
      initialized = true;
      console.log('✅ Memory Provider: v2-memory (quantsys-v2 API)');
      return memoryProvider;
    } catch (error) {
      console.warn(`⚠️  V2MemoryProvider 不可用，降级到文件存储: ${error}`);
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
