#!/usr/bin/env node
/**
 * Wake Channel 启动脚本
 *
 * 用于启动 quantsys-v2 推送通知接收服务
 */
import { config } from "dotenv";
import { startWakeChannel } from "./wake-channel.js";

// 加载环境变量
config();

const PORT = process.env.WAKE_CHANNEL_PORT ? parseInt(process.env.WAKE_CHANNEL_PORT) : 3001;

console.log("🚀 启动 Wake Channel...");

const { shutdown } = startWakeChannel(PORT);

// 优雅关闭
process.on('SIGINT', () => {
  console.log('\n📴 收到 SIGINT 信号，正在关闭...');
  shutdown();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n📴 收到 SIGTERM 信号，正在关闭...');
  shutdown();
  process.exit(0);
});
