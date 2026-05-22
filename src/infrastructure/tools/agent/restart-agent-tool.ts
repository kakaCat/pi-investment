/**
 * Restart Agent Tool
 *
 * 在不退出当前终端会话的前提下，重启 agent 进程和 Python bridge。
 * 适用于：
 * - 新工具注册后想让当前 session 生效
 * - Python bridge 卡死或异常
 * - 需要干净重启恢复性能
 *
 * 原理：
 *   1. 保存重启上下文（对话摘要、session 信息）到 .restart/context.json
 *   2. 终止 Python bridge 进程
 *   3. 通过 child_process.spawn 启动新的 agent 进程
 *   4. 当前进程 exit
 *
 * 新进程启动时会检测 .restart/context.json，恢复上下文。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { execSync } from "child_process";
import process from "node:process";
import { join, dirname } from "path";
import { writeFileSync, mkdirSync, existsSync, unlinkSync } from "fs";
import { fileURLToPath } from "url";
import { getSessionKey, getConversationMessages } from "../../logging/observable-logger.js";
import { resetTerminalModes } from "../../tui/pi-tui-compat.js";

// ── Constants ──────────────────────────────────────────────────────────────

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, "..", "..", "..");
const RESTART_DIR = join(PROJECT_ROOT, ".restart");
const CONTEXT_FILE = join(RESTART_DIR, "context.json");

let currentSession: any = null;

export function initRestartAgentTool(session: any): void {
  currentSession = session;
}

interface RestartTerminalStreams {
  stdin?: {
    isTTY?: boolean;
    setRawMode?: (mode: boolean) => void;
  };
  stdout?: {
    write?: (data: string) => unknown;
  };
}

interface RestartExecPlanInput {
  projectRoot?: string;
  argv?: string[];
  execPath?: string;
  localTsxExists?: boolean;
}

interface RestartExecPlan {
  file: string;
  args: string[];
}

interface RestartContextMessage {
  role: string;
  content: string;
  timestamp: string;
}

interface BuildRestartContextInput {
  cwd: string;
  prevSessionKey: string;
  conversationMessages: RestartContextMessage[];
  sdkSessionFile?: string;
  sdkSessionId?: string;
  env: {
    NODE_ENV: string;
    BACKGROUND_MODE: string;
  };
}

export function buildRestartContext(input: BuildRestartContextInput) {
  return {
    timestamp: new Date().toISOString(),
    cwd: input.cwd,
    reason: "user_requested_restart",
    prevSessionKey: input.prevSessionKey,
    sdkSessionFile: input.sdkSessionFile,
    sdkSessionId: input.sdkSessionId,
    conversationMessageCount: input.conversationMessages.length,
    messages: input.conversationMessages.slice(-50),
    env: input.env,
  };
}

function getCurrentSessionInfo(): { sessionFile?: string; sessionId?: string } {
  if (!currentSession) return {};
  return {
    sessionFile: currentSession.sessionFile ?? currentSession.sessionManager?.getSessionFile?.(),
    sessionId: currentSession.sessionId ?? currentSession.sessionManager?.getSessionId?.(),
  };
}

/**
 * 查找 QuantSys CLI daemon 进程并终止
 * 只匹配通过本项目启动的 quantsys.cli --daemon 进程
 */
function killPythonBridge(): boolean {
  try {
    const result = execSync("pgrep -f 'quantsys.cli.*--daemon' 2>/dev/null || true", {
      encoding: "utf-8",
      timeout: 3000,
    });
    const pids = result.trim().split("\n").filter(Boolean);
    if (pids.length > 0) {
      execSync(`kill ${pids.join(" ")} 2>/dev/null || true`, { timeout: 3000 });
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * 获取正确的启动命令
 *
 * 当前进程在 tsx 下运行时：
 *   tsx src/index.ts  → 实际进程 argv = [node, /path/to/src/index.ts]
 *   (tsx 内部通过 loader 方式执行，process.argv[1] 是入口文件)
 *
 * 统一使用 tsx（优先本地 .bin/tsx，否则全局 tsx）来重启
 */
export function buildRestartExecPlan(input: RestartExecPlanInput = {}): RestartExecPlan {
  const projectRoot = input.projectRoot ?? PROJECT_ROOT;
  const argv = input.argv ?? process.argv;
  const execPath = input.execPath ?? process.execPath;
  const localTsx = join(projectRoot, "node_modules", ".bin", "tsx");
  const localTsxExists = input.localTsxExists ?? existsSync(localTsx);

  if (localTsxExists) {
    const entryFile =
      argv[1] && argv[1] !== argv[0] && argv[1].endsWith(".ts")
        ? argv[1]
        : join(projectRoot, "src", "index.ts");

    return {
      file: localTsx,
      args: [localTsx, entryFile],
    };
  }

  return {
    file: execPath,
    args: [execPath, ...argv.slice(1)],
  };
}

/**
 * Restore terminal modes that pi-tui enables before handing the TTY to a new
 * process. This mirrors the important parts of ProcessTerminal.stop() without
 * needing direct access to the InteractiveMode instance.
 */
export function resetTerminalForRestart(streams: RestartTerminalStreams = {}): void {
  const stdin = streams.stdin ?? process.stdin;
  const stdout = streams.stdout ?? process.stdout;

  try {
    stdout.write?.("\x1b[?2026l"); // synchronized output off
    stdout.write?.("\x1b[?2004l"); // bracketed paste off
    stdout.write?.("\x1b[<u"); // Kitty keyboard protocol off
    stdout.write?.("\x1b[>4;0m"); // xterm modifyOtherKeys off
    stdout.write?.("\x1b[?1l"); // normal cursor-key mode
    stdout.write?.("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l"); // mouse modes off
    stdout.write?.("\x1b[0m");
    stdout.write?.("\x1b(B");
    stdout.write?.("\x1b[?25h");
  } catch {
    // ignore
  }

  try {
    if (stdin.isTTY) {
      stdin.setRawMode?.(false);
    }
  } catch {
    // ignore
  }

  try {
    execSync("stty sane 2>/dev/null || true", { stdio: "ignore", timeout: 1000 });
  } catch {
    // ignore
  }

  try {
    execSync("stty iutf8 2>/dev/null || true", { stdio: "ignore", timeout: 1000 });
  } catch {
    // ignore
  }

  if (streams.stdin === undefined && streams.stdout === undefined) {
    resetTerminalModes({ restoreRawMode: true, runStty: true });
  }
}

// ── Tool Definition ────────────────────────────────────────────────────────

export const restartAgentTool: ToolDefinition = {
  name: "restart_agent",
  label: "重启 Agent",
  description:
    "Restart the entire agent process (TypeScript + Python bridge) without leaving the terminal. " +
    "Use when: (1) new tools have been added to the codebase and need to take effect, " +
    "(2) Python bridge is stuck or unresponsive, (3) general performance degradation. " +
    "The conversation context will be saved and restored after restart. " +
    "Note: there will be a ~10-30 second delay while the new process starts up.",
  parameters: Type.Object({
    preserve_context: Type.Optional(
      Type.Boolean({
        description:
          "Whether to save and restore the current conversation context. " +
          "Default: true. Set to false for a completely clean restart.",
      }),
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    const preserveContext = params.preserve_context !== false;

    // ── 1. 保存重启上下文 ──────────────────────────────────────────
    if (preserveContext) {
      try {
        if (!existsSync(RESTART_DIR)) {
          mkdirSync(RESTART_DIR, { recursive: true });
        }

        const prevSessionKey = getSessionKey();
        const conversationMessages = getConversationMessages();

        const currentSession = getCurrentSessionInfo();
        const context = buildRestartContext({
          cwd: process.cwd(),
          prevSessionKey,
          conversationMessages,
          sdkSessionFile: currentSession.sessionFile,
          sdkSessionId: currentSession.sessionId,
          env: {
            NODE_ENV: process.env.NODE_ENV || "development",
            BACKGROUND_MODE: process.env.BACKGROUND_MODE || "false",
          },
        });

        writeFileSync(CONTEXT_FILE, JSON.stringify(context, null, 2), "utf-8");
      } catch (e) {
        // 即使保存失败也继续重启
        console.error("[restart] 保存上下文失败:", e);
      }
    } else {
      // 清理旧上下文，实现干净重启
      try {
        if (existsSync(CONTEXT_FILE)) {
          unlinkSync(CONTEXT_FILE);
        }
      } catch {
        // ignore
      }
    }

    // ── 2. 终止 Python bridge ──────────────────────────────────────
    try {
      killPythonBridge();
    } catch {
      // ignore
    }

    // ── 3. 准备原地替换当前进程 ───────────────────────────────────
    const restartPlan = buildRestartExecPlan();
    const env = {
      ...process.env,
      PI_RESTARTED: "true",
      PI_RESTART_TIMESTAMP: new Date().toISOString(),
      // 确保 UTF-8 编码
      LANG: process.env.LANG || "zh_CN.UTF-8",
      LC_ALL: process.env.LC_ALL || "zh_CN.UTF-8",
      LC_CTYPE: process.env.LC_CTYPE || "zh_CN.UTF-8",
    };
    resetTerminalForRestart();

    // ── 4. 返回消息并退出 ──────────────────────────────────────────
    // 使用 execve 原地替换当前进程，保留前台进程组和 TTY 控制权。
    const response = {
      content: [
        {
          type: "text" as const,
          text: `## 🔄 Agent 重启中...\n\n` +
                `当前进程将原地重启，PID 会保持在前台终端中。\n` +
                (preserveContext
                  ? `✅ 对话上下文已保存，重启后将恢复。\n`
                  : `🆕 干净重启，不保留上下文。\n`) +
                `⏱ 预计 10-30 秒后新 agent 可用。\n\n` +
                `**新工具（如 get_concept_list、get_concept_stocks）将在重启后生效。**`,
        },
      ],
      details: {
        preserve_context: preserveContext,
        command: restartPlan.args.join(" "),
        mode: "execve",
      },
    };

    setImmediate(() => {
      const execve = process.execve;
      if (!execve) {
        console.error("[restart] 当前 Node 版本不支持 process.execve，无法安全原地重启");
        return;
      }

      try {
        process.stdin.pause();
      } catch {
        // ignore
      }

      setTimeout(() => {
        execve(restartPlan.file, restartPlan.args, env);
      }, 500);
    });

    return response;
  },
};
