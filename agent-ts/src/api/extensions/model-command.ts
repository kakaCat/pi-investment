/**
 * /provider 斜杠命令 — LLM provider 热切换（人工入口）
 *
 * 通过 SDK extensionFactories 注入。命名 /provider 而非 /model，
 * 因为 SDK 内置 /model 已存在（模型选择器，不认识我们的自定义模型）。
 *
 * 用法：
 *   /provider            显示当前 provider 与各 provider key 配置状态
 *   /provider kimi       切换到 Kimi（当前会话立即生效 + 未来新会话）
 *   /provider deepseek   切换到 DeepSeek
 */

import {
  DefaultResourceLoader,
  getAgentDir,
  type ExtensionFactory,
} from "@mariozechner/pi-coding-agent";
import {
  createModel,
  getActiveProvider,
  getActiveModelId,
} from "../../config/config.js";
import {
  setRuntimeProvider,
  isProviderConfigured,
  listProviders,
  logSwitch,
  type RuntimeProviderName,
} from "../../config/model-switcher.js";

const PROVIDERS: RuntimeProviderName[] = ["deepseek", "kimi"];

export const modelCommandExtension: ExtensionFactory = (pi) => {
  pi.registerCommand("provider", {
    description: "查看或切换 LLM provider（deepseek/kimi）",
    handler: async (args, ctx) => {
      const target = args.trim();

      // 无参数：显示状态
      if (!target) {
        const current = getActiveProvider();
        const lines = listProviders()
          .map((p) => ` ${p.name === current ? "→" : " "} ${p.name}: ${p.configured ? "key 已配置" : "❌ key 未配置"}`)
          .join("\n");
        ctx.ui.notify(`当前 provider: ${current} (${getActiveModelId()})\n${lines}`, "info");
        return;
      }

      if (!PROVIDERS.includes(target as RuntimeProviderName)) {
        ctx.ui.notify(`❌ 未知 provider "${target}"，可选：${PROVIDERS.join(", ")}`, "error");
        return;
      }

      const current = getActiveProvider();
      if (target === current) {
        ctx.ui.notify(`ℹ️ 已是 ${target}，无需切换`, "info");
        return;
      }

      if (!isProviderConfigured(target as RuntimeProviderName)) {
        ctx.ui.notify(`❌ ${target} 的 API key 未配置（检查 .env 的 ${target.toUpperCase()}_API_KEY）`, "error");
        return;
      }

      setRuntimeProvider(target as RuntimeProviderName);
      const model = createModel();
      const ok = await pi.setModel(model);
      if (ok) {
        logSwitch(current, target, "human");
        ctx.ui.notify(`✅ 已切换 ${current} → ${target} (${model.id})，下一轮对话生效`, "info");
      } else {
        ctx.ui.notify(
          `⚠️ 运行时状态已切换（新会话将用 ${target}），但当前会话 setModel 未生效`,
          "warning"
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
    extensionFactories: [modelCommandExtension],
  });
  await loader.reload();
  return loader;
}
