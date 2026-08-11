/**
 * model_switch — LLM provider/模型热切换工具（agent 自主入口）
 *
 * 当当前模型持续报错（429 限流 / 超时 / 5xx）时，agent 可调用本工具
 * 切换到备用 provider；也可在同 provider 内切换模型档位
 * （如 deepseek-v4-flash ↔ deepseek-v4-pro：日常用 flash 省钱，
 * 复杂分析用 pro 提质量）。
 *
 * 生效范围：切换统一走 services/llm 的 switch()——立即持久化到
 * llm-state.json（重启保持）；之后新建的会话立即使用新模型；
 * 其他运行中的会话（wake/飞书/定时任务）下一轮对话自动惰性切换；
 * 当前会话保持原模型直到结束（工具拿不到 session 句柄）。
 * 人工要立即切当前会话请用 /provider 命令。
 *
 * 防抖动：滚动 1 小时窗口内最多切换 3 次。
 */

import type { ToolDefinition } from "../index.js";
import { getLLM } from "../../../services/llm/index.js";
import { resolveSwitchTarget } from "../../../services/llm/switch-service.js";
import { isProviderConfigured } from "../../../services/llm/catalog.js";

const WINDOW_MS = 60 * 60 * 1000;
const MAX_SWITCHES_PER_WINDOW = 3;
const switchTimestamps: number[] = [];

/** 仅测试使用：清空切换历史 */
export function resetSwitchHistoryForTests(): void {
  switchTimestamps.length = 0;
}

const PROVIDERS = ["deepseek", "kimi"];
const MODEL_TARGETS = ["flash", "pro", "deepseek-v4-flash", "deepseek-v4-pro", "kimi-k3"];

export const modelSwitchTool: ToolDefinition = {
  name: "model_switch",
  description:
    "切换 LLM provider 或模型档位。当当前模型持续报错（429 限流、超时、5xx）时切备用 provider；" +
    "也可在 deepseek 内切档位：flash（便宜，日常任务）↔ pro（更强，复杂分析）。" +
    "切换立即持久化（重启保持）；新会话立即生效，其他运行中会话下一轮对话自动切换；" +
    "当前会话继续用原模型直到结束；如需本会话立即切换，请提示用户使用 /provider 命令。1 小时内最多切换 3 次。",
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

    const llm = getLLM();
    const current = llm.current();

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

    // 只读预检：解析目标 → 相同目标/未配置直接返回（不计入防抖动）
    const target = resolveSwitchTarget(provider);
    if (!target) {
      return fail(`❌ 未知目标 "${provider}"，可选：${[...PROVIDERS, ...MODEL_TARGETS].join(", ")}`);
    }
    const from = `${current.provider}:${current.modelId}`;
    const to = `${target.provider}:${target.modelId}`;
    if (from === to) {
      return {
        content: [{ type: "text" as const, text: `ℹ️ 已是 ${to}，无需切换。` }],
        details: { from, to, changed: false },
      };
    }
    if (!isProviderConfigured(target.provider)) {
      return fail(`❌ ${target.provider} 的 API key 未配置，无法切换。请在 .env 配置后重试。`);
    }

    const flapErr = checkFlap();
    if (flapErr) return fail(flapErr);

    const result = llm.switch(provider, "agent");
    if (!result.ok) return fail(`❌ ${result.error}`);

    const text = [
      `✅ 已切换：${result.from} → ${result.to}（已持久化，重启保持）。`,
      `生效范围：新会话立即使用；运行中的其他会话（wake/飞书/定时任务）下一轮对话自动切换。`,
      `当前会话继续使用 ${from} 直到结束。如需本会话立即切换，请提示用户使用 /provider ${provider}。`,
    ].join("\n");
    return {
      content: [{ type: "text" as const, text }],
      details: { from: result.from, to: result.to, changed: true },
    };
  },
};
