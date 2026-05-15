# Session Memory Saver - 会话记忆自动保存

## 概述

在会话结束时自动派发独立 agent 来回顾对话历史，提取关键信息并写入长期记忆。

## 设计理念

参考 Claude Code 的实现方式：
- 使用独立的 agent 来处理记忆保存（不污染主会话上下文）
- 异步执行，不阻塞主进程退出
- 创建结构化的会话摘要（10个标准section）
- 单一文档格式，便于回顾和检索

## 架构

```
主会话结束
    ↓
派发 Memory Saver Agent（独立会话）
    ↓
读取主会话历史（最近 20 条消息）
    ↓
分析并创建结构化会话摘要
    ↓
调用 memory_write 工具保存（category: session_summary）
    ↓
返回保存确认
```

## 核心组件

### 1. SessionMemorySaver 服务

**位置：** `src/services/intelligence/session-memory-saver.ts`

**主要函数：**

```typescript
// 异步保存（不阻塞）
saveSessionMemoryAsync(session, options)

// 同步保存（阻塞直到完成）
saveSessionMemorySync(session, options)

// 提取会话摘要（不保存）
extractSessionSummary(session)
```

**选项：**
- `timeout`: 超时时间（毫秒），默认 30 秒
- `verbose`: 是否输出详细日志，默认 false

### 2. Memory Saver Agent

**系统提示词：**
- 专门的会话摘要 agent
- 遵循 Claude Code 的10个section结构化格式
- 清晰的文档组织要求

**会话摘要的10个section：**
1. **Session Title** - 会话主题（一行概括）
2. **Current State** - 当前状态（完成情况、进度、待办、阻塞）
3. **Task Specification** - 任务规格（需求、约束、成功标准）
4. **Files and Functions** - 文件和函数（创建/修改的文件、关键函数）
5. **Workflow** - 工作流程（分步描述工作过程）
6. **Errors & Corrections** - 错误和修正（问题、原因、解决方案）
7. **Codebase and System Documentation** - 代码库文档（架构决策、设计模式）
8. **Learnings** - 经验总结（有效方法、无效方法、最佳实践）
9. **Key Results** - 关键成果（实现的功能、修复的bug、创建的文档）
10. **Worklog** - 工作日志（按时间顺序记录主要活动）

**记忆类型：**
- `session_summary` - 结构化会话摘要（单一文档）

## 集成点

### 1. 进程退出时（SIGINT）

```typescript
process.on('SIGINT', async () => {
  console.log("\n🧠 保存会话记忆...");
  
  saveSessionMemoryAsync(session, {
    timeout: 30000,
    verbose: true
  });
  
  await new Promise(resolve => setTimeout(resolve, 500));
  
  // ... 其他清理工作
  process.exit(0);
});
```

### 2. 正常退出时

```typescript
// 交互式模式结束后
await mode.run();

console.log("\n🧠 保存会话记忆...");
await saveSessionMemoryAsync(session, {
  timeout: 30000,
  verbose: true
});

await new Promise(resolve => setTimeout(resolve, 1000));
```

## 工作流程

### 1. 会话历史提取

```typescript
const messages = getMessages(mainSession);

const conversationHistory = messages
  .filter(msg => msg.role === "user" || msg.role === "assistant")
  .slice(-20)  // 只取最近 20 条消息
  .map(msg => `${msg.role}: ${content.slice(0, 500)}`)
  .join("\n\n");
```

### 2. 创建独立 Agent

```typescript
const memorySaverSession = await createAgentSession({
  cwd: process.cwd(),
  model: createDeepSeekModel(),
  systemPrompt: buildMemorySaverSystemPrompt(),
  customTools: [memoryWriteTool, memorySearchTool],
  skills: [],
});
```

### 3. 执行记忆保存

```typescript
const prompt = buildMemorySaverPrompt(conversationHistory);
await memorySaverSession.prompt(prompt);
```

### 4. Agent 创建结构化摘要

Memory Saver Agent 会自动：
1. 分析对话历史
2. 提取10个section的信息
3. 创建结构化markdown文档
4. 调用 `memory_write` 工具保存（category: session_summary）
5. 返回保存确认

## 示例输出

```
🧠 保存会话记忆...
🧠 启动会话记忆保存 agent...
🔍 分析会话历史并提取关键信息...

[Memory Saver Agent 执行]
- 创建结构化会话摘要（10个section）
- memory_write(content: "# Session Title\n重构akshare-ts模块...\n\n# Current State\n...", category: "session_summary")

✅ 会话记忆保存完成

Saved session summary with 10 sections:
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
```

## 存储位置

记忆保存到：
```
.pi-invest/memory/daily/{date}.jsonl
```

每条记忆格式：
```json
{
  "ts": "2026-05-15T10:30:00.000Z",
  "category": "session_summary",
  "content": "# Session Title\n重构akshare-ts模块为分层架构\n\n# Current State\n完成1248行代码重构为11个模块文件...\n\n# Task Specification\n...\n\n# Files and Functions\n...\n\n# Workflow\n...\n\n# Errors & Corrections\n...\n\n# Codebase and System Documentation\n...\n\n# Learnings\n...\n\n# Key Results\n...\n\n# Worklog\n..."
}
```

## 测试

### 单元测试

```bash
npm test -- session-memory-saver.test.ts
```

### 手动测试

```bash
npm run memory-saver-test
```

或直接运行：
```bash
tsx src/scripts/test-memory-saver.ts
```

## 配置

### 超时时间

默认 30 秒，可以调整：

```typescript
saveSessionMemoryAsync(session, {
  timeout: 60000  // 60 秒
});
```

### 详细日志

```typescript
saveSessionMemoryAsync(session, {
  verbose: true  // 输出详细日志
});
```

### 禁用功能

如果不想自动保存记忆，注释掉 `api/index.ts` 中的调用：

```typescript
// saveSessionMemoryAsync(session, { ... });
```

## 优势

### 1. 不阻塞主进程
- 异步执行，用户可以立即退出
- 超时保护，不会无限等待

### 2. 独立上下文
- 使用独立 agent，不污染主会话
- 专门的系统提示词，提取质量高

### 3. 结构化格式
- 遵循 Claude Code 的10个section标准
- 单一文档，便于回顾
- 完整的会话上下文保留

### 4. 可测试
- 完整的单元测试覆盖
- 手动测试工具

## 注意事项

### 1. Token 消耗
- 每次会话结束会消耗额外的 token
- 只分析最近 20 条消息，控制成本

### 2. 超时处理
- 默认 30 秒超时
- 超时后静默失败，不影响主进程

### 3. 记忆质量
- 依赖 LLM 的理解能力
- 可能会遗漏或误判某些信息

### 4. 存储空间
- 每天一个 JSONL 文件
- 需要定期清理旧文件

## 未来改进

1. **增量保存** - 在会话过程中定期保存，而不是只在结束时
2. **记忆去重** - 避免保存重复信息
3. **记忆合并** - 将相关记忆合并成更完整的条目
4. **优先级排序** - 根据重要性对记忆排序
5. **用户确认** - 在保存前让用户确认关键记忆

## 相关文件

- `src/services/intelligence/session-memory-saver.ts` - 核心实现
- `src/services/intelligence/session-memory-saver.test.ts` - 单元测试
- `src/services/intelligence/memory-store.ts` - 记忆存储
- `src/infrastructure/tools/memory-tool.ts` - 记忆工具
- `src/api/index.ts` - 集成点
- `src/scripts/test-memory-saver.ts` - 测试脚本
