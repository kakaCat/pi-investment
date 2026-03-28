/**
 * Tool Worker - 在独立线程中执行工具调用
 */
import { parentPort, workerData } from "worker_threads";
import { callInvestTool } from "../../infrastructure/tools/invest-tools.js";

const { toolName, params, timeout } = workerData;

const timeoutId = setTimeout(() => {
  parentPort?.postMessage({ error: `Timeout (${timeout}ms)` });
  process.exit(1);
}, timeout);

(async () => {
  try {
    const result = await callInvestTool(toolName, params);
    clearTimeout(timeoutId);
    parentPort?.postMessage({ output: result });
  } catch (error) {
    clearTimeout(timeoutId);
    const message = error instanceof Error ? error.message : String(error);
    parentPort?.postMessage({ error: message });
  }
})();
