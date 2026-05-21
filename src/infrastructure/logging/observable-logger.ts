/**
 * Observable Logger - 实时记录 Agent 详细追踪信息
 *
 * 通过包装 Agent 的方法来记录详细的执行信息
 */

import { appendFileSync, writeFileSync, existsSync, mkdirSync, readFileSync } from 'fs';
import { join } from 'path';
import { randomBytes } from 'crypto';

const LOGS_DIR = join(process.cwd(), '.pi-invest', 'sessions');
const RUN_ID = randomBytes(4).toString('hex');
let sessionKey: string;
let sessionDir: string;
let eventsFile: string;
let conversationFile: string;
let metadataFile: string;

// 导出 session 信息供其他模块使用
export function getSessionDir(): string {
  return sessionDir;
}

export function getRunId(): string {
  return RUN_ID;
}

export function getSessionKey(): string {
  return sessionKey;
}

/** 获取当前会话的对话消息（用于跨重启恢复） */
export function getConversationMessages(): Array<{ role: string; content: string; timestamp: string }> {
  return [...conversation.messages];
}

let turnIndex = 0;
let llmCalls = 0;
let toolCalls = 0;
let totalTokens = 0;
let totalCost = 0;
let toolCallsInCurrentTurn = 0;

const conversation = {
  session_key: '',
  messages: [] as any[],
};

const metadata = {
  session_key: '',
  run_id: RUN_ID,
  start_time: new Date().toISOString(),
  model: 'deepseek-chat',
  cwd: process.cwd(),
  workspace: process.cwd(),
};

// 写入事件
export function logEvent(event: string, data: any = {}) {
  const entry = {
    ts: Date.now() / 1000,
    event,
    run_id: RUN_ID,
    ...data,
  };

  if (eventsFile) {
    appendFileSync(eventsFile, JSON.stringify(entry) + '\n');
  }
}

// 保存对话
function saveConversation() {
  if (conversationFile) {
    writeFileSync(conversationFile, JSON.stringify(conversation, null, 2));
  }
}

// 保存元数据
function saveMetadata() {
  if (metadataFile) {
    writeFileSync(metadataFile, JSON.stringify(metadata, null, 2));
  }
}

// 初始化会话
export function initSession(sessionId?: string) {
  const shouldResumeExisting = Boolean(sessionId);
  // 格式: YYYYMMDDHHmmss_run_id (例如: 20260316170255_4d0b4701)
  const now = new Date();
  const timeStr = now.toISOString()
    .replace(/[-:]/g, '')
    .slice(0, 14); // YYYYMMDDHHmmss
  sessionKey = sessionId || `${timeStr}_${RUN_ID}`;
  sessionDir = join(LOGS_DIR, sessionKey);

  if (!existsSync(sessionDir)) {
    mkdirSync(sessionDir, { recursive: true });
  }

  eventsFile = join(sessionDir, 'events.jsonl');
  conversationFile = join(sessionDir, 'conversation.json');
  metadataFile = join(sessionDir, 'metadata.json');

  // 创建子目录
  const tasksDir = join(sessionDir, 'tasks');
  const screenshotsDir = join(sessionDir, 'screenshots');
  const workspaceDir = join(sessionDir, 'workspace');

  mkdirSync(tasksDir, { recursive: true });
  mkdirSync(screenshotsDir, { recursive: true });
  mkdirSync(workspaceDir, { recursive: true });

  if (shouldResumeExisting && existsSync(conversationFile)) {
    try {
      const existingConversation = JSON.parse(readFileSync(conversationFile, "utf-8"));
      conversation.session_key = existingConversation.session_key || sessionKey;
      conversation.messages = Array.isArray(existingConversation.messages) ? existingConversation.messages : [];
    } catch {
      conversation.session_key = sessionKey;
      conversation.messages = [];
    }
  } else {
    conversation.session_key = sessionKey;
    conversation.messages = [];
  }

  if (shouldResumeExisting && existsSync(metadataFile)) {
    try {
      Object.assign(metadata, JSON.parse(readFileSync(metadataFile, "utf-8")));
    } catch {
      // keep current metadata
    }
  }
  (metadata as any).session_key = sessionKey;

  logEvent('session.start', {
    session_key: sessionKey,
    session_dir: sessionDir,
  });

  if (!shouldResumeExisting || !existsSync(metadataFile)) {
    saveMetadata();
  }
  if (!shouldResumeExisting || !existsSync(conversationFile)) {
    saveConversation();
  }

  console.log(`\n📊 Observable Logger 已启动`);
  console.log(`📁 Session: ${sessionKey}`);
  console.log(`📂 Directory: ${sessionDir}\n`);

  return sessionKey;
}

// 记录回合开始
export function logTurnStart() {
  toolCallsInCurrentTurn = 0;
  logEvent('turn.start', {
    turn_index: turnIndex,
  });
}

// 记录用户输入
export function logUserInput(content: string) {
  logEvent('user.input', {
    turn_index: turnIndex,
    source: 'interactive',
    content_length: content.length,
    content_preview: content.substring(0, 200),
  });

  conversation.messages.push({
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  });

  saveConversation();
}

// 记录 Agent 开始
export function logAgentStart(prompt?: string) {
  logEvent('agent.start', {
    turn_index: turnIndex,
    prompt: prompt?.substring(0, 500),
    prompt_length: prompt?.length,
    history_length: conversation.messages.length,
  });
}

// 记录 LLM 开始
export function logLLMStart(model: string, promptCount: number, fullPrompt?: string) {
  const llmRunId = randomBytes(8).toString('hex');

  logEvent('llm.start', {
    turn_index: turnIndex,
    llm_run_id: llmRunId,
    model,
    prompt_count: promptCount,
    full_prompt: fullPrompt?.substring(0, 1000), // 记录前 1000 字符
  });

  return llmRunId;
}

// 记录 LLM 结束
export function logLLMEnd(llmRunId: string, usage: any, output?: string, durationMs?: number, reasoning?: string) {
  llmCalls++;
  const normalizedUsage = normalizeUsage(usage);
  totalTokens += normalizedUsage.totalTokens;
  totalCost += normalizedUsage.cost.total;

  const maxTokens = 32000; // DeepSeek context window
  const contextUsage = normalizedUsage.input ? (normalizedUsage.input / maxTokens * 100).toFixed(1) : 0;

  logEvent('llm.end', {
    turn_index: turnIndex,
    llm_run_id: llmRunId,
    input_tokens: normalizedUsage.input,
    output_tokens: normalizedUsage.output,
    total_tokens: normalizedUsage.totalTokens,
    context_usage_percent: contextUsage,
    cost: normalizedUsage.cost.total,
    duration_ms: durationMs,
    reasoning: reasoning,
    output: output,
  });
}

function serializeError(error: any): any {
  if (!error) return null;
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
  }
  return error;
}

// 记录工具调用
export function logToolCall(toolName: string, toolId: string, input: any) {
  toolCalls++;
  toolCallsInCurrentTurn++;

  logEvent('tool.call', {
    turn_index: turnIndex,
    tool_name: toolName,
    tool_id: toolId,
    params: input ?? null,
    params_length: input == null ? 0 : JSON.stringify(input).length,
    start_time: Date.now(),
  });
}

// 记录工具结果
export function logToolResult(toolName: string, toolId: string, result: any, error?: any, durationMs?: number) {
  logEvent('tool.result', {
    turn_index: turnIndex,
    tool_name: toolName,
    tool_id: toolId,
    success: !error,
    error: serializeError(error),
    result: result ?? null,
    result_length: result ? JSON.stringify(result).length : 0,
    duration_ms: durationMs,
  });
}

// 记录 Agent 结束
export function logAgentEnd(stopReason: string, usage: any, output?: string) {
  const normalizedUsage = normalizeUsage(usage);
  logEvent('agent.end', {
    turn_index: turnIndex,
    stop_reason: stopReason,
    output: output?.substring(0, 200),
    output_length: output?.length,
    total_steps: 1,
    llm_calls: llmCalls,
    tool_calls: toolCalls,
    usage: normalizedUsage,
  });

  if (output) {
    conversation.messages.push({
      role: 'assistant',
      content: output,
      timestamp: new Date().toISOString(),
    });

    saveConversation();
  }
}

function normalizeUsage(usage: any) {
  const input = usage?.input ?? usage?.input_tokens ?? 0;
  const output = usage?.output ?? usage?.output_tokens ?? 0;
  const cacheRead = usage?.cacheRead ?? usage?.cache_read ?? 0;
  const cacheWrite = usage?.cacheWrite ?? usage?.cache_write ?? 0;
  const totalTokens = usage?.totalTokens ?? usage?.total_tokens ?? input + output + cacheRead + cacheWrite;
  const cost = usage?.cost ?? {};
  return {
    input,
    output,
    cacheRead,
    cacheWrite,
    totalTokens,
    cost: {
      input: cost.input ?? 0,
      output: cost.output ?? 0,
      cacheRead: cost.cacheRead ?? cost.cache_read ?? 0,
      cacheWrite: cost.cacheWrite ?? cost.cache_write ?? 0,
      total: cost.total ?? 0,
    },
  };
}

// 记录回合结束
export function logTurnEnd() {
  logEvent('turn.end', {
    turn_index: turnIndex,
    tools_count: toolCallsInCurrentTurn,
    is_parallel: toolCallsInCurrentTurn > 1,
    execution_mode: toolCallsInCurrentTurn > 1 ? 'parallel' : toolCallsInCurrentTurn === 1 ? 'serial' : 'no_tools',
  });

  turnIndex++;

  // 更新元数据
  (metadata as any).total_turns = turnIndex;
  (metadata as any).total_messages = conversation.messages.length;
  (metadata as any).total_tokens = totalTokens;
  (metadata as any).total_cost = totalCost;
  (metadata as any).llm_calls = llmCalls;
  (metadata as any).tool_calls = toolCalls;

  saveMetadata();
}

// 记录会话结束
export function logSessionEnd() {
  (metadata as any).end_time = new Date().toISOString();

  logEvent('session.end', {
    turn_index: turnIndex,
    total_messages: conversation.messages.length,
    total_tokens: totalTokens,
    total_cost: totalCost,
  });

  saveMetadata();

  console.log(`\n📊 会话统计:`);
  console.log(`   Session: ${sessionKey}`);
  console.log(`   回合数: ${turnIndex}`);
  console.log(`   消息数: ${conversation.messages.length}`);
  console.log(`   LLM 调用: ${llmCalls}`);
  console.log(`   工具调用: ${toolCalls}`);
  console.log(`   Token: ${totalTokens}`);
  console.log(`   成本: $${totalCost.toFixed(4)}`);
  console.log(`\n📁 文件:`);
  console.log(`   对话: ${conversationFile}`);
  console.log(`   追踪: ${eventsFile}`);
  console.log(`   元数据: ${metadataFile}\n`);
}

// 记录加载的 bootstrap 文件
export function logBootstrapFiles(bootstrapData: Record<string, string>) {
  const files = Object.entries(bootstrapData).map(([name, content]) => ({
    name,
    length: content.length,
    preview: content.substring(0, 200),
    full: content,
  }));
  logEvent('bootstrap.loaded', {
    files,
    total_files: files.length,
    total_length: files.reduce((sum, f) => sum + f.length, 0),
  });
}

// 记录系统提示词
export function logSystemPrompt(systemPrompt: string, turnIndex: number) {
  logEvent('system.prompt', {
    turn_index: turnIndex,
    length: systemPrompt.length,
    preview: systemPrompt.substring(0, 500),
    full: systemPrompt,
  });
}

// 记录 subagent 开始
export function logSubagentStart(agentType: 'subagent' | 'plan' | 'clarify' | 'reflect', prompt: string, parentTurnIndex?: number) {
  logEvent(`${agentType}.start`, {
    turn_index: turnIndex,
    parent_turn_index: parentTurnIndex ?? turnIndex,
    prompt: prompt.substring(0, 500),
    prompt_length: prompt.length,
  });
}

// 记录 subagent 结束
export function logSubagentEnd(agentType: 'subagent' | 'plan' | 'clarify' | 'reflect', output: string, llmCallCount: number, toolCallCount: number, durationMs: number) {
  logEvent(`${agentType}.end`, {
    turn_index: turnIndex,
    output: output.substring(0, 200),
    output_length: output.length,
    llm_calls: llmCallCount,
    tool_calls: toolCallCount,
    duration_ms: durationMs,
  });
}

export const observableLogger = {
  initSession,
  logTurnStart,
  logUserInput,
  logAgentStart,
  logLLMStart,
  logLLMEnd,
  logToolCall,
  logToolResult,
  logAgentEnd,
  logTurnEnd,
  logSessionEnd,
  logBootstrapFiles,
  logSystemPrompt,
  logSubagentStart,
  logSubagentEnd,
};
