#!/usr/bin/env node
/**
 * Session Memory Saver CLI - 手动测试会话记忆保存功能
 *
 * 用法：
 *   npm run memory-saver-test
 */
import { createAgentSession } from "@mariozechner/pi-coding-agent";
import { createDeepSeekModel } from "../config/config.js";
import { saveSessionMemorySync } from "../services/intelligence/session-memory-saver.js";
import { initMemoryTools } from "../infrastructure/tools/memory-tool.js";
import { join } from "path";

const piDir = join(process.cwd(), ".pi-invest");

async function main() {
  console.log("🧪 测试会话记忆保存功能\n");

  // 初始化记忆系统
  initMemoryTools(piDir);

  // 创建一个模拟的会话
  console.log("1️⃣ 创建模拟会话...");
  const session = await createAgentSession({
    cwd: process.cwd(),
    model: createDeepSeekModel(),
    systemPrompt: "You are a helpful AI assistant.",
    customTools: [],
    skills: [],
  } as any);

  // 模拟一些对话
  console.log("2️⃣ 模拟对话...\n");

  await session.prompt("我想重构 akshare-ts 模块，它现在有 1248 行代码，太大了");
  console.log("   User: 我想重构 akshare-ts 模块，它现在有 1248 行代码，太大了");

  await session.prompt("我决定将它拆分成 data/、indicators/、services/ 三层架构");
  console.log("   User: 我决定将它拆分成 data/、indicators/、services/ 三层架构");

  await session.prompt("我喜欢用 TypeScript strict mode，所有新文件都要开启");
  console.log("   User: 我喜欢用 TypeScript strict mode，所有新文件都要开启");

  await session.prompt("记得要写单元测试，测试覆盖率要达到 80% 以上");
  console.log("   User: 记得要写单元测试，测试覆盖率要达到 80% 以上\n");

  // 保存会话记忆
  console.log("3️⃣ 保存会话记忆...\n");

  try {
    await saveSessionMemorySync(session, {
      timeout: 60000,  // 60 秒超时
      verbose: true
    });

    console.log("\n✅ 会话记忆保存完成！");
    console.log("\n📂 检查记忆文件：");
    console.log(`   ${piDir}/memory/daily/`);
  } catch (error) {
    console.error("\n❌ 保存失败:", error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

main().catch(error => {
  console.error("❌ 测试失败:", error instanceof Error ? error.message : String(error));
  process.exit(1);
});
