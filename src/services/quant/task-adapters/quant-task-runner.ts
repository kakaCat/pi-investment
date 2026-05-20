import { access } from "fs/promises";
import * as path from "path";
import { spawn } from "child_process";
import type { JobType } from "../../jobs/job-service.js";
import { getQuantJobAdapter } from "./quant-job-command-map.js";

export interface QuantTaskCommand {
  command: string;
  args: string[];
  cwd: string;
}

export interface QuantTaskRunnerOptions {
  projectRoot?: string;
  pythonCommand?: string;
  params?: Record<string, unknown>;
  maxOutputChars?: number;
}

export interface QuantTaskRunResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  command: string;
  args: string[];
}

export function buildQuantTaskCommand(
  jobType: JobType,
  options: QuantTaskRunnerOptions = {}
): QuantTaskCommand {
  const adapter = getQuantJobAdapter(jobType);
  if (adapter.type !== "command") {
    throw new Error(`Quant job type ${jobType} is not configured as a local command`);
  }

  const projectRoot = options.projectRoot ?? process.cwd();
  const scriptPath = path.join(projectRoot, adapter.script);
  const args = [
    scriptPath,
    ...adapter.args.slice(1),
    ...buildArgs(adapter.paramsToArgs, options.params ?? {}),
  ];

  return {
    command: options.pythonCommand ?? "python3",
    args,
    cwd: path.join(projectRoot, "quant"),
  };
}

export class QuantTaskRunner {
  constructor(private readonly options: QuantTaskRunnerOptions = {}) {}

  async run(
    jobType: JobType,
    params: Record<string, unknown> = {},
    signal?: AbortSignal
  ): Promise<QuantTaskRunResult> {
    const task = buildQuantTaskCommand(jobType, { ...this.options, params });
    await assertFileExists(task.args[0]);

    return runCommandWithLimit(task, this.options.maxOutputChars ?? DEFAULT_MAX_OUTPUT_CHARS, signal);
  }
}

function buildArgs(
  paramsToArgs: Record<string, string> | undefined,
  params: Record<string, unknown>
): string[] {
  if (!paramsToArgs) {
    return [];
  }

  const args: string[] = [];
  for (const [paramName, flag] of Object.entries(paramsToArgs)) {
    const value = params[paramName];
    if (value === undefined || value === null || value === false) {
      continue;
    }

    args.push(flag);
    if (value !== true) {
      args.push(Array.isArray(value) ? value.join(",") : String(value));
    }
  }
  return args;
}

const DEFAULT_MAX_OUTPUT_CHARS = 20_000;

function truncateOutput(output: string, maxChars: number): string {
  if (output.length <= maxChars) {
    return output;
  }
  return output.slice(output.length - maxChars);
}

async function assertFileExists(filePath: string): Promise<void> {
  try {
    await access(filePath);
  } catch {
    throw new Error(`Quant task script not found: ${filePath}`);
  }
}

function runCommandWithLimit(
  task: QuantTaskCommand,
  maxOutputChars: number,
  signal?: AbortSignal
): Promise<QuantTaskRunResult> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error("Quant task aborted"));
      return;
    }

    const child = spawn(task.command, task.args, {
      cwd: task.cwd,
      env: process.env,
    });

    let stdout = "";
    let stderr = "";
    let aborted = false;

    const abort = () => {
      aborted = true;
      child.kill("SIGTERM");
    };
    signal?.addEventListener("abort", abort, { once: true });

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      signal?.removeEventListener("abort", abort);
      reject(error);
    });
    child.on("close", (exitCode) => {
      signal?.removeEventListener("abort", abort);
      if (aborted) {
        reject(new Error("Quant task aborted"));
        return;
      }

      const result = {
        exitCode: exitCode ?? -1,
        stdout: truncateOutput(stdout, maxOutputChars),
        stderr: truncateOutput(stderr, maxOutputChars),
        command: task.command,
        args: task.args,
      };

      if (result.exitCode === 0) {
        resolve(result);
      } else {
        reject(
          new Error(
            `Quant task failed with exit code ${result.exitCode}: ${stderr || stdout}`
          )
        );
      }
    });
  });
}
