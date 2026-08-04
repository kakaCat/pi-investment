/**
 * model_switch — LLM provider/模型热切换工具（agent 自主入口）
 *
 * 当当前模型持续报错（429 限流 / 超时 / 5xx）时，agent 可调用本工具
 * 切换到备用 provider；也可在同 provider 内切换模型档位
 * （如 deepseek-v4-flash ↔ deepseek-v4-pro：日常用 flash 省钱，
 * 复杂分析用 pro 提质量）。
 *
 * 生效范围（重要）：只设置进程级运行时状态，对之后新建的会话
 * （定时任务唤醒、subagent、下一个人工会话）立即生效；
 * 当前正在运行的会话保持原模型直到结束——工具拿不到 session 句柄，
 * 无法调 setModel。人工要立即切当前会话请用 /provider 命令。
 *
 * 防抖动：滚动 1 小时窗口内最多切换 3 次。
 */

import type { ToolDefinition } from "../index.js";
import { getActiveProvider, getActiveModelId, createModel, resolveModelTarget } from "../../../config/config.js";
import {
  setRuntimeProvider,
  setRuntimeModelOverride,
  isProviderConfigured,
  logSwitch,
  type RuntimeProviderName,
} from "../../../config/model-switcher.js";

const WINDOW_MS = 60 * 60 * 1000;
const MAX_SWITCHES_PER_WINDOW = 3;
const switchTimestamps: number[] = [];

/** 仅测试使用：清空切换历史 */
export function resetSwitchHistoryForTests(): void {
  switchTimestamps.length = 0;
}

const PROVIDERS: RuntimeProviderName[] = ["deepseek", "kimi"];
const MODEL_TARGETS = ["flash", "pro", "deepseek-v4-flash", "deepseek-v4-pro", "kimi-k3"];

export const modelSwitchTool: ToolDefinition = {
  name: "model_switch",
  description:
    "切换 LLM provider 或模型档位。当当前模型持续报错（429 限流、超时、5xx）时切备用 provider；" +
    "也可在 deepseek 内切档位：flash（便宜，日常任务）↔ pro（更强，复杂分析）。" +
    "注意：仅对之后新建的会话生效（定时任务、subagent），当前会话继续用原模型直到结束；" +
    "如需本会话立即切换，请提示用户使用 /provider 命令。1 小时内最多切换 3 次。",
  parameters: {
    type: "object",
    properties: {
      provider: {
        type: "string",
        enum: [...PROVIDERS, ...MODEL_TARGETS],
        description:
          "切换目标：provider（deepseek/kimi）或模型（flash/pro/deepseek-v4-flash/deepseek-v4-pro/kimi-k3）",
      },
    },
    required: ["provider"],
  },
  execute: async (_toolCallId, params) => {
    const { provider } = params as { provider: string };
    const fail = (msg: string) => ({
      content: [{ type: "text" as const, text: msg }],
      details: { error: msg },
    });

    const current = getActiveProvider();

    // 防抖动（provider 与模型切换共用同一窗口）
    const checkFlap = (): string | null => {
      const now = Date.now();
      const recent = switchTimestamps.filter((t) => now - t < WINDOW_MS);
      if (recent.length >= MAX_SWITCHES_PER_WINDOW) {
        return (
          `❌ 切换过于频繁：1 小时内已切换 ${recent.length} 次（上限 ${MAX_SWITCHES_PER_WINDOW}）。` +
          `请提示用户人工排查（/provider 命令不受此限制）。`
        );
      }
      switchTimestamps.push(now);
      return null;
    };

    // 模型粒度目标（flash/pro/deepseek-v4-pro 等）
    const modelTarget = resolveModelTarget(provider);
    if (modelTarget) {
      const currentModel = getActiveModelId();
      if (modelTarget.provider === current && modelTarget.modelId === currentModel) {
        return {
          content: [{ type: "text" as const, text: `ℹ️ 已是 ${modelTarget.modelId}，无需切换。` }],
          details: { provider: current, modelId: currentModel, changed: false },
        };
      }
      if (!isProviderConfigured(modelTarget.provider)) {
        return fail(`❌ ${modelTarget.provider} 的 API key 未配置，无法切换。请在 .env 配置后重试。`);
      }
      const flapErr = checkFlap();
      if (flapErr) return fail(flapErr);
      setRuntimeModelOverride(modelTarget.provider, modelTarget.modelId);
      const model = createModel();
      logSwitch(`${current}:${currentModel}`, `${modelTarget.provider}:${modelTarget.modelId}`, "agent");
      const text = [
        `✅ 已切换模型：${currentModel} → ${modelTarget.modelId}。`,
        `生效范围：新会话（定时任务唤醒、subagent）将使用 ${modelTarget.modelId}；`,
        `当前会话继续使用 ${currentModel} 直到结束。如需本会话立即切换，请提示用户使用 /provider ${provider}。`,
      ].join("\n");
      return {
        content: [{ type: "text" as const, text }],
        details: { from: currentModel, to: modelTarget.modelId, modelId: model.id, changed: true },
      };
    }

    // provider 粒度目标
    if (!PROVIDERS.includes(provider as RuntimeProviderName)) {
      return fail(`❌ 未知目标 "${provider}"，可选：${[...PROVIDERS, ...MODEL_TARGETS].join(", ")}`);
    }
    const target = provider as RuntimeProviderName;

    if (target === current) {
      return {
        content: [{ type: "text" as const, text: `ℹ️ 已是 ${target}（${getActiveModelId()}），无需切换。` }],
        details: { provider: current, changed: false },
      };
    }

    if (!isProviderConfigured(target)) {
      return fail(`❌ ${target} 的 API key 未配置，无法切换。请在 .env 配置后重试。`);
    }

    const flapErr = checkFlap();
    if (flapErr) return fail(flapErr);

    setRuntimeProvider(target);
    const model = createModel(); // 同步 OPENAI_API_KEY 到新 provider 的 key
    logSwitch(current, target, "agent");

    const text = [
      `✅ 已从 ${current} 切换到 ${target}（${model.id}）。`,
      `生效范围：新会话（定时任务唤醒、subagent）将使用 ${target}；`,
      `当前会话继续使用 ${current} 直到结束。如需本会话立即切换，请提示用户使用 /provider 命令。`,
    ].join("\n");
    return {
      content: [{ type: "text" as const, text }],
      details: { from: current, to: target, modelId: model.id, changed: true },
    };
  },
};
