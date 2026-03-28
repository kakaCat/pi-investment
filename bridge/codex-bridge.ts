/**
 * Claude-Codex 双向通信桥
 *
 * 架构:
 *   Claude Code (Main Agent)
 *       ↕ HTTP (REST + SSE)
 *   CodexBridge (本文件, port 8765)
 *       ↕ WebSocket JSON-RPC
 *   codex app-server (port 3100)
 *       ↕ LLM calls
 *   GPT-5.4 (Codex subagent)
 *
 * Claude → Codex:  POST /task       发任务
 * Codex  → Claude: GET  /approvals  Codex 请求审批（文件修改/命令执行）
 * Claude → Codex:  POST /approve    Claude 回复审批
 * 双方实时:         GET  /events    SSE 事件流
 */

import WebSocket from "ws";
import http from "http";
import { EventEmitter } from "events";
import { randomUUID } from "crypto";
import { spawn, exec, ChildProcess } from "child_process";

const CODEX_WS_PORT = 3100;
const BRIDGE_HTTP_PORT = 8765;
const CODEX_STARTUP_WAIT_MS = 3000;

// ─── Types ────────────────────────────────────────────────────────────────────

interface Task {
  id: string;
  prompt: string;
  workdir: string;
  status: "pending" | "running" | "done" | "error";
  result: string;
  events: any[];
  createdAt: number;
  threadId?: string;
  error?: string;
}

interface PendingApproval {
  id: string;
  taskId: string;
  type: string; // "apply_patch" | "command_execution" | "file_change"
  description: string;
  params: any;
  requestId: string;
  createdAt: number;
}

// ─── Bridge ───────────────────────────────────────────────────────────────────

class CodexBridge extends EventEmitter {
  private ws: WebSocket | null = null;
  private tasks = new Map<string, Task>();
  private approvals = new Map<string, PendingApproval>();
  private pendingRpc = new Map<string, (r: any) => void>();
  private rpcCounter = 0;
  private sseClients = new Set<http.ServerResponse>();
  private codexProc: ChildProcess | null = null;

  async start() {
    console.log("🚀 Starting Claude-Codex Bridge...");
    await this.launchCodexServer();
    await this.connectWs();
    this.startHttpServer();
  }

  // ── Launch codex app-server ──────────────────────────────────────────────

  private launchCodexServer(): Promise<void> {
    return new Promise((resolve) => {
      console.log(`   Launching codex app-server on ws://127.0.0.1:${CODEX_WS_PORT}...`);
      this.codexProc = spawn(
        "codex",
        ["app-server", "--listen", `ws://127.0.0.1:${CODEX_WS_PORT}`],
        { stdio: ["ignore", "pipe", "pipe"] }
      );

      this.codexProc.stdout?.on("data", (d) => process.stdout.write(`[codex] ${d}`));
      this.codexProc.stderr?.on("data", (d) => {
        const msg = d.toString();
        process.stderr.write(`[codex] ${msg}`);
        if (/listen|ready|bound/i.test(msg)) resolve();
      });

      this.codexProc.on("error", (e) => console.error("codex process error:", e));
      this.codexProc.on("exit", (code) => {
        console.warn(`codex app-server exited with code ${code}`);
      });

      // Fallback: assume started after timeout
      setTimeout(resolve, CODEX_STARTUP_WAIT_MS);
    });
  }

  // ── WebSocket connection ─────────────────────────────────────────────────

  private connectWs(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = `ws://127.0.0.1:${CODEX_WS_PORT}`;
      console.log(`   Connecting WebSocket to ${url}...`);
      this.ws = new WebSocket(url);

      this.ws.on("open", async () => {
        console.log("   WebSocket connected ✓");
        try {
          await this.rpc("initialize", {
            clientInfo: { name: "claude-code-bridge", version: "1.0.0" },
          });
          resolve();
        } catch (e) {
          reject(e);
        }
      });

      this.ws.on("message", (raw) => {
        try {
          const msg = JSON.parse(raw.toString());
          this.handleWsMessage(msg);
        } catch (e) {
          console.error("WS parse error:", e);
        }
      });

      this.ws.on("error", (e) => {
        console.error("WS error:", e.message);
        reject(e);
      });

      this.ws.on("close", () => {
        console.warn("WS connection closed, reconnecting in 3s...");
        setTimeout(() => this.connectWs().catch(console.error), 3000);
      });
    });
  }

  // ── WebSocket message handler ────────────────────────────────────────────

  private handleWsMessage(msg: any) {
    this.broadcastSse({ source: "codex", msg });

    // JSON-RPC response → resolve pending promise
    if ("id" in msg && this.pendingRpc.has(String(msg.id))) {
      this.pendingRpc.get(String(msg.id))!(msg.result ?? msg.error);
      this.pendingRpc.delete(String(msg.id));
      return;
    }

    // Notification
    if (msg.method) {
      this.handleNotification(msg.method, msg.params ?? {});
    }
  }

  private handleNotification(method: string, params: any) {
    const task = params.threadId
      ? this.findTaskByThreadId(params.threadId)
      : undefined;

    switch (method) {
      case "thread/started":
        if (task) {
          task.status = "running";
          task.threadId = params.threadId;
        }
        break;

      case "thread/status/changed":
        if (task) {
          const st = params.status?.type ?? params.status;
          if (st === "completed" || st === "idle") {
            // idle after a turn = turn completed
          }
          if (st === "error") {
            task.status = "error";
            task.error = params.error ?? "unknown error";
            this.notify(
              "Codex 任务失败 ❌",
              task.prompt.slice(0, 60) + (task.prompt.length > 60 ? "…" : "")
            );
          }
        }
        break;

      // turn completed
      case "turn/completed":
        if (task && params.turn?.status === "completed") {
          task.status = "done";
          this.notify(
            "Codex 任务完成 ✅",
            task.prompt.slice(0, 60) + (task.prompt.length > 60 ? "…" : "")
          );
        }
        break;

      // Streaming agent output: item/agentMessage/delta
      case "item/agentMessage/delta":
        if (task && params.delta) {
          task.result += params.delta;
        }
        break;

      // item completed: capture final text if we missed deltas
      case "item/completed":
        if (task && params.item?.type === "agentMessage" && params.item?.text) {
          if (!task.result) task.result = params.item.text;
        }
        break;

      // ── Bidirectional: Codex requests Claude's approval ──────────────────
      case "apply_patch/approval":
      case "applyPatchApproval":
        this.storePendingApproval(task, "apply_patch", params);
        break;

      case "command_execution/approval":
      case "commandExecutionRequestApproval":
        this.storePendingApproval(task, "command_execution", params);
        break;

      case "file_change/approval":
      case "fileChangeRequestApproval":
        this.storePendingApproval(task, "file_change", params);
        break;
    }

    if (task) task.events.push({ method, params, ts: Date.now() });
  }

  private storePendingApproval(task: Task | undefined, type: string, params: any) {
    const approval: PendingApproval = {
      id: randomUUID(),
      taskId: task?.id ?? "unknown",
      type,
      description: this.describeApproval(type, params),
      params,
      requestId: params.requestId ?? params.id ?? "",
      createdAt: Date.now(),
    };
    this.approvals.set(approval.id, approval);
    console.log(`\n⚠️  Approval needed [${type}]: ${approval.description}`);
    this.broadcastSse({ source: "bridge", event: "approval_needed", approval });
  }

  private describeApproval(type: string, params: any): string {
    if (type === "apply_patch") {
      const files = (params.patch ?? "").match(/^[+]{3} b\/(.+)$/gm) ?? [];
      return `Apply patch to: ${files.join(", ") || "(unknown files)"}`;
    }
    if (type === "command_execution") {
      return `Run command: ${params.command ?? JSON.stringify(params)}`;
    }
    if (type === "file_change") {
      return `Modify file: ${params.path ?? JSON.stringify(params)}`;
    }
    return JSON.stringify(params).slice(0, 120);
  }

  // ── Send task to Codex ───────────────────────────────────────────────────

  async sendTask(prompt: string, workdir: string = process.cwd()): Promise<Task> {
    const task: Task = {
      id: randomUUID(),
      prompt,
      workdir,
      status: "pending",
      result: "",
      events: [],
      createdAt: Date.now(),
    };
    this.tasks.set(task.id, task);

    console.log(`\n📤 Sending task to Codex: "${prompt.slice(0, 80)}..."`);
    this.notify(
      "Codex 任务开始 🤖",
      prompt.slice(0, 60) + (prompt.length > 60 ? "…" : "")
    );

    const threadResult = await this.rpc("thread/start", {
      initialPrompt: prompt,
      workdir,
      approvalPolicy: "on-request", // Codex asks Claude for approval before file/cmd changes
    });

    const threadId = threadResult?.thread?.id;
    if (!threadId) {
      task.status = "error";
      task.error = "thread/start failed";
      return task;
    }

    task.threadId = threadId;
    task.status = "running";
    this.tasks.set(task.id, task); // ensure indexed by threadId

    // Actually start the agent turn
    await this.rpc("turn/start", {
      threadId,
      input: [{ type: "text", text: prompt }],
    });

    return task;
  }

  // ── Claude approves/rejects Codex action ────────────────────────────────

  approve(approvalId: string, approved: boolean, reason?: string): boolean {
    const approval = this.approvals.get(approvalId);
    if (!approval) return false;

    const responseMethod = this.approvalResponseMethod(approval.type);
    this.wsNotify(responseMethod, {
      requestId: approval.requestId,
      decision: approved ? "approve" : "reject",
      reason,
    });

    console.log(`\n${approved ? "✅" : "❌"} Approval ${approved ? "granted" : "rejected"}: ${approval.description}`);
    this.approvals.delete(approvalId);
    this.broadcastSse({
      source: "bridge",
      event: "approval_resolved",
      approvalId,
      approved,
    });
    return true;
  }

  private approvalResponseMethod(type: string): string {
    const map: Record<string, string> = {
      apply_patch: "applyPatchApproval",
      command_execution: "commandExecutionRequestApproval",
      file_change: "fileChangeRequestApproval",
    };
    return map[type] ?? type;
  }

  // ── JSON-RPC helpers ─────────────────────────────────────────────────────

  private rpc(method: string, params: any): Promise<any> {
    return new Promise((resolve, reject) => {
      const id = ++this.rpcCounter;
      const timeout = setTimeout(() => {
        this.pendingRpc.delete(String(id));
        reject(new Error(`RPC timeout: ${method}`));
      }, 30_000);

      this.pendingRpc.set(String(id), (result) => {
        clearTimeout(timeout);
        resolve(result);
      });

      this.ws!.send(JSON.stringify({ id, method, params }));
    });
  }

  private wsNotify(method: string, params: any) {
    this.ws!.send(JSON.stringify({ method, params }));
  }

  private notify(title: string, message: string) {
    const cmd = `terminal-notifier -title ${JSON.stringify(title)} -message ${JSON.stringify(message)} -sound Glass -sender com.apple.Terminal -ignoreDnD`;
    exec(cmd, (err) => {
      if (err) console.error("[notify] terminal-notifier failed:", err.message);
    });
  }

  // ── SSE broadcast ────────────────────────────────────────────────────────

  private broadcastSse(data: any) {
    const payload = `data: ${JSON.stringify(data)}\n\n`;
    for (const client of this.sseClients) {
      client.write(payload);
    }
  }

  // ── Wait for task completion ─────────────────────────────────────────────

  waitForTask(taskId: string, timeoutMs = 120_000): Promise<Task> {
    return new Promise((resolve, reject) => {
      const task = this.tasks.get(taskId);
      if (!task) { reject(new Error("Task not found")); return; }
      if (task.status === "done" || task.status === "error") { resolve(task); return; }

      const timer = setTimeout(() => {
        cleanup();
        reject(new Error(`Task timeout after ${timeoutMs}ms`));
      }, timeoutMs);

      const check = () => {
        const t = this.tasks.get(taskId)!;
        if (t.status === "done" || t.status === "error") {
          cleanup();
          resolve(t);
        }
      };

      // Poll via SSE broadcast hook
      const interval = setInterval(check, 500);
      const cleanup = () => { clearTimeout(timer); clearInterval(interval); };
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  private findTaskByThreadId(threadId: string): Task | undefined {
    for (const t of this.tasks.values()) {
      if (t.threadId === threadId) return t;
    }
    return undefined;
  }

  // ── HTTP API ─────────────────────────────────────────────────────────────

  private startHttpServer() {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url!, `http://localhost:${BRIDGE_HTTP_PORT}`);
      const cors = () => {
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        res.setHeader("Access-Control-Allow-Headers", "Content-Type");
      };
      const json = (data: any, status = 200) => {
        cors();
        res.writeHead(status, { "Content-Type": "application/json" });
        res.end(JSON.stringify(data, null, 2));
      };
      const readBody = (): Promise<any> =>
        new Promise((resolve) => {
          let body = "";
          req.on("data", (d) => (body += d));
          req.on("end", () => {
            try { resolve(body ? JSON.parse(body) : {}); }
            catch { resolve({}); }
          });
        });

      cors();
      if (req.method === "OPTIONS") { res.end(); return; }

      const path = url.pathname;

      // ── GET /status ──────────────────────────────────────────────────────
      if (req.method === "GET" && path === "/status") {
        json({
          wsState: this.ws?.readyState === WebSocket.OPEN ? "connected" : "disconnected",
          tasks: this.tasks.size,
          pendingApprovals: this.approvals.size,
          sseClients: this.sseClients.size,
        });
        return;
      }

      // ── POST /task ───────────────────────────────────────────────────────
      if (req.method === "POST" && path === "/task") {
        readBody().then(async (body) => {
          const { prompt, workdir } = body;
          if (!prompt) { json({ error: "prompt required" }, 400); return; }
          const task = await this.sendTask(prompt, workdir);
          json({ taskId: task.id, status: task.status });
        });
        return;
      }

      // ── POST /task/sync ──────────────────────────────────────────────────
      // 发任务并阻塞等待完成，一次调用拿到结果
      if (req.method === "POST" && path === "/task/sync") {
        readBody().then(async (body) => {
          const { prompt, workdir, timeout } = body;
          if (!prompt) { json({ error: "prompt required" }, 400); return; }
          const task = await this.sendTask(prompt, workdir);
          if (task.status === "error") { json(task); return; }
          try {
            const done = await this.waitForTask(task.id, timeout ?? 120_000);
            json({ id: done.id, status: done.status, result: done.result, error: done.error });
          } catch (e: any) {
            json({ id: task.id, status: "error", error: e.message }, 504);
          }
        });
        return;
      }

      // ── GET /tasks ───────────────────────────────────────────────────────
      if (req.method === "GET" && path === "/tasks") {
        json(
          Array.from(this.tasks.values()).map((t) => ({
            id: t.id,
            status: t.status,
            prompt: t.prompt.slice(0, 100),
            resultLen: t.result.length,
            createdAt: t.createdAt,
          }))
        );
        return;
      }

      // ── GET /result/:id ──────────────────────────────────────────────────
      if (req.method === "GET" && path.startsWith("/result/")) {
        const taskId = path.split("/")[2];
        const task = this.tasks.get(taskId);
        if (!task) { json({ error: "not found" }, 404); return; }
        json({
          id: task.id,
          status: task.status,
          result: task.result,
          error: task.error,
          eventCount: task.events.length,
        });
        return;
      }

      // ── GET /approvals ───────────────────────────────────────────────────
      // Codex → Claude: "请审批这些操作"
      if (req.method === "GET" && path === "/approvals") {
        json(Array.from(this.approvals.values()));
        return;
      }

      // ── POST /approve/:id ────────────────────────────────────────────────
      // Claude → Codex: "我批准/拒绝"
      if (req.method === "POST" && path.startsWith("/approve/")) {
        readBody().then((body) => {
          const approvalId = path.split("/")[2];
          const approved = body.approved !== false;
          const ok = this.approve(approvalId, approved, body.reason);
          json({ ok });
        });
        return;
      }

      // ── GET /events ──────────────────────────────────────────────────────
      // SSE stream: both directions
      if (req.method === "GET" && path === "/events") {
        cors();
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        });
        this.sseClients.add(res);
        res.write(`: connected\n\n`);
        req.on("close", () => this.sseClients.delete(res));
        return;
      }

      // ── GET /help ────────────────────────────────────────────────────────
      if (req.method === "GET" && path === "/help") {
        json({
          endpoints: {
            "GET  /status":           "Bridge & WS connection status",
            "POST /task":             "Send task to Codex  { prompt, workdir? }",
            "GET  /tasks":            "List all tasks",
            "GET  /result/:id":       "Get task result",
            "GET  /approvals":        "Pending approvals waiting for Claude",
            "POST /approve/:id":      "Approve/reject  { approved: bool, reason? }",
            "GET  /events":           "SSE stream of all events (both directions)",
          },
          workflow: [
            "1. Claude POSTs /task with a prompt",
            "2. Bridge sends thread/start to Codex via WebSocket",
            "3. Codex runs, may emit apply_patch/approval or command_execution/approval",
            "4. Claude GETs /approvals, sees pending actions",
            "5. Claude POSTs /approve/:id  { approved: true }",
            "6. Bridge sends approval response back to Codex via WebSocket",
            "7. Claude polls /result/:id until status=done",
          ],
        });
        return;
      }

      res.writeHead(404);
      res.end("Not found. Try GET /help");
    });

    server.listen(BRIDGE_HTTP_PORT, "127.0.0.1", () => {
      console.log(`
╔══════════════════════════════════════════════════╗
║     Claude ↔ Codex Bridge  READY                ║
╠══════════════════════════════════════════════════╣
║  HTTP API : http://localhost:${BRIDGE_HTTP_PORT}             ║
║  Codex WS : ws://localhost:${CODEX_WS_PORT}               ║
╠══════════════════════════════════════════════════╣
║  POST /task       → send task to Codex           ║
║  GET  /approvals  → Codex asks Claude for OK     ║
║  POST /approve/:id→ Claude approves/rejects      ║
║  GET  /events     → SSE real-time stream         ║
║  GET  /help       → full API docs                ║
╚══════════════════════════════════════════════════╝
`);
    });
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const bridge = new CodexBridge();
bridge.start().catch((e) => {
  console.error("Bridge failed to start:", e);
  process.exit(1);
});

process.on("SIGINT", () => {
  console.log("\n👋 Bridge shutting down...");
  process.exit(0);
});
