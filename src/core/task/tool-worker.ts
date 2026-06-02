/**
 * Tool Worker - 在独立线程中执行工具调用
 *
 * 使用动态导入以支持 tsx 环境下的模块解析
 */
import { parentPort, workerData } from "worker_threads";

const { toolName, params, timeout } = workerData;

const timeoutId = setTimeout(() => {
  parentPort?.postMessage({ error: `Timeout (${timeout}ms)` });
  process.exit(1);
}, timeout);

(async () => {
  try {
    // 动态导入工具注册表（支持 tsx 环境）
    const toolsModule = await import("../../infrastructure/tools/index.js");
    const allCustomTools = toolsModule.allCustomTools;

    // 从工具注册表中查找工具
    const tool = allCustomTools.find(t => t.name === toolName);
    if (!tool) {
      throw new Error(`Tool not found: ${toolName}`);
    }

    // 创建 AbortSignal
    const abortController = new AbortController();

    // 执行工具 (5个参数: toolCallId, params, signal, onUpdate, ctx)
    const result = await tool.execute(
      "worker-call",
      params,
      abortController.signal,
      undefined, // onUpdate callback
      {} as any  // ExtensionContext (minimal mock)
    );

    clearTimeout(timeoutId);
    parentPort?.postMessage({ output: result });
  } catch (error) {
    clearTimeout(timeoutId);
    const message = error instanceof Error ? error.message : String(error);
    parentPort?.postMessage({ error: message });
  }
})();
