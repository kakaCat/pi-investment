#!/usr/bin/env node
/**
 * Wake Channel 启动脚本（薄入口）
 * quantsys-v2 推送通知接收服务：WakeAdapter + Gateway
 */
import "dotenv/config";
import { startGateway } from "./gateway/start-gateway.js";
import { WakeAdapter } from "./gateway/adapters/wake-adapter.js";
import { initLLM } from "../services/llm/index.js";
import { paths } from "../config/config.js";

// 初始化 LLM 供给模块（state 文件 > env > 默认）
initLLM(paths.piDir);

console.log("🚀 启动 Wake Channel...");
const { shutdown } = await startGateway([new WakeAdapter()]);

process.on("SIGINT", async () => { await shutdown(); process.exit(0); });
process.on("SIGTERM", async () => { await shutdown(); process.exit(0); });
