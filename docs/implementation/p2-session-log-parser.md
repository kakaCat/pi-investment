# P2: Session 日志解析 - 详细实施方案

## 📋 目标

从 session 日志（conversation.json、events.jsonl、metadata.json）中提取深层决策信息，包括推理过程、错误原因、决策路径。

---

## 🎯 核心功能

### 1. 对话历史解析
- 提取用户意图
- 提取 Agent 推理过程
- 识别决策结论

### 2. 事件流解析
- 工具调用序列
- 错误和异常
- 性能指标（响应时间）

### 3. 决策路径分析
- 工具调用模式
- 成功/失败路径
- 决策效率

---

## 📁 文件结构

```
src/services/intelligence/
├── session-log-parser.ts           # 日志解析器
├── session-log-parser.test.ts      # 单元测试
├── session-path-analyzer.ts        # 决策路径分析器
└── types/
    └── session-analysis.ts         # 类型定义
```

---

## 🔧 实施步骤

### Step 1: 扩展类型定义

**文件**: `src/types/session-analysis.ts`（新增字段）

```typescript
/**
 * 增强的 Session 分析结果
 */
export interface SessionAnalysisEnhanced {
  // 基础信息（已有）
  sessionId: string;
  timestamp: string;
  decision: 'buy' | 'sell' | 'hold' | 'unknown';
  symbol?: string;
  outcome?: 'profit' | 'loss' | 'pending';
  
  // 新增：决策路径
  decisionPath: DecisionPath;
  
  // 新增：推理质量
  reasoning: ReasoningQuality;
  
  // 新增：用户交互
  interaction: UserInteraction;
  
  // 新增：决策时间分布
  timing: DecisionTiming;
  
  // 新增：错误分析
  errors: ErrorAnalysis;
  
  // 新增：工具效能（单次 session）
  toolPerformance: ToolPerformance[];
}

export interface DecisionPath {
  toolSequence: string[];           // 工具调用序列
  totalTools: number;               // 总工具数
  uniqueTools: number;              // 去重后的工具数
  parallelCalls: number;            // 并行调用次数
  sequentialCalls: number;          // 串行调用次数
  avgResponseTime: number;          // 平均响应时间（ms）
  totalDuration: number;            // 总耗时（ms）
  failedTools: FailedTool[];        // 失败的工具
}

export interface FailedTool {
  name: string;
  timestamp: string;
  reason: string;
  errorType: 'data' | 'logic' | 'timeout' | 'unknown';
  retried: boolean;
  retrySuccess?: boolean;
}

export interface ReasoningQuality {
  hasExplicitReasoning: boolean;    // 是否有明确推理
  reasoningLength: number;          // 推理文本长度
  dataSourcesCited: string[];       // 引用的数据源
  contradictions: number;           // 矛盾次数（前后不一致）
  confidenceLevel: 'high' | 'medium' | 'low';
}

export interface UserInteraction {
  userMessages: number;             // 用户消息数
  agentMessages: number;            // Agent 消息数
  clarificationAsked: number;       // Agent 澄清问题次数
  userCorrected: number;            // 用户纠正次数
  conversationRounds: number;       // 对话轮数
}

export interface DecisionTiming {
  dataGatheringTime: number;        // 数据收集耗时（ms）
  analysisTime: number;             // 分析耗时（ms）
  totalTime: number;                // 总耗时（ms）
  timeOfDay: 'morning' | 'afternoon' | 'afterHours';
  marketStatus: 'open' | 'closed';
}

export interface ErrorAnalysis {
  totalErrors: number;
  dataErrors: number;               // 数据获取失败
  logicErrors: number;              // 逻辑错误（如类型错误）
  timeoutErrors: number;            // 超时
  recoveryAttempts: number;         // 恢复尝试次数
  recoverySuccess: number;          // 恢复成功次数
}

export interface ToolPerformance {
  toolName: string;
  callCount: number;
  successCount: number;
  failureCount: number;
  avgResponseTime: number;
  totalTime: number;
}

/**
 * 决策路径模式
 */
export interface DecisionPathPattern {
  pattern: string[];                // 工具序列模式
  count: number;                    // 出现次数
  winRate: number;                  // 胜率
  avgReturn: number;                // 平均收益
  avgDuration: number;              // 平均耗时
  examples: string[];               // 示例 session ID
}
```

---

### Step 2: 实现日志解析器

**文件**: `src/services/intelligence/session-log-parser.ts`

```typescript
/**
 * Session 日志解析器
 * 
 * 解析 conversation.json、events.jsonl、metadata.json
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { existsSync } from 'fs';
import type {
  SessionAnalysisEnhanced,
  DecisionPath,
  ReasoningQuality,
  UserInteraction,
  DecisionTiming,
  ErrorAnalysis,
  ToolPerformance,
  FailedTool,
} from '../../types/session-analysis.js';

// ─── 主函数 ──────────────────────────────────────────────────────────────

/**
 * 解析 session 日志
 */
export async function parseSessionLog(
  sessionDir: string
): Promise<SessionAnalysisEnhanced | null> {
  try {
    // 检查目录是否存在
    if (!existsSync(sessionDir)) {
      console.warn(`[Session 解析] 目录不存在: ${sessionDir}`);
      return null;
    }
    
    // 读取三个文件
    const [metadata, conversation, events] = await Promise.all([
      readMetadata(sessionDir),
      readConversation(sessionDir),
      readEvents(sessionDir),
    ]);
    
    if (!metadata) {
      console.warn(`[Session 解析] metadata.json 不存在或无效`);
      return null;
    }
    
    // 提取基础信息
    const sessionId = metadata.session_key;
    const timestamp = metadata.start_time;
    
    // 解析决策路径
    const decisionPath = parseDecisionPath(events, metadata);
    
    // 解析推理质量
    const reasoning = parseReasoningQuality(conversation);
    
    // 解析用户交互
    const interaction = parseUserInteraction(conversation, metadata);
    
    // 解析时间分布
    const timing = parseDecisionTiming(events, metadata);
    
    // 解析错误
    const errors = parseErrors(events);
    
    // 解析工具性能
    const toolPerformance = parseToolPerformance(events);
    
    // 提取决策和结果（从 session-context.json）
    const { decision, symbol, outcome } = await extractDecisionInfo(sessionDir);
    
    return {
      sessionId,
      timestamp,
      decision,
      symbol,
      outcome,
      decisionPath,
      reasoning,
      interaction,
      timing,
      errors,
      toolPerformance,
    };
  } catch (error) {
    console.error(`[Session 解析] 解析失败:`, error);
    return null;
  }
}

// ─── 文件读取 ────────────────────────────────────────────────────────────

async function readMetadata(sessionDir: string): Promise<any | null> {
  const filePath = path.join(sessionDir, 'metadata.json');
  if (!existsSync(filePath)) return null;
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

async function readConversation(sessionDir: string): Promise<any | null> {
  const filePath = path.join(sessionDir, 'conversation.json');
  if (!existsSync(filePath)) return null;
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

async function readEvents(sessionDir: string): Promise<any[]> {
  const filePath = path.join(sessionDir, 'events.jsonl');
  if (!existsSync(filePath)) return [];
  
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    const lines = content.trim().split('\n');
    return lines.map(line => JSON.parse(line));
  } catch {
    return [];
  }
}

// ─── 决策路径解析 ────────────────────────────────────────────────────────

function parseDecisionPath(events: any[], metadata: any): DecisionPath {
  // 提取工具调用事件
  const toolEvents = events.filter(e => 
    e.event === 'tool.start' || 
    e.event === 'tool.end' || 
    e.event === 'tool.error'
  );
  
  // 构建工具调用序列
  const toolSequence: string[] = [];
  const toolTimings = new Map<string, { start: number; end?: number }>();
  const failedTools: FailedTool[] = [];
  
  for (const event of toolEvents) {
    const toolId = event.tool_id || `${event.tool_name}_${event.ts}`;
    
    if (event.event === 'tool.start') {
      toolSequence.push(event.tool_name);
      toolTimings.set(toolId, { start: event.ts });
    } else if (event.event === 'tool.end') {
      const timing = toolTimings.get(toolId);
      if (timing) {
        timing.end = event.ts;
      }
    } else if (event.event === 'tool.error') {
      failedTools.push({
        name: event.tool_name,
        timestamp: new Date(event.ts * 1000).toISOString(),
        reason: event.error || 'Unknown error',
        errorType: classifyErrorType(event.error),
        retried: false, // TODO: 检测重试
      });
    }
  }
  
  // 计算统计信息
  const totalTools = toolSequence.length;
  const uniqueTools = new Set(toolSequence).size;
  
  // 计算平均响应时间
  const responseTimes: number[] = [];
  for (const timing of toolTimings.values()) {
    if (timing.end) {
      responseTimes.push((timing.end - timing.start) * 1000); // 转换为 ms
    }
  }
  const avgResponseTime = responseTimes.length > 0
    ? responseTimes.reduce((sum, t) => sum + t, 0) / responseTimes.length
    : 0;
  
  // 计算总耗时
  const totalDuration = metadata.end_time && metadata.start_time
    ? (new Date(metadata.end_time).getTime() - new Date(metadata.start_time).getTime())
    : 0;
  
  // 检测并行调用（简化：相邻工具调用时间差 < 1s 认为是并行）
  let parallelCalls = 0;
  let sequentialCalls = 0;
  
  const startEvents = events.filter(e => e.event === 'tool.start');
  for (let i = 1; i < startEvents.length; i++) {
    const timeDiff = (startEvents[i].ts - startEvents[i - 1].ts) * 1000;
    if (timeDiff < 1000) {
      parallelCalls++;
    } else {
      sequentialCalls++;
    }
  }
  
  return {
    toolSequence,
    totalTools,
    uniqueTools,
    parallelCalls,
    sequentialCalls,
    avgResponseTime: Math.round(avgResponseTime),
    totalDuration,
    failedTools,
  };
}

function classifyErrorType(error: string): 'data' | 'logic' | 'timeout' | 'unknown' {
  if (!error) return 'unknown';
  
  const errorLower = error.toLowerCase();
  
  if (errorLower.includes('timeout') || errorLower.includes('timed out')) {
    return 'timeout';
  } else if (errorLower.includes('data') || errorLower.includes('fetch') || errorLower.includes('network')) {
    return 'data';
  } else if (errorLower.includes('type') || errorLower.includes('undefined') || errorLower.includes('null')) {
    return 'logic';
  } else {
    return 'unknown';
  }
}

// ─── 推理质量解析 ────────────────────────────────────────────────────────

function parseReasoningQuality(conversation: any): ReasoningQuality {
  if (!conversation || !conversation.messages) {
    return {
      hasExplicitReasoning: false,
      reasoningLength: 0,
      dataSourcesCited: [],
      contradictions: 0,
      confidenceLevel: 'low',
    };
  }
  
  const messages = conversation.messages;
  const agentMessages = messages.filter((m: any) => m.role === 'assistant');
  
  // 检查是否有明确推理
  let hasExplicitReasoning = false;
  let totalReasoningLength = 0;
  const dataSourcesCited = new Set<string>();
  
  for (const msg of agentMessages) {
    const content = msg.content || '';
    
    // 检测推理关键词
    if (
      content.includes('因为') ||
      content.includes('由于') ||
      content.includes('根据') ||
      content.includes('分析') ||
      content.includes('判断')
    ) {
      hasExplicitReasoning = true;
    }
    
    totalReasoningLength += content.length;
    
    // 提取数据源引用（简化：查找工具名称）
    const toolMentions = content.match(/get_\w+|analyze_\w+|calculate_\w+/g);
    if (toolMentions) {
      toolMentions.forEach(tool => dataSourcesCited.add(tool));
    }
  }
  
  // 检测矛盾（简化：查找"但是"、"然而"等转折词）
  let contradictions = 0;
  for (const msg of agentMessages) {
    const content = msg.content || '';
    contradictions += (content.match(/但是|然而|不过|相反/g) || []).length;
  }
  
  // 评估置信度
  let confidenceLevel: 'high' | 'medium' | 'low';
  if (hasExplicitReasoning && dataSourcesCited.size >= 3 && contradictions <= 1) {
    confidenceLevel = 'high';
  } else if (hasExplicitReasoning && dataSourcesCited.size >= 1) {
    confidenceLevel = 'medium';
  } else {
    confidenceLevel = 'low';
  }
  
  return {
    hasExplicitReasoning,
    reasoningLength: totalReasoningLength,
    dataSourcesCited: Array.from(dataSourcesCited),
    contradictions,
    confidenceLevel,
  };
}

// ─── 用户交互解析 ────────────────────────────────────────────────────────

function parseUserInteraction(conversation: any, metadata: any): UserInteraction {
  if (!conversation || !conversation.messages) {
    return {
      userMessages: 0,
      agentMessages: 0,
      clarificationAsked: 0,
      userCorrected: 0,
      conversationRounds: 0,
    };
  }
  
  const messages = conversation.messages;
  
  const userMessages = messages.filter((m: any) => m.role === 'user').length;
  const agentMessages = messages.filter((m: any) => m.role === 'assistant').length;
  
  // 检测澄清问题（Agent 消息中包含问号）
  let clarificationAsked = 0;
  for (const msg of messages) {
    if (msg.role === 'assistant' && msg.content && msg.content.includes('?')) {
      clarificationAsked++;
    }
  }
  
  // 检测用户纠正（用户消息中包含"不是"、"错了"等）
  let userCorrected = 0;
  for (const msg of messages) {
    if (msg.role === 'user' && msg.content) {
      const content = msg.content.toLowerCase();
      if (content.includes('不是') || content.includes('错了') || content.includes('不对')) {
        userCorrected++;
      }
    }
  }
  
  // 对话轮数（用户消息数）
  const conversationRounds = userMessages;
  
  return {
    userMessages,
    agentMessages,
    clarificationAsked,
    userCorrected,
    conversationRounds,
  };
}

// ─── 时间分布解析 ────────────────────────────────────────────────────────

function parseDecisionTiming(events: any[], metadata: any): DecisionTiming {
  // 提取工具调用时间
  const toolEvents = events.filter(e => e.event === 'tool.start' || e.event === 'tool.end');
  
  let dataGatheringTime = 0;
  let analysisTime = 0;
  
  // 简化：前50%的工具调用时间算数据收集，后50%算分析
  const midpoint = Math.floor(toolEvents.length / 2);
  
  for (let i = 0; i < toolEvents.length - 1; i++) {
    const timeDiff = (toolEvents[i + 1].ts - toolEvents[i].ts) * 1000;
    
    if (i < midpoint) {
      dataGatheringTime += timeDiff;
    } else {
      analysisTime += timeDiff;
    }
  }
  
  // 总耗时
  const totalTime = metadata.end_time && metadata.start_time
    ? new Date(metadata.end_time).getTime() - new Date(metadata.start_time).getTime()
    : 0;
  
  // 判断时间段
  const startTime = new Date(metadata.start_time);
  const hour = startTime.getHours();
  
  let timeOfDay: 'morning' | 'afternoon' | 'afterHours';
  if (hour >= 9 && hour < 12) {
    timeOfDay = 'morning';
  } else if (hour >= 13 && hour < 15) {
    timeOfDay = 'afternoon';
  } else {
    timeOfDay = 'afterHours';
  }
  
  // 判断市场状态（简化）
  const marketStatus = (hour >= 9 && hour < 15 && startTime.getDay() >= 1 && startTime.getDay() <= 5)
    ? 'open'
    : 'closed';
  
  return {
    dataGatheringTime: Math.round(dataGatheringTime),
    analysisTime: Math.round(analysisTime),
    totalTime,
    timeOfDay,
    marketStatus,
  };
}

// ─── 错误解析 ────────────────────────────────────────────────────────────

function parseErrors(events: any[]): ErrorAnalysis {
  const errorEvents = events.filter(e => e.event === 'tool.error' || e.event === 'error');
  
  let dataErrors = 0;
  let logicErrors = 0;
  let timeoutErrors = 0;
  
  for (const event of errorEvents) {
    const errorType = classifyErrorType(event.error || event.message);
    
    if (errorType === 'data') {
      dataErrors++;
    } else if (errorType === 'logic') {
      logicErrors++;
    } else if (errorType === 'timeout') {
      timeoutErrors++;
    }
  }
  
  // TODO: 检测恢复尝试
  const recoveryAttempts = 0;
  const recoverySuccess = 0;
  
  return {
    totalErrors: errorEvents.length,
    dataErrors,
    logicErrors,
    timeoutErrors,
    recoveryAttempts,
    recoverySuccess,
  };
}

// ─── 工具性能解析 ────────────────────────────────────────────────────────

function parseToolPerformance(events: any[]): ToolPerformance[] {
  const toolStats = new Map<string, {
    callCount: number;
    successCount: number;
    failureCount: number;
    totalTime: number;
  }>();
  
  const toolTimings = new Map<string, number>();
  
  for (const event of events) {
    if (event.event === 'tool.start') {
      const toolId = event.tool_id || `${event.tool_name}_${event.ts}`;
      toolTimings.set(toolId, event.ts);
      
      if (!toolStats.has(event.tool_name)) {
        toolStats.set(event.tool_name, {
          callCount: 0,
          successCount: 0,
          failureCount: 0,
          totalTime: 0,
        });
      }
      
      toolStats.get(event.tool_name)!.callCount++;
    } else if (event.event === 'tool.end') {
      const toolId = event.tool_id || `${event.tool_name}_${event.ts}`;
      const startTime = toolTimings.get(toolId);
      
      if (startTime) {
        const duration = (event.ts - startTime) * 1000;
        const stats = toolStats.get(event.tool_name);
        
        if (stats) {
          stats.successCount++;
          stats.totalTime += duration;
        }
      }
    } else if (event.event === 'tool.error') {
      const stats = toolStats.get(event.tool_name);
      if (stats) {
        stats.failureCount++;
      }
    }
  }
  
  // 转换为数组
  const result: ToolPerformance[] = [];
  
  for (const [toolName, stats] of toolStats.entries()) {
    result.push({
      toolName,
      callCount: stats.callCount,
      successCount: stats.successCount,
      failureCount: stats.failureCount,
      avgResponseTime: stats.successCount > 0
        ? Math.round(stats.totalTime / stats.successCount)
        : 0,
      totalTime: Math.round(stats.totalTime),
    });
  }
  
  return result;
}

// ─── 决策信息提取 ────────────────────────────────────────────────────────

async function extractDecisionInfo(sessionDir: string): Promise<{
  decision: 'buy' | 'sell' | 'hold' | 'unknown';
  symbol?: string;
  outcome?: 'profit' | 'loss' | 'pending';
}> {
  const contextPath = path.join(sessionDir, 'session-context.json');
  
  if (!existsSync(contextPath)) {
    return { decision: 'unknown' };
  }
  
  try {
    const content = await fs.readFile(contextPath, 'utf-8');
    const context = JSON.parse(content);
    
    return {
      decision: context.decision || 'unknown',
      symbol: context.symbol,
      outcome: context.outcome || 'pending',
    };
  } catch {
    return { decision: 'unknown' };
  }
}

// ─── 导出 ────────────────────────────────────────────────────────────────

export {
  parseDecisionPath,
  parseReasoningQuality,
  parseUserInteraction,
  parseDecisionTiming,
  parseErrors,
  parseToolPerformance,
};
```

---

### Step 3: 集成到 Session 分析器

**文件**: `src/services/intelligence/session-analyzer.ts`（修改）

```typescript
import { parseSessionLog } from './session-log-parser.js';

// 在 analyzeSessionsAndCalculateEfficiency 函数中集成

export function analyzeSessionsAndCalculateEfficiency(
  piDir: string,
  trades: Trade[],
  windowDays?: number
): ToolEfficiency[] {
  // ... 现有代码 ...
  
  // 新增：解析 session 日志
  const enhancedSessions: SessionAnalysisEnhanced[] = [];
  
  for (const sessionId of sessionIds) {
    const sessionDir = path.join(piDir, 'sessions', sessionId);
    const parsed = await parseSessionLog(sessionDir);
    
    if (parsed) {
      enhancedSessions.push(parsed);
    }
  }
  
  console.log(`[Session 分析] 成功解析 ${enhancedSessions.length}/${sessionIds.length} 个 session`);
  
  // 使用增强的 session 数据计算工具效能
  // ... 更新工具效能计算逻辑 ...
  
  return toolStats;
}
```

---

## ✅ 验收标准

### 功能测试
- [ ] 能成功解析 conversation.json
- [ ] 能成功解析 events.jsonl
- [ ] 能成功解析 metadata.json
- [ ] 能正确提取工具调用序列
- [ ] 能正确识别错误类型
- [ ] 能正确计算响应时间

### 数据质量
- [ ] 解析成功率 > 90%
- [ ] 工具序列完整性 > 95%
- [ ] 错误分类准确率 > 80%

### 性能测试
- [ ] 单个 session 解析耗时 < 100ms
- [ ] 批量解析 100 个 session < 10s

---

## 🚀 执行命令

```bash
# 1. 创建类型定义
# 编辑 src/types/session-analysis.ts

# 2. 创建日志解析器
touch src/services/intelligence/session-log-parser.ts

# 3. 运行测试
npm run test:session-parser

# 4. 集成到 session-analyzer
# 编辑 src/services/intelligence/session-analyzer.ts

# 5. 运行完整测试
npx tsx src/scripts/test-evolution-session.ts
```

---

## 📝 注意事项

1. **大文件处理**: events.jsonl 可能很大，考虑流式读取
2. **错误容忍**: 单个 session 解析失败不应影响整体流程
3. **性能优化**: 批量解析时使用并行处理
4. **数据验证**: 检查解析结果的合理性
5. **向后兼容**: 旧版本 session 可能缺少某些字段

---

## 🔗 下一步

完成 P2 后，继续实施 **P3: 工具效能增强**。
