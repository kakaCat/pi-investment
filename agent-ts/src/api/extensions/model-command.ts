/**
 * /provider 斜杠命令 — LLM provider/模型热切换（人工入口）
 *
 * 通过 SDK extensionFactories 注入。命名 /provider 而非 /model，
 * 因为 SDK 内置 /model 已存在（模型选择器，不认识我们的自定义模型）。
 *
 * 切换统一走 services/llm 的 switch()：立即持久化到 llm-state.json
 * （重启保持）；当前会话立即 setModel，其他活跃会话下一轮惰性生效。
 *
 * 用法：
 *   /provider              显示当前 provider/模型/来源 与各 provider key 配置状态
 *   /provider kimi         切换到 Kimi
 *   /provider deepseek     切换到 DeepSeek（用环境变量/默认模型）
 *   /provider flash        切到 deepseek-v4-flash（便宜，日常）
 *   /provider pro          切到 deepseek-v4-pro（更强，复杂分析）
 *   /provider deepseek-v4-pro  完整模型 ID 亦可
 */

import {
  DefaultResourceLoader,
  getAgentDir,
  type ExtensionFactory,
} from "@mariozechner/pi-coding-agent";
import { getLLM } from "../../services/llm/index.js";
import { loopGuardianExtension } from "./loop-guardian.js";
import { recallExtension } from "./recall-extension.js";

export const modelCommandExtension: ExtensionFactory = (pi) => {
  pi.registerCommand("provider", {
    description: "查看或切换 LLM provider/模型（deepseek/kimi、flash/pro），切换持久化",
    handler: async (args, ctx) => {
      const target = args.trim().toLowerCase();
      const llm = getLLM();

      // 无参数：显示状态
      if (!target) {
        const st = llm.status();
        const lines = st.providers
          .map(
            (p) =>
              ` ${p.active ? "→" : " "} ${p.name}: ${p.configured ? "key 已配置" : "❌ key 未配置"}${p.active ? ` (${p.modelId})` : ""}`,
          )
          .join("\n");
        ctx.ui.notify(
          `当前: ${st.current.provider} (${st.current.modelId}) [来源: ${st.source}]\n${lines}\n切换: /provider deepseek | kimi | flash | pro`,
          "info",
        );
        return;
      }

      const result = llm.switch(target, "human");
      if (!result.ok) {
        ctx.ui.notify(`❌ ${result.error}`, "error");
        return;
      }
      if (!result.changed) {
        ctx.ui.notify(`ℹ️ 已是 ${result.to}，无需切换`, "info");
        return;
      }
      const ok = await pi.setModel(llm.getSessionModel() as any);
      if (ok) {
        ctx.ui.notify(
          `✅ 已切换 ${result.from} → ${result.to}，下一轮对话生效（已持久化，重启保持）`,
          "info",
        );
      } else {
        ctx.ui.notify(
          `⚠️ 已持久化切换（新会话将用 ${result.to}），但当前会话 setModel 未生效`,
          "warning",
        );
      }
    },
  });
};

/**
 * 构建带 /provider 命令的 ResourceLoader。
 * 与 SDK 内部默认构造参数一致（sdk.js: new DefaultResourceLoader({ cwd, agentDir, settingsManager })），
 * 仅追加 extensionFactories。SDK 只在自己创建 loader 时才调 reload()，
 * 所以这里必须自行 await reload()。
 */
export async function createAppResourceLoader(cwd: string): Promise<DefaultResourceLoader> {
  const loader = new DefaultResourceLoader({
    cwd,
    agentDir: getAgentDir(),
    extensionFactories: [modelCommandExtension, loopGuardianExtension, recallExtension],
  });
  await loader.reload();
  return loader;
}
