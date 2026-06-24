/**
 * Session Memory Saver - 会话结束时自动保存记忆
 *
 * 在会话结束时派发独立 agent 回顾对话历史，提取关键信息并写入记忆
 */
import { createAgentSession, type AgentSession } from "@mariozechner/pi-coding-agent";
import { createDeepSeekModel } from "../../config/config.js";
import { memoryWriteTool, memorySearchTool } from "../../infrastructure/tools/agent/memory-tool.js";
import { getMessages, type SessionMessage } from "../../core/agent/session-adapter.js";

export interface SessionSummary {
  keyDecisions: string[];
  importantFacts: string[];
  userPreferences: string[];
  unfinishedTasks: string[];
  lessonsLearned: string[];
}

/**
 * 异步保存会话记忆（不阻塞主进程）
 */
export async function saveSessionMemoryAsync(
  mainSession: AgentSession,
  options: {
    timeout?: number;  // 超时时间（毫秒），默认 30 秒
    verbose?: boolean; // 是否输出详细日志
  } = {}
): Promise<void> {
  const { timeout = 30000, verbose = false } = options;

  // 异步执行，不阻塞主进程
  Promise.race([
    saveSessionMemoryInternal(mainSession, verbose),
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Memory save timeout")), timeout)
    )
  ]).catch((error: unknown) => {
    console.error(`⚠️  会话记忆保存失败: ${error instanceof Error ? error.message : String(error)}`);
  });
}

/**
 * 同步保存会话记忆（阻塞直到完成）
 */
export async function saveSessionMemorySync(
  mainSession: AgentSession,
  options: {
    timeout?: number;
    verbose?: boolean;
  } = {}
): Promise<void> {
  const { timeout = 30000, verbose = false } = options;

  try {
    await Promise.race([
      saveSessionMemoryInternal(mainSession, verbose),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("Memory save timeout")), timeout)
      )
    ]);
  } catch (error) {
    console.error(`❌ 会话记忆保存失败: ${error instanceof Error ? error.message : String(error)}`);
    throw error;
  }
}

/**
 * 内部实现：创建独立 agent 来保存记忆
 */
async function saveSessionMemoryInternal(
  mainSession: AgentSession,
  verbose: boolean
): Promise<void> {
  if (verbose) {
    console.log("🧠 启动会话记忆保存 agent...");
  }

  // 获取主会话的消息历史
  const messages = getMessages(mainSession);

  // 过滤出用户和助手的对话（排除系统消息）
  const conversationHistory = messages
    .filter((msg: SessionMessage) => msg.role === "user" || msg.role === "assistant")
    .slice(-20)  // 只取最近 20 条消息，避免上下文过长
    .map((msg: SessionMessage) => {
      const content = typeof msg.content === "string"
        ? msg.content
        : Array.isArray(msg.content)
          ? msg.content.find((c: unknown) => typeof c === "object" && c !== null && "text" in c)?.text || ""
          : "";
      return `${msg.role === "user" ? "User" : "Assistant"}: ${content.slice(0, 500)}`;
    })
    .join("\n\n");

  if (!conversationHistory.trim()) {
    if (verbose) {
      console.log("⚠️  没有对话历史，跳过记忆保存");
    }
    return;
  }

  // 创建独立的 memory saver agent
  // @ts-ignore - Type mismatch from SDK update
  const { session: memorySaverSession } = await createAgentSession({
    cwd: process.cwd(),
    model: createDeepSeekModel(),
    systemPrompt: buildMemorySaverSystemPrompt(),
    customTools: [memoryWriteTool, memorySearchTool],
    skills: [],
  } as any);

  // 构建 prompt
  const prompt = buildMemorySaverPrompt(conversationHistory);

  if (verbose) {
    console.log("🔍 分析会话历史并提取关键信息...");
  }

  try {
    // 执行记忆保存
    await memorySaverSession.prompt(prompt);

    if (verbose) {
      console.log("✅ 会话记忆保存完成");
    }
  } catch (error) {
    if (verbose) {
      console.error(`❌ Memory saver agent 执行失败: ${error instanceof Error ? error.message : String(error)}`);
    }
    throw error;
  }
}

/**
 * 构建 memory saver agent 的系统提示词（参考 Claude Code 的结构化格式）
 */
function buildMemorySaverSystemPrompt(): string {
  return `You are a session memory documentation agent. Your job is to create a structured summary of this conversation session following Claude Code's session memory format.

## Your Task

Analyze the conversation history and create a comprehensive session summary with these sections:

### 1. Session Title
A concise title (one line) describing the main task or focus of this session.

### 2. Current State
Detailed description of:
- What was accomplished in this session
- Current progress and status
- What's pending or needs follow-up
- Any blockers or issues

### 3. Task Specification
- Original requirements and goals
- Constraints and limitations
- Success criteria
- Any changes to the original plan

### 4. Files and Functions
List of files created, modified, or analyzed:
- File paths
- Key functions or classes
- Purpose of each file

### 5. Workflow
Step-by-step description of the work process:
1. First step taken
2. Second step taken
3. ...

### 6. Errors & Corrections
Problems encountered and how they were resolved:
- Error descriptions
- Root causes
- Solutions applied
- Lessons learned

### 7. Codebase and System Documentation
Key information about the codebase:
- Architecture decisions
- Design patterns used
- Integration points
- Dependencies

### 8. Learnings
Important lessons from this session:
- What worked well
- What didn't work
- Best practices discovered
- Things to avoid in the future

### 9. Key Results
Main outcomes and deliverables:
- Features implemented
- Bugs fixed
- Documentation created
- Tests added

### 10. Worklog
Chronological log of major activities:
1. [Time/Order] Activity description
2. [Time/Order] Activity description
3. ...

## Guidelines

- Write in a structured, factual manner
- Focus on information valuable for future sessions
- Be specific with file paths, function names, and technical details
- Include both successes and failures
- Write self-contained descriptions (no "this session" or "today")

## Output Format

Use memory_write to save the complete structured summary as a single memory entry with category "session_summary".

Example:
memory_write(
  content: "# Session Title\\n[title]\\n\\n# Current State\\n[state]\\n\\n# Task Specification\\n[spec]\\n\\n# Files and Functions\\n[files]\\n\\n# Workflow\\n[workflow]\\n\\n# Errors & Corrections\\n[errors]\\n\\n# Codebase and System Documentation\\n[docs]\\n\\n# Learnings\\n[learnings]\\n\\n# Key Results\\n[results]\\n\\n# Worklog\\n[worklog]",
  category: "session_summary"
)

After saving, provide a brief confirmation of what was documented.`;
}

/**
 * 构建 memory saver agent 的 prompt
 */
function buildMemorySaverPrompt(conversationHistory: string): string {
  return `Create a comprehensive structured summary of this conversation session following the 10-section format specified in your system prompt.

## Conversation History

${conversationHistory}

## Instructions

1. Carefully analyze the entire conversation history
2. Extract information for all 10 sections:
   - Session Title
   - Current State
   - Task Specification
   - Files and Functions
   - Workflow
   - Errors & Corrections
   - Codebase and System Documentation
   - Learnings
   - Key Results
   - Worklog
3. Create a single structured markdown document with all sections
4. Use memory_write to save the complete summary with category "session_summary"
5. Provide a brief confirmation after saving

Begin creating the structured session summary now.`;
}

/**
 * 提取会话摘要（不保存，仅用于日志）
 */
export async function extractSessionSummary(
  mainSession: AgentSession
): Promise<SessionSummary> {
  const messages = getMessages(mainSession);

  // 简单的启发式提取（可以后续用 LLM 改进）
  const summary: SessionSummary = {
    keyDecisions: [],
    importantFacts: [],
    userPreferences: [],
    unfinishedTasks: [],
    lessonsLearned: [],
  };

  // 扫描消息中的关键词
  for (const msg of messages.slice(-10)) {
    const content = typeof msg.content === "string"
      ? msg.content
      : Array.isArray(msg.content)
        ? msg.content.find((c: unknown) => typeof c === "object" && c !== null && "text" in c)?.text || ""
        : "";

    const lower = content.toLowerCase();

    if (lower.includes("decided") || lower.includes("chose") || lower.includes("选择")) {
      summary.keyDecisions.push(content.slice(0, 200));
    }
    if (lower.includes("prefer") || lower.includes("like") || lower.includes("喜欢")) {
      summary.userPreferences.push(content.slice(0, 200));
    }
    if (lower.includes("todo") || lower.includes("未完成") || lower.includes("继续")) {
      summary.unfinishedTasks.push(content.slice(0, 200));
    }
    if (lower.includes("learned") || lower.includes("fixed") || lower.includes("解决")) {
      summary.lessonsLearned.push(content.slice(0, 200));
    }
  }

  return summary;
}
