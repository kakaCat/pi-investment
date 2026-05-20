import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import * as path from "node:path";

export interface QuantCliResponse<T = unknown> {
  ok: boolean;
  command: string;
  params?: Record<string, unknown>;
  data?: T;
  artifacts?: string[];
  warnings?: string[];
  error?: {
    code?: string;
    message?: string;
    hint?: string;
  } | null;
}

export interface ProcessResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

export type SpawnQuantCli = (
  command: string,
  args: string[],
  options: { cwd: string; env: NodeJS.ProcessEnv },
  signal?: AbortSignal
) => Promise<ProcessResult>;

export interface RunQuantCliOptions {
  python?: string;
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  signal?: AbortSignal;
  spawn?: SpawnQuantCli;
}

export function buildQuantCliArgs(
  domain: string,
  action: string,
  params: Record<string, unknown> = {}
): string[] {
  const args = ["-m", "quantsys.cli", domain, `+${action}`, "--json"];

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === false) {
      continue;
    }

    args.push(`--${key.replace(/_/g, "-")}`);
    if (value !== true) {
      args.push(Array.isArray(value) ? value.join(",") : String(value));
    }
  }

  return args;
}

export async function runQuantCli<T = unknown>(
  domain: string,
  action: string,
  params: Record<string, unknown> = {},
  options: RunQuantCliOptions = {}
): Promise<QuantCliResponse<T>> {
  const python = options.python ?? process.env.QUANT_CLI_PYTHON ?? "python";
  const cwd = options.cwd ?? getQuantRoot();
  const args = buildQuantCliArgs(domain, action, params);
  const spawnFn = options.spawn ?? spawnProcess;

  const result = await spawnFn(
    python,
    args,
    { cwd, env: options.env ?? process.env },
    options.signal
  );
  const payload = parseQuantCliJson<T>(result.stdout, result.stderr);

  if (!payload.ok) {
    const code = payload.error?.code ?? "QUANT_CLI_FAILED";
    const message = payload.error?.message ?? (result.stderr || "Quant CLI command failed");
    throw new Error(`${code}: ${message}`);
  }

  return payload;
}

export function getQuantRoot(): string {
  const currentFile = fileURLToPath(import.meta.url);
  return path.resolve(path.dirname(currentFile), "../../../quant");
}

function parseQuantCliJson<T>(stdout: string, stderr: string): QuantCliResponse<T> {
  const trimmed = stdout.trim();
  if (!trimmed) {
    throw new Error(`QUANT_CLI_NO_OUTPUT: ${stderr || "Quant CLI returned no output"}`);
  }

  try {
    return JSON.parse(trimmed) as QuantCliResponse<T>;
  } catch (error) {
    throw new Error(
      `QUANT_CLI_INVALID_JSON: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

function spawnProcess(
  command: string,
  args: string[],
  options: { cwd: string; env: NodeJS.ProcessEnv },
  signal?: AbortSignal
): Promise<ProcessResult> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error("Quant CLI command aborted"));
      return;
    }

    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
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
        reject(new Error("Quant CLI command aborted"));
        return;
      }

      resolve({
        exitCode: exitCode ?? -1,
        stdout,
        stderr,
      });
    });
  });
}
