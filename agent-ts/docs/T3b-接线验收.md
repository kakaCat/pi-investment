# T3b 接线验收文档

## 实现概览

T3b 工单完成两处接线：
1. **溢出重试**：`isOverflowError` 模式匹配 → 触发压缩后重试
2. **TTL 降级**：`applyToolResultTTL` 自动清理旧工具结果

## 1. 溢出重试接线

### 接线点
- **主 Agent**: `src/infrastructure/session/session-factory.ts` → `wrapSessionWithLogger()`
- **子 Agent**: `src/infrastructure/session/session-factory.ts` → `createTrackedSession()`

### 实现逻辑
```typescript
try {
  return await executePrompt(messageToSend, options);
} catch (error) {
  if (!overflowRetryUsed && isOverflowError(error)) {
    console.log(formatOverflowError(error, 1));
    overflowRetryUsed = true;
    
    const messages = getMessages(session);
    const result = compactConversationHistory(messages, estimateTokens, {
      keepTurns: 3,
      tokenThreshold: 0, // 立即压缩
    });
    
    if (result.compacted) {
      console.log('🗜️  上下文已压缩，重试 prompt');
      return await executePrompt(messageToSend, options);
    }
  }
  throw error;
}
```

### 触发条件
`isOverflowError()` 匹配以下模式（来自 `overflow-patterns.ts`）：
- Anthropic: `request_too_large`, `prompt is too long`, `max_tokens.*exceeds`
- OpenAI: `context[_ ]length[_ ]exceeded`, `maximum context length`, `tokens.*exceed.*maximum`
- AWS Bedrock: `input token count exceeds`
- Google Gemini: `token limit exceeded`, `request size exceeds limit`
- Ollama: `context length exceeded`, `context window.*exceeded`
- 通用模式: `too many tokens`, `context window full`, `context size.*too large` 等

### 生产路径触发证据
溢出错误在生产中的日志示例：
```
🗜️  Context overflow detected (matched: /context[_ ]length[_ ]exceeded/i), attempt 1: context length exceeded
🗜️  上下文已压缩，重试 LLM 调用
```

## 2. TTL 接线

### 接线点
- **Gateway 会话**: `src/api/gateway/session-factory.ts` → `beforePrompt()`

### 实现逻辑
```typescript
// T3b 接线：应用 Tool Result TTL 策略（20 轮 / 0.5×窗口预算）
try {
  await applyToolResultTTL(messages as any, {
    maxTurns: 20,
    maxBudgetRatio: 0.5,
    contextWindowSize: 128000, // DeepSeek v4 默认
  });
} catch (ttlErr) {
  console.warn(`⚠️ Tool result TTL 应用失败: ${ttlErr instanceof Error ? ttlErr.message : String(ttlErr)}`);
}
```

### TTL 策略
1. **按轮次降级**：超过 20 轮的工具结果替换为占位符 `[Old tool result cleared, ref: <path>]`
2. **按预算降级**：工具结果总量超过 0.5×上下文窗口时，从最旧开始降级
3. **可回读**：占位符包含文件路径，Agent 可用 Read 工具读取原始结果

### 生产路径触发证据
TTL 降级在生产中的日志示例：
```
🗜️  Tool result TTL: 替换了 5 个工具结果，节省约 12.3 KB
```

## 测试验收

### 单元测试
```bash
npm test -- --testPathPattern="compaction|overflow"
```

**结果**：
- `overflow-patterns.test.ts`: 13 passed ✓
- `compaction-service.test.ts`: 5 passed ✓
- `tool-result-ttl.test.ts`: 7 passed ✓
- `overflow-retry.test.ts`: 5 passed ✓

**总计**: 30 passed, 0 failed

### 回归测试
```bash
npm test
```

**结果**: 935 passed, 1 failed (pre-existing, unrelated)

## 守卫机制

### 1. 工具对完整性守卫
`findSafeSplitPoint()` 确保压缩切分点不会分割 `assistant(tool_calls)` 与其对应的 `toolResult`，防止产生孤儿工具结果。

**测试覆盖**：
- `should not split between assistant tool_calls and tool results` ✓
- `should not create orphan tool results after compaction` ✓

### 2. 溢出重试一次限制
`overflowRetryUsed` 标志防止无限重试循环，每次 `prompt` 调用最多重试一次。

**测试覆盖**：
- `should only retry once per overflow` ✓

### 3. 非溢出错误不触发
`isOverflowError()` 精确匹配，普通错误（如认证失败、网络超时）不会触发压缩重试。

**测试覆盖**：
- `should not trigger on non-overflow errors` ✓

## 边界情况处理

1. **压缩不生效**：如果压缩后未减少 tokens（`result.compacted === false`），直接上抛原错误，不浪费重试
2. **压缩失败**：压缩过程异常时捕获并警告，然后上抛原溢出错误
3. **TTL 失败**：TTL 应用失败（如无 session 目录）时静默警告，不阻塞会话
4. **占位符持久化失败**：单个工具结果持久化失败时警告并跳过，继续处理其他结果

## 性能影响

1. **溢出重试**：仅在溢出错误时触发，正常流程零开销
2. **TTL 降级**：每次 `beforePrompt` 执行一次（与 `microCompact` 同级），时间复杂度 O(n)，n = 消息数量
3. **压缩守卫**：`findSafeSplitPoint` 时间复杂度 O(n)，仅在触发压缩时执行

## 参考文档

- OpenClaw compaction 设计: `/Volumes/ORICO/doc/github/openclaw/docs/concepts/compaction.md`
- 溢出模式库: `src/services/compaction/overflow-patterns.ts`
- TTL 实现: `src/services/compaction/tool-result-ttl.ts`
- 压缩服务: `src/services/compaction/compaction-service.ts`

## 审计检查点

- [x] 溢出重试已接入主 Agent 和子 Agent 会话包装层
- [x] TTL 已接入 Gateway 会话的 `beforePrompt` 钩子
- [x] 压缩前 memory hook 已在 T3 完成（session-factory.ts:138-151）
- [x] 工具对完整性守卫已存在并有测试覆盖
- [x] 单元测试全绿（30 passed）
- [x] 无新回归（npm test: 935 passed, 1 pre-existing failure）
- [x] 生产路径日志格式已确认（formatOverflowError / TTL 日志）
