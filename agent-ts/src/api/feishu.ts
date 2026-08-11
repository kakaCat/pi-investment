/**
 * 飞书 Bot 入口
 * - 被 src/api/index.ts 引用：startFeishuBot() 在 dev 主进程内启动
 * - 被 `npm run feishu` 直接执行：standalone 模式
 */
import "dotenv/config";
import { pathToFileURL } from "url";
import { startGateway, type GatewayHandle } from "./gateway/start-gateway.js";
import { FeishuAdapter } from "./gateway/adapters/feishu-adapter.js";
import { initLLM } from "../services/llm/index.js";
import { paths } from "../config/config.js";

// 初始化 LLM 供给模块（幂等；经 api/index.ts 启动时已初始化则直接复用）
initLLM(paths.piDir);

export interface FeishuBotHandle {
  shutdown: () => Promise<void>;
}

export async function startFeishuBot(): Promise<FeishuBotHandle | null> {
  const appId = process.env.FEISHU_APP_ID;
  const appSecret = process.env.FEISHU_APP_SECRET;

  if (!appId || !appSecret) {
    console.warn("⚠️ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET，飞书 Bot 未启动");
    return null;
  }

  const handle: GatewayHandle = await startGateway([new FeishuAdapter({ appId, appSecret })]);
  return { shutdown: handle.shutdown };
}

// standalone 模式：npm run feishu → tsx src/api/feishu.ts
const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  console.log("🚀 启动飞书 Bot...");
  const bot = await startFeishuBot();
  if (!bot) {
    process.exit(1);
  }
  process.on("SIGINT", async () => { await bot.shutdown(); process.exit(0); });
  process.on("SIGTERM", async () => { await bot.shutdown(); process.exit(0); });
}
