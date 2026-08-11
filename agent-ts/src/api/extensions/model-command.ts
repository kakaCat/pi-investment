/**
 * /provider 斜杠命令 — LLM provider/模型热切换（人工入口）
 *
 * 通过 SDK extensionFactories 注入。命名 /provider 而非 /model，
 * 因为 SDK 内置 /model 已存在（模型选择器，不认识我们的自定义模型）。
 *
 * 用法：
 *   /provider              显示当前 provider/模型 与各 provider key 配置状态
 *   /provider kimi         切换到 Kimi（当前会话立即生效 + 未来新会话）
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
import {
  createModel,
  getActiveProvider,
  getActiveModelId,
  resolveModelTarget,
} from "../../config/config.js";
import {
  setRuntimeProvider,
  setRuntimeModelOverride,
  isProviderConfigured,
  listProviders,
  logSwitch,
  type RuntimeProviderName,
} from "../../config/model-switcher.js";
import { loopGuardianExtension } from "./loop-guardian.js";

const PROVIDERS: RuntimeProviderName[] = ["deepseek", "kimi"];
const MODEL_HINTS = ["flash", "pro", "deepseek-v4-flash", "deepseek-v4-pro"];

export const modelCommandExtension: ExtensionFactory = (pi) => {
  pi.registerCommand("provider", {
    description: "查看或切换 LLM provider/模型（deepseek/kimi、flash/pro）",
    handler: async (args, ctx) => {
      const target = args.trim().toLowerCase();

      // 无参数：显示状态
      if (!target) {
        const current = getActiveProvider();
        const lines = listProviders()
          .map((p) => ` ${p.name === current ? "→" : " "} ${p.name}: ${p.configured ? "key 已配置" : "❌ key 未配置"}`)
          .join("\n");
        ctx.ui.notify(
          `当前: ${current} (${getActiveModelId()})\n${lines}\n切换: /provider ${[...PROVIDERS, ...MODEL_HINTS].join(" | ")}`,
          "info"
        );
        return;
      }

      // 模型粒度目标（flash/pro/deepseek-v4-pro 等）
      const modelTarget = resolveModelTarget(target);
      if (modelTarget) {
        const currentModel = getActiveModelId();
        if (modelTarget.provider === getActiveProvider() && modelTarget.modelId === currentModel) {
          ctx.ui.notify(`ℹ️ 已是 ${modelTarget.modelId}，无需切换`, "info");
          return;
        }
        if (!isProviderConfigured(modelTarget.provider)) {
          ctx.ui.notify(`❌ ${modelTarget.provider} 的 API key 未配置（检查 .env）`, "error");
          return;
        }
        setRuntimeModelOverride(modelTarget.provider, modelTarget.modelId);
        const model = createModel();
        const ok = await pi.setModel(model);
        if (ok) {
          logSwitch(currentModel, modelTarget.modelId, "human");
          ctx.ui.notify(`✅ 已切换模型 ${currentModel} → ${model.id}，下一轮对话生效`, "info");
        } else {
          ctx.ui.notify(
            `⚠️ 运行时状态已切换（新会话将用 ${modelTarget.modelId}），但当前会话 setModel 未生效`,
            "warning"
          );
        }
        return;
      }

      // provider 粒度目标
      if (!PROVIDERS.includes(target as RuntimeProviderName)) {
        ctx.ui.notify(
          `❌ 未知目标 "${target}"，可选：${[...PROVIDERS, ...MODEL_HINTS].join(", ")}`,
          "error"
        );
        return;
      }

      const current = getActiveProvider();
      if (target === current) {
        ctx.ui.notify(`ℹ️ 已是 ${target}（${getActiveModelId()}），无需切换`, "info");
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
    extensionFactories: [modelCommandExtension, loopGuardianExtension],
  });
  await loader.reload();
  return loader;
}
