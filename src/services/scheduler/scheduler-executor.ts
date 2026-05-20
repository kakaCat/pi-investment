import { spawn } from "node:child_process";
import path from "node:path";
import { FxRateServiceAdapter } from "../fx-rate-service-adapter.js";
import { DailyReviewService } from "../operations/daily-review-service.js";
import { StopLossAlertService } from "../operations/stop-loss-alert-service.js";
import { runWeeklyEvolution } from "../intelligence/evolution-service.js";
import type { SchedulerExecutor } from "./scheduler-service.js";

export interface SchedulerExecutorOptions {
  projectRoot?: string;
  piDir?: string;
  promptAgent?: (message: string) => Promise<void>;
  writeOutput?: (message: string) => void;
  dailyReviewService?: DailyReviewService;
  stopLossAlertService?: StopLossAlertService;
  fxRateService?: FxRateServiceAdapter;
}

export function createSchedulerExecutor(options: SchedulerExecutorOptions = {}): SchedulerExecutor {
  const projectRoot = options.projectRoot ?? process.cwd();
  const piDir = options.piDir ?? path.join(projectRoot, ".pi-invest");
  const writeOutput = options.writeOutput ?? ((message) => process.stdout.write(message));
  const dailyReviewService = options.dailyReviewService ?? new DailyReviewService(piDir);
  const stopLossAlertService = options.stopLossAlertService ?? new StopLossAlertService(piDir);
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
      await options.promptAgent(message);
      return { ok: true };
    }
    if (kind === "daily_review") {
      const report = await dailyReviewService.run();
      writeOutput(`\n[定时复盘] ${report}\n`);
      return { ok: true };
    }
    if (kind === "stop_loss_alert") {
      const result = await stopLossAlertService.run();
      writeOutput(`${result.summary}\n`);
      return { ok: true };
    }
    if (kind === "weekly_evolution") {
      const result = await runWeeklyEvolution();
      writeOutput(`[进化分析] 完成: ${result.reportPath}\n`);
      return result;
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

function runIpoWatch(projectRoot: string, payload: Record<string, unknown>): Promise<{ stdout: string; stderr: string }> {
  const scriptPath = path.join(projectRoot, "quant/scripts/ipo_watch_pipeline.py");
  const args = [scriptPath];
  if (typeof payload.agent_endpoint === "string") {
    args.push("--agent-endpoint", payload.agent_endpoint);
  }
  if (typeof payload.board === "string") {
    args.push("--board", payload.board);
  }
  if (typeof payload.min_confidence === "number") {
    args.push("--min-confidence", String(payload.min_confidence));
  }

  return new Promise((resolve, reject) => {
    const child = spawn("python3", args, {
      cwd: path.join(projectRoot, "quant"),
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }
      reject(new Error(`ipo_watch failed with exit code ${code}: ${stderr || stdout}`));
    });
  });
}
