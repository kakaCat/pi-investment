/**
 * Codex MCP Server (stdio)
 *
 * Claude Code 通过 MCP 协议调用此服务，此服务转发到 bridge HTTP API。
 * 注册到 ~/.claude.json 后，Claude Code 可以直接用原生工具调用 Codex：
 *
 *   mcp__codex__task      — 发任务给 Codex，同步等待结果
 *   mcp__codex__review    — 让 Codex 做 code review
 *   mcp__codex__status    — 查看 bridge 状态
 *   mcp__codex__approvals — 查看待审批操作
 *   mcp__codex__approve   — 批准 Codex 的操作
 */

const BRIDGE = "http://127.0.0.1:8765";

// ─── MCP Protocol (JSON-RPC over stdio) ──────────────────────────────────────

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: any;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: any;
  error?: { code: number; message: string };
}

function send(msg: JsonRpcResponse) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

function ok(id: string | number, result: any) {
  send({ jsonrpc: "2.0", id, result });
}

function err(id: string | number | null, code: number, message: string) {
  send({ jsonrpc: "2.0", id, error: { code, message } });
}

// ─── Bridge HTTP helpers ──────────────────────────────────────────────────────

async function bridgeGet(path: string) {
  const res = await fetch(`${BRIDGE}${path}`);
  return res.json();
}

async function bridgePost(path: string, body: any) {
  const res = await fetch(`${BRIDGE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function ensureBridge(): Promise<boolean> {
  try {
    await bridgeGet("/status");
    return true;
  } catch {
    return false;
  }
}

// ─── Tool definitions ─────────────────────────────────────────────────────────

const TOOLS = [
  {
    name: "task",
    description:
      "发任务给 Codex（GPT-5.4）执行，Codex 可以读取文件、分析代码、给出建议。同步等待结果返回。适合：code review、分析 bug、给出修改方案、回答代码问题。",
    inputSchema: {
      type: "object",
      properties: {
        prompt: {
          type: "string",
          description: "给 Codex 的任务描述",
        },
        workdir: {
          type: "string",
          description: "工作目录，默认为项目根目录",
        },
        timeout: {
          type: "number",
          description: "超时毫秒数，默认 120000",
        },
      },
      required: ["prompt"],
    },
  },
  {
    name: "review",
    description:
      "让 Codex 做 code review。分析当前 git 变更或指定文件，找出 bug、边界条件问题、代码质量问题。",
    inputSchema: {
      type: "object",
      properties: {
        files: {
          type: "string",
          description: "要 review 的文件路径（逗号分隔），不填则 review git 最近变更",
        },
        focus: {
          type: "string",
          description: "review 重点，例如：'边界条件'、'性能'、'安全性'",
        },
      },
    },
  },
  {
    name: "status",
    description: "查看 Claude-Codex Bridge 的连接状态、任务数量、待审批数量",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "approvals",
    description: "查看 Codex 请求 Claude 审批的操作列表（文件修改、命令执行等）",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "approve",
    description: "批准或拒绝 Codex 请求的操作",
    inputSchema: {
      type: "object",
      properties: {
        id: { type: "string", description: "审批 ID" },
        approved: { type: "boolean", description: "true=批准, false=拒绝" },
        reason: { type: "string", description: "拒绝原因（可选）" },
      },
      required: ["id", "approved"],
    },
  },
];

// ─── Tool handlers ────────────────────────────────────────────────────────────

async function handleTool(name: string, args: any): Promise<string> {
  const alive = await ensureBridge();
  if (!alive && name !== "status") {
    return "❌ Bridge 未运行，请先执行: npm run bridge";
  }

  switch (name) {
    case "task": {
      const { prompt, workdir, timeout } = args;
      const result = await bridgePost("/task/sync", {
        prompt,
        workdir: workdir ?? process.cwd(),
        timeout: timeout ?? 120_000,
      });
      if (result.status === "error") {
        return `❌ Codex 执行失败: ${result.error}`;
      }
      return result.result || "(Codex 无输出)";
    }

    case "review": {
      const { files, focus } = args;
      let prompt = "请做 code review";
      if (files) prompt += `，检查这些文件: ${files}`;
      else prompt += "，检查最近的 git 变更";
      if (focus) prompt += `。重点关注: ${focus}`;
      prompt += "。用中文回答，列出具体问题和建议。";

      const result = await bridgePost("/task/sync", {
        prompt,
        workdir: process.cwd(),
        timeout: 120_000,
      });
      return result.result || result.error || "(无输出)";
    }

    case "status": {
      if (!alive) return "❌ Bridge 未运行 (http://localhost:8765 无响应)";
      const s = await bridgeGet("/status");
      return [
        `Bridge 状态: ${s.wsState === "connected" ? "✅ 已连接" : "❌ 断开"}`,
        `任务总数: ${s.tasks}`,
        `待审批: ${s.pendingApprovals}`,
        `SSE 客户端: ${s.sseClients}`,
      ].join("\n");
    }

    case "approvals": {
      const list = await bridgeGet("/approvals");
      if (!list.length) return "✅ 无待审批操作";
      return list
        .map(
          (a: any) =>
            `[${a.id.slice(0, 8)}] ${a.type}\n  ${a.description}\n  任务: ${a.taskId.slice(0, 8)}`
        )
        .join("\n\n");
    }

    case "approve": {
      const { id, approved, reason } = args;
      const r = await bridgePost(`/approve/${id}`, { approved, reason });
      return r.ok
        ? `${approved ? "✅ 已批准" : "❌ 已拒绝"}`
        : "❌ 未找到该审批 ID";
    }

    default:
      return `未知工具: ${name}`;
  }
}

// ─── MCP Request handler ──────────────────────────────────────────────────────

async function handleRequest(req: JsonRpcRequest) {
  const { id, method, params } = req;

  switch (method) {
    case "initialize":
      ok(id, {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "codex-bridge-mcp", version: "1.0.0" },
      });
      break;

    case "notifications/initialized":
      // no response needed
      break;

    case "tools/list":
      ok(id, { tools: TOOLS });
      break;

    case "tools/call": {
      const { name, arguments: args } = params;
      try {
        const text = await handleTool(name, args ?? {});
        ok(id, {
          content: [{ type: "text", text }],
        });
      } catch (e: any) {
        ok(id, {
          content: [{ type: "text", text: `Error: ${e.message}` }],
          isError: true,
        });
      }
      break;
    }

    default:
      err(id, -32601, `Method not found: ${method}`);
  }
}

// ─── Stdio loop ───────────────────────────────────────────────────────────────

let buffer = "";

process.stdin.setEncoding("utf8");
process.stdin.on("data", async (chunk: string) => {
  buffer += chunk;
  const lines = buffer.split("\n");
  buffer = lines.pop() ?? "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const req = JSON.parse(trimmed) as JsonRpcRequest;
      await handleRequest(req);
    } catch (e) {
      err(null, -32700, "Parse error");
    }
  }
});

process.stdin.on("end", () => process.exit(0));
process.stderr.write("[codex-mcp] MCP server started\n");
