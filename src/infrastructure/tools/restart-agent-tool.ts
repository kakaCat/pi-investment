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
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { spawn, execSync } from "child_process";
import { join, dirname } from "path";
import { writeFileSync, mkdirSync, existsSync, unlinkSync } from "fs";
import { fileURLToPath } from "url";
import { getSessionKey, getConversationMessages } from "../logging/observable-logger.js";

// ── Constants ──────────────────────────────────────────────────────────────

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, "..", "..", "..");
const RESTART_DIR = join(PROJECT_ROOT, ".restart");
const CONTEXT_FILE = join(RESTART_DIR, "context.json");

/**
 * 查找 Python akshare_bridge 进程并终止
 * 只匹配通过本项目启动的 akshare_bridge.py --daemon 进程
 */
function killPythonBridge(): boolean {
  try {
    const result = execSync("pgrep -f 'akshare_bridge.py' 2>/dev/null || true", {
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
function getSpawnCommand(): { cmd: string; args: string[] } {
  // 优先查找本项目的 tsx
  const localTsx = join(PROJECT_ROOT, "node_modules", ".bin", "tsx");
  const tsxBin = existsSync(localTsx) ? localTsx : "tsx";

  // 取当前运行的文件作为入口
  // process.argv[1] 是 tsx 加载的入口文件路径（src/index.ts）
  // 如果不可用，回退到已知入口
  const entryFile = process.argv[1];
  if (entryFile && entryFile !== process.argv[0] && entryFile.endsWith(".ts")) {
    return {
      cmd: tsxBin,
      args: [entryFile],
    };
  }

  // 回退：用 tsx 直接启动入口
  return {
    cmd: tsxBin,
    args: [join(PROJECT_ROOT, "src", "index.ts")],
  };
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

        const context = {
          timestamp: new Date().toISOString(),
          cwd: process.cwd(),
          reason: "user_requested_restart",
          prevSessionKey,
          conversationMessageCount: conversationMessages.length,
          messages: conversationMessages.slice(-50), // 保留最近 50 条消息
          env: {
            NODE_ENV: process.env.NODE_ENV || "development",
            BACKGROUND_MODE: process.env.BACKGROUND_MODE || "false",
          },
        };

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

    // ── 3. 启动新进程 ──────────────────────────────────────────────
    const { cmd, args } = getSpawnCommand();

    // 先验证 tsx 可执行文件存在
    const tsxExists = existsSync(cmd) || cmd === "tsx";
    if (!tsxExists) {
      console.warn(`[restart] 警告: ${cmd} 不存在，尝试使用全局 tsx`);
    }

    const child = spawn(cmd, args, {
      cwd: process.cwd(),
      stdio: "inherit",
      detached: true,
      env: {
        ...process.env,
        PI_RESTARTED: "true",
        PI_RESTART_TIMESTAMP: new Date().toISOString(),
        // 保持原有的 locale 设置，不要覆盖
      },
    });

    // 监听 spawn 错误（如命令不存在）
    let spawnFailed = false;
    child.on("error", (err: NodeJS.ErrnoException) => {
      spawnFailed = true;
      console.error(`[restart] 新进程启动失败: ${err.message}`);
    });

    child.unref();

    // ── 4. 返回消息并退出 ──────────────────────────────────────────
    // 使用 setImmediate + process.exit 确保 response 先返回
    // 然后当前进程退出，新进程继续运行
    const response = {
      content: [
        {
          type: "text" as const,
          text: `## 🔄 Agent 重启中...\n\n` +
                `新进程已启动 (PID: ${child.pid ?? '?'})，当前进程即将退出。\n` +
                (preserveContext
                  ? `✅ 对话上下文已保存，重启后将恢复。\n`
                  : `🆕 干净重启，不保留上下文。\n`) +
                `⏱ 预计 10-30 秒后新 agent 可用。\n\n` +
                `**新工具（如 get_concept_list、get_concept_stocks）将在重启后生效。**`,
        },
      ],
      details: {
        new_pid: child.pid,
        preserve_context: preserveContext,
        command: `${cmd} ${args.join(" ")}`,
      },
    };

    // 返回后安排退出
    // 需要先重置终端状态，避免子进程继承 raw mode 导致乱码
    setImmediate(() => {
      if (spawnFailed) {
        console.log("[restart] 新进程启动失败，当前进程继续运行");
        return;
      }

      // 重置终端模式：InteractiveMode (readline) 会将 stdin 设为 raw mode，
      // 必须在退出前重置，否则子进程会继承错误的终端状态导致输入乱码
      try {
        if (process.stdin.isTTY) {
          process.stdin.setRawMode(false);
        }
      } catch {
        // stdin 可能已被关闭或不可用
      }

      try {
        process.stdin.pause();
      } catch {
        // ignore
      }

      // 使用 stty 命令恢复正常终端模式
      try {
        execSync('stty sane', { stdio: 'ignore', timeout: 1000 });
      } catch {
        // ignore - stty 可能不可用
      }

      // 延迟退出，确保终端状态完全恢复
      setTimeout(() => {
        process.exit(0);
      }, 300);
    });

    return response;
  },
};
