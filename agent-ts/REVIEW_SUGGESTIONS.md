# Agent-TS 代码审查 - 改进建议

## 1. Session 管理重构 (High Priority)

### 当前问题
- 全局单例 session 无法支持多用户/多场景
- sessionContext 切换可能导致状态不一致

### 建议方案
```typescript
class SessionManager {
  private sessions = new Map<string, AgentSession>();
  
  async getOrCreate(sessionId: string, context: SessionContext): Promise<AgentSession> {
    if (!this.sessions.has(sessionId)) {
      this.sessions.set(sessionId, await this.createSession(context));
    }
    return this.sessions.get(sessionId)!;
  }
  
  async cleanup(sessionId: string) {
    this.sessions.delete(sessionId);
  }
}
```

## 2. 递归调用改为循环 (High Priority)

### 当前代码 (agent-loop.ts:299-304)
```typescript
if (runningCount > 0) {
  await new Promise(resolve => setTimeout(resolve, 2000));
  return agentLoop(messages);  // 递归调用 - 风险！
}
```

### 建议改为
```typescript
const MAX_WAIT_ROUNDS = 10;
let waitRounds = 0;

while (bgManager.getRunningCount() > 0 && waitRounds < MAX_WAIT_ROUNDS) {
  console.log(`⏳ 等待后台任务完成 (${waitRounds + 1}/${MAX_WAIT_ROUNDS})...`);
  await new Promise(resolve => setTimeout(resolve, 2000));
  waitRounds++;
}

if (bgManager.getRunningCount() > 0) {
  console.warn(`⚠️ 后台任务仍未完成，超时退出`);
}
```

## 3. 统一错误处理策略 (Medium Priority)

### 建议方案
```typescript
// src/core/agent/error-handler.ts
export enum ErrorSeverity {
  SILENT = 'silent',      // 静默处理，返回默认值
  WARNING = 'warning',    // 打印警告，继续执行
  RECOVERABLE = 'recoverable',  // 打印错误，尝试恢复
  FATAL = 'fatal'         // 打印错误，重新抛出
}

export function handleAgentError(
  error: unknown,
  context: string,
  severity: ErrorSeverity
): void {
  const message = error instanceof Error ? error.message : String(error);
  
  switch (severity) {
    case ErrorSeverity.SILENT:
      // 不输出
      break;
    case ErrorSeverity.WARNING:
      console.warn(`⚠️ ${context}: ${message}`);
      break;
    case ErrorSeverity.RECOVERABLE:
      console.error(`❌ ${context}: ${message}`);
      // 可以在这里添加错误上报
      break;
    case ErrorSeverity.FATAL:
      console.error(`💥 ${context}: ${message}`);
      throw error;
  }
}
```

## 4. Skills 执行机制优化 (Medium Priority)

### 当前问题
- 强制约束可能导致 Agent 卡住
- 简单问题被过度流程化

### 建议方案
```markdown
## Skills 执行策略（智能匹配）

执行优先级：
1. 如果用户明确指定 skill（如 `/portfolio-review`），强制执行
2. 如果正则匹配度高（包含多个关键词），建议执行 skill
3. 如果匹配度低，可直接回答或调用工具

智能判断规则：
- 包含股票代码 + "分析" → deep-analysis (建议)
- "查看持仓" → portfolio (强制)
- "什么是市盈率" → 不匹配 skill (直接回答)
```

## 5. 记忆保存优化 (Medium Priority)

### 建议方案
```typescript
// 在消息处理完成后异步触发
if (totalTokens > 50000) {
  // 不阻塞用户流程
  Promise.resolve().then(async () => {
    console.log("🧠 触发异步记忆保存");
    await agentSession.prompt(
      "Background memory sync: Use memory_write to save key facts."
    );
  });
}
```

## 6. 性能监控增强 (Low Priority)

### 建议添加
```typescript
// src/infrastructure/monitoring/agent-metrics.ts
export class AgentMetrics {
  trackToolCall(toolName: string, duration: number, success: boolean) {
    // 记录工具调用耗时
  }
  
  trackPromptTokens(input: number, output: number) {
    // 记录 token 使用
  }
  
  trackSessionLifetime(sessionId: string, duration: number) {
    // 记录会话时长
  }
  
  getReport(): MetricsReport {
    // 生成性能报告
  }
}
```

## 7. 类型安全改进 (Low Priority)

### 当前问题
- session-adapter.ts 使用大量 `any` 类型
- `normalizeAssistantUsages` 的类型定义不清晰

### 建议方案
```typescript
// 定义更精确的消息类型
interface SessionMessage {
  role: 'user' | 'assistant' | 'system';
  content: Array<TextBlock | ImageBlock>;
  usage?: UsageInfo;
}

interface UsageInfo {
  input: number;
  output: number;
  cacheRead?: number;
  cacheWrite?: number;
  totalTokens: number;
  cost: CostInfo;
}
```

## 8. 测试覆盖补充 (Low Priority)

### 当前状态
- 95 个测试文件 ✓
- 缺少集成测试覆盖

### 建议添加
```typescript
// src/core/agent/__tests__/agent-loop.integration.test.ts
describe('Agent Loop Integration', () => {
  it('should handle background tasks correctly', async () => {
    // 测试后台任务流程
  });
  
  it('should trigger memory save at threshold', async () => {
    // 测试记忆保存触发
  });
  
  it('should route skills based on user input', async () => {
    // 测试技能路由
  });
});
```

## 9. 配置管理改进 (Low Priority)

### 当前问题
- `bootstrapData` 在模块加载时缓存，修改文件后需要重启

### 建议
```typescript
// 只保留 getBootstrapData() 动态加载
// 移除 bootstrapData 导出以避免混淆
export const bootstrapData = _bootstrapLoader.loadAll("full");  // ❌ 删除这行
```

## 10. 文档补充 (Low Priority)

### 建议添加
- `docs/agent-architecture.md` - Agent 架构文档
- `docs/skill-development.md` - Skill 开发指南
- `docs/tool-development.md` - Tool 开发指南
- `docs/troubleshooting.md` - 故障排查指南

---

## 优先级总结

### 立即处理 (High)
1. Session 管理重构 - 避免多用户冲突
2. 递归调用改为循环 - 避免栈溢出

### 近期处理 (Medium)
3. 统一错误处理策略
4. Skills 执行机制优化
5. 记忆保存优化

### 长期改进 (Low)
6. 性能监控增强
7. 类型安全改进
8. 测试覆盖补充
9. 配置管理改进
10. 文档补充

---

## 总体评价

**优点**：
- 架构设计清晰，分层合理
- SDK 隔离良好，易于升级
- 功能丰富，支持并行任务、记忆系统、技能路由
- 测试覆盖较好（95个测试文件）

**需要改进**：
- Session 管理需要重构以支持多用户
- 递归调用存在风险
- 错误处理需要统一
- Skills 强制机制可能过于严格

**推荐度**: ⭐⭐⭐⭐ (4/5)

这是一个设计良好的 Agent 系统，核心逻辑清晰，但在生产环境使用前需要处理上述 High Priority 问题。
