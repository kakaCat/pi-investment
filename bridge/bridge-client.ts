/**
 * Claude Code → Codex Bridge CLI 客户端
 *
 * 用法:
 *   npx tsx bridge/bridge-client.ts task "审查 src/tools/akshare_tools.py 的边界条件"
 *   npx tsx bridge/bridge-client.ts result <taskId>
 *   npx tsx bridge/bridge-client.ts wait <taskId>        # 阻塞等待完成
 *   npx tsx bridge/bridge-client.ts approvals            # 列出待审批
 *   npx tsx bridge/bridge-client.ts approve <id>         # 批准
 *   npx tsx bridge/bridge-client.ts reject <id> [reason] # 拒绝
 *   npx tsx bridge/bridge-client.ts status               # 桥接状态
 *   npx tsx bridge/bridge-client.ts events               # 实时事件流
 */

const BASE = "http://127.0.0.1:8765";

async function api(method: string, path: string, body?: any) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok && res.status !== 200) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  const ct = res.headers.get("content-type") ?? "";
  return ct.includes("json") ? res.json() : res.text();
}

async function waitForResult(taskId: string, pollMs = 2000): Promise<any> {
  process.stdout.write(`\n⏳ Waiting for task ${taskId.slice(0, 8)}...`);
  while (true) {
    const task = await api("GET", `/result/${taskId}`);
    if (task.status === "done" || task.status === "error") {
      console.log(` ${task.status === "done" ? "✅" : "❌"}`);
      return task;
    }
    // Check for pending approvals mid-task
    const approvals: any[] = await api("GET", "/approvals");
    const mine = approvals.filter((a) => a.taskId === taskId);
    if (mine.length > 0) {
      console.log(`\n\n⚠️  Codex is asking for approval (${mine.length} pending):`);
      for (const a of mine) {
        console.log(`   [${a.id.slice(0, 8)}] ${a.type}: ${a.description}`);
      }
      console.log(
        `\n   Run: npx tsx bridge/bridge-client.ts approve <id>`
      );
      console.log(`   Or:  npx tsx bridge/bridge-client.ts reject <id> [reason]`);
      return { status: "waiting_approval", approvals: mine };
    }
    process.stdout.write(".");
    await new Promise((r) => setTimeout(r, pollMs));
  }
}

async function streamEvents() {
  console.log("📡 Streaming events (Ctrl+C to stop)...\n");
  const res = await fetch(`${BASE}/events`);
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    for (const line of text.split("\n")) {
      if (!line.startsWith("data:")) continue;
      try {
        const data = JSON.parse(line.slice(5).trim());
        const { source, msg, event } = data;
        if (source === "codex" && msg?.method) {
          console.log(`[codex→] ${msg.method}`, msg.params ? JSON.stringify(msg.params).slice(0, 120) : "");
        } else if (source === "bridge") {
          console.log(`[bridge] ${event}`, JSON.stringify(data).slice(0, 120));
        }
      } catch {}
    }
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const [, , cmd, ...args] = process.argv;

(async () => {
  try {
    switch (cmd) {
      case "task": {
        const prompt = args.join(" ");
        if (!prompt) { console.error("Usage: task <prompt>"); process.exit(1); }
        const result = await api("POST", "/task", { prompt, workdir: process.cwd() });
        console.log(`✅ Task created: ${result.taskId}`);
        console.log(`   Status: ${result.status}`);
        console.log(`\n   Monitor: npx tsx bridge/bridge-client.ts wait ${result.taskId}`);
        break;
      }

      case "wait": {
        const [taskId] = args;
        if (!taskId) { console.error("Usage: wait <taskId>"); process.exit(1); }
        const task = await waitForResult(taskId);
        if (task.result) {
          console.log("\n─── Codex Result ───────────────────────────────────");
          console.log(task.result);
          console.log("────────────────────────────────────────────────────");
        }
        if (task.error) console.error("Error:", task.error);
        break;
      }

      case "result": {
        const [taskId] = args;
        if (!taskId) { console.error("Usage: result <taskId>"); process.exit(1); }
        const task = await api("GET", `/result/${taskId}`);
        console.log(JSON.stringify(task, null, 2));
        break;
      }

      case "tasks": {
        const tasks = await api("GET", "/tasks");
        if (!tasks.length) { console.log("No tasks yet."); break; }
        for (const t of tasks) {
          const icon = { pending: "⏳", running: "🔄", done: "✅", error: "❌" }[t.status as string] ?? "?";
          console.log(`${icon} [${t.id.slice(0, 8)}] ${t.status.padEnd(8)} ${t.prompt.slice(0, 70)}`);
        }
        break;
      }

      case "approvals": {
        const list = await api("GET", "/approvals");
        if (!list.length) { console.log("No pending approvals."); break; }
        console.log(`\n⚠️  ${list.length} pending approval(s):\n`);
        for (const a of list) {
          console.log(`  ID:   ${a.id}`);
          console.log(`  Type: ${a.type}`);
          console.log(`  Desc: ${a.description}`);
          console.log(`  Task: ${a.taskId.slice(0, 8)}`);
          console.log();
        }
        break;
      }

      case "approve": {
        const [id] = args;
        if (!id) { console.error("Usage: approve <approvalId>"); process.exit(1); }
        const r = await api("POST", `/approve/${id}`, { approved: true });
        console.log(r.ok ? "✅ Approved" : "❌ Not found");
        break;
      }

      case "reject": {
        const [id, ...reasonParts] = args;
        if (!id) { console.error("Usage: reject <approvalId> [reason]"); process.exit(1); }
        const r = await api("POST", `/approve/${id}`, { approved: false, reason: reasonParts.join(" ") });
        console.log(r.ok ? "❌ Rejected" : "❌ Not found");
        break;
      }

      case "status": {
        const s = await api("GET", "/status");
        console.log("Bridge Status:");
        console.log(`  WebSocket : ${s.wsState}`);
        console.log(`  Tasks     : ${s.tasks}`);
        console.log(`  Approvals : ${s.pendingApprovals}`);
        console.log(`  SSE clients: ${s.sseClients}`);
        break;
      }

      case "events": {
        await streamEvents();
        break;
      }

      default:
        console.log(`Claude ↔ Codex Bridge Client

Commands:
  task <prompt>           Send task to Codex
  wait <taskId>           Wait for task completion (polls + shows approvals)
  result <taskId>         Get task result (raw JSON)
  tasks                   List all tasks
  approvals               List pending Codex→Claude approval requests
  approve <id>            Approve a Codex action
  reject <id> [reason]    Reject a Codex action
  status                  Bridge connection status
  events                  Stream all events in real-time

Workflow:
  1. Start bridge:  npm run bridge
  2. Send task:     npm run codex:task -- "review my code"
  3. Wait+approve:  npm run codex:wait -- <taskId>
`);
    }
  } catch (e: any) {
    if (e.message?.includes("ECONNREFUSED")) {
      console.error("❌ Bridge not running. Start it with: npm run bridge");
    } else {
      console.error("Error:", e.message);
    }
    process.exit(1);
  }
})();
