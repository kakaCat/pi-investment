#!/usr/bin/env node
/**
 * Wake Channel + Agent OS Webhook 启动脚本
 * 在端口 3002 上同时提供：
 * - quantsys-v2 推送通知接收服务 (WakeAdapter)
 * - Agent OS Scheduler webhook 接收服务 (AgentOSAdapter)
 */
import "dotenv/config";
import { startGateway } from "./gateway/start-gateway.js";
import { WakeAdapter } from "./gateway/adapters/wake-adapter.js";
import { AgentOSAdapter } from "./gateway/adapters/agent-os-adapter.js";
import { initLLM } from "../services/llm/index.js";
import { paths } from "../config/config.js";

// 初始化 LLM 供给模块（state 文件 > env > 默认）
initLLM(paths.piDir);

console.log("🚀 启动 Gateway 服务 (Wake + Agent OS)...");

// 启动 Gateway，多个 adapter 共享端口 3002
const { shutdown } = await startGateway(
  [new WakeAdapter(), new AgentOSAdapter()],
  { sharedPort: 3002 }
);

console.log(`✅ Gateway 启动完成 (端口 3002)`);
console.log(`  - Wake Channel: POST /wake`);
console.log(`  - Agent OS Webhook: POST /api/webhook/agent-os/trigger`);

process.on("SIGINT", async () => { await shutdown(); process.exit(0); });
process.on("SIGTERM", async () => { await shutdown(); process.exit(0); });
