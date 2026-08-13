import path from "node:path";
import { FxRateServiceAdapter } from "../fx-rate-service-adapter.js";
import type { AgentKind } from "../../domain/agent-roles/types.js";
import type { SchedulerExecutor } from "./scheduler-service.js";

export interface SchedulerExecutorOptions {
  projectRoot?: string;
  piDir?: string;
  promptAgent?: (message: string, agentKind?: AgentKind) => Promise<void>;
  writeOutput?: (message: string) => void;
  fxRateService?: FxRateServiceAdapter;
}

export function createSchedulerExecutor(options: SchedulerExecutorOptions = {}): SchedulerExecutor {
  const projectRoot = options.projectRoot ?? process.cwd();
  const piDir = options.piDir ?? path.join(projectRoot, ".pi-invest");
  const writeOutput = options.writeOutput ?? ((message) => process.stdout.write(message));
  const fxRateService = options.fxRateService ?? new FxRateServiceAdapter(piDir);

  return async ({ task }) => {
    const kind = String(task.payload.kind ?? "");
    if (kind === "agent_turn") {
      const message = String(task.payload.message ?? "");
      if (!message) {
        return { skipped: true, reason: "empty message" };
      }
      if (!options.promptAgent) {
        throw new Error("No prompt agent configured for scheduler agent_turn task");
      }
      await options.promptAgent(message, task.payload.agentKind as AgentKind | undefined);
      return { ok: true };
    }
    if (kind === "daily_review") {
      return Promise.reject(new Error("daily_review feature is deprecated. Services have been removed."));
    }
    if (kind === "stop_loss_alert") {
      return Promise.reject(new Error("stop_loss_alert feature is deprecated. Services have been removed."));
    }
    if (kind === "system_event" && task.payload.message === "update_fx_rates") {
      await fxRateService.updateCache();
      return { ok: true };
    }
    if (kind === "system_event") {
      const text = String(task.payload.text ?? "");
      if (text) {
        writeOutput(`\n[系统] ${text}\n`);
      }
      return { ok: true };
    }
    if (kind === "ipo_watch") {
      return runIpoWatch(projectRoot, task.payload);
    }
    throw new Error(`Unsupported scheduler payload kind: ${kind}`);
  };
}

function runIpoWatch(_projectRoot: string, _payload: Record<string, unknown>): Promise<{ stdout: string; stderr: string }> {
  // IPO watch 功能已废弃（quant/ 目录已删除）
  // 如需恢复，请在 quantsys-v2 中实现对应功能
  return Promise.reject(new Error("IPO watch feature is deprecated. The quant/ directory has been removed."));
}
