# REQ-f6307c 设计文档 · 修复立项弹框跳过问题

> serves: BUG-1, BUG-2

---

## 1. 目标（serves: BUG-1, BUG-2）

**在代码层面要达成**：找到并修复动态注入提示词链路中的断链点，使 Agent 在收到新工作意图消息时能稳定调用 `reqboard_capture` 立项弹框。

**可证伪标准**：
- 在 unbound 窗口发送"修复 XX"消息后，日志显示 5 个关键节点全部正常触发
- LLM 收到的 systemPrompt 中包含动态注入的立项提示词
- Agent 的第一个工具调用是 `reqboard_capture`
- 连续 3 次测试，成功率 100%

---

## 2. 设计（serves: BUG-1, BUG-2）

### 2.1 诊断链路设计（serves: BUG-1）

#### 2.1.1 诊断点布局（serves: BUG-1）

在 5 个关键节点插入诊断日志，形成完整的可观测链路：

```
节点1: index.ts 订阅处
  ↓ 事件流
节点2: CaptureHook.ts handler 入口
  ↓ 窗口判断
节点3: CaptureHook.ts pendingCapture 填充
  ↓ systemPrompt 组装
节点4: gate-wiring.ts section.text 调用
  ↓ 提示词生成
节点5: capture-section.ts 文本返回
```

#### 2.1.2 具体实现位置与内容（serves: BUG-1）

**节点1**：`packages/pages/dsh-pmboard/src/index.ts` 第 233-312 行

```typescript
// 在订阅成功后添加日志
const disposable = ctx.on('session/event', async (event, session) => {
  await hook.handle(event, session);
});

// 添加确认日志
ctx.logger.info('[reqboard-capture] Hook subscribed successfully', {
  disposable: !!disposable,
  handler: 'CaptureHook.handle'
});
```

**节点2**：`packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts` handler 入口（约第 180 行）

```typescript
async handle(event: SessionEvent, session: Session): Promise<void> {
  const { type, detail } = event;
  
  // 添加事件到达日志
  this.ctx.logger.debug('[reqboard-capture] Event received', {
    type,
    hasDetail: !!detail,
    detailKeys: detail ? Object.keys(detail) : []
  });

  if (type === 'user/message') {
    // ... 现有逻辑
  }
}
```

**节点3**：`packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts` pendingCapture 填充后（约第 220 行）

```typescript
if (shouldCapture) {
  pending.set(windowKey, { text, capturedAt: Date.now() });
  
  // 添加填充确认日志
  this.ctx.logger.info('[reqboard-capture] Pending capture registered', {
    windowKey,
    messageLength: text.length,
    pendingSize: pending.size,
    capturedAt: new Date().toISOString()
  });
}
```

**节点4**：`packages/pages/dsh-pmboard/src/gate-wiring.ts` section.text 调用处（约第 100 行）

```typescript
text: async (assembleContext: AssembleContext) => {
  const windowKey = windowKeyFromContext(assembleContext);
  const hasPending = !!hook.pending.get(windowKey);
  
  // 添加组装时检查日志
  hook.ctx.logger.debug('[reqboard-capture] Section.text called', {
    windowKey,
    hasPending,
    pendingSize: hook.pending.size,
    contextKeys: Object.keys(assembleContext)
  });

  return captureSectionText(hook.ledger, hook.pending, assembleContext);
}
```

**节点5**：`packages/pages/dsh-pmboard/src/application/internal/capture-section.ts` 返回前（约第 270 行）

```typescript
export function captureSectionText(
  ledger: View,
  pending: Map<string, PendingCapture>,
  assembleContext: AssembleContext
): string {
  const windowKey = windowKeyFromContext(assembleContext);
  const captured = pending.get(windowKey);

  // 添加最终文本生成日志
  const result = captured ? capturePromptForMessage(captured.text) : '';
  
  if (captured) {
    ctx.logger.info('[reqboard-capture] Prompt generated', {
      windowKey,
      promptLength: result.length,
      messagePreview: captured.text.slice(0, 50)
    });
  } else {
    ctx.logger.debug('[reqboard-capture] No pending capture', {
      windowKey,
      reason: !windowKey ? 'windowKey_undefined' : 'not_in_pending_map'
    });
  }

  return result;
}
```

#### 2.1.3 日志格式规范（serves: BUG-1）

- **前缀**：统一使用 `[reqboard-capture]`
- **级别**：
  - `info`：关键状态变更（订阅成功、pendingCapture 填充、提示词生成）
  - `debug`：中间检查点（事件到达、windowKey 提取）
- **字段**：JSON 格式，包含 windowKey、时间戳、关键状态值

### 2.2 修复策略设计（serves: BUG-2）

#### 2.2.1 修复决策树（serves: BUG-2）

根据 BUG-1 诊断结果，按以下决策树修复：

```
诊断结果
├─ 节点1 未触发
│  └─ 修复：检查 ctx.on 返回值，确认事件订阅成功
├─ 节点2 未触发
│  └─ 修复：检查事件派发链路，确认 'session/event' 正确派发
├─ 节点3 未填充
│  ├─ shouldCaptureWindow 返回 false
│  │  ├─ isWindowBound 误判 → 修复判断逻辑
│  │  └─ hasPendingSuggestion 误判 → 修复判断逻辑
│  └─ windowKey 提取失败 → 修复 windowKeyFromContext
├─ 节点4 未读到 pending
│  ├─ windowKey 不一致 → 统一提取逻辑
│  └─ 时序问题 → 调整 pending 生命周期
└─ 节点5 返回空串
   └─ capturePromptForMessage 逻辑问题 → 修复生成逻辑
```

#### 2.2.2 常见问题修复方案（serves: BUG-2）

**问题1：windowKey 提取不一致**

```typescript
// 统一 windowKey 提取逻辑
function windowKeyFromContext(ctx: AssembleContext): string | undefined {
  // 优先使用 agent.id（会话级）
  if (ctx.agent?.id) return ctx.agent.id;
  
  // 回退到 scope（请求级）
  if (ctx.scope?.sessionId) return ctx.scope.sessionId;
  
  // 无法提取时返回 undefined
  return undefined;
}
```

**问题2：pendingCapture 状态不一致**

```typescript
// 确保 pending 在 turn/end 之前被消费
ctx.on('turn/start', () => {
  // turn 开始时不清除，等待 systemPrompt 组装消费
});

ctx.on('turn/end', () => {
  // turn 结束后才清除
  if (pending.has(windowKey)) {
    pending.delete(windowKey);
  }
});
```

**问题3：shouldCaptureWindow 误判**

```typescript
// 添加防御性检查
function shouldCaptureWindow(ledger: View, windowKey: string): boolean {
  if (!windowKey) return false; // 防御：无效 windowKey
  
  const isUnbound = !isWindowBound(ledger, windowKey);
  const noPending = !hasPendingSuggestion(ledger, windowKey);
  
  // 添加日志辅助诊断
  ctx.logger.debug('[reqboard-capture] shouldCapture check', {
    windowKey,
    isUnbound,
    noPending,
    result: isUnbound && noPending
  });
  
  return isUnbound && noPending;
}
```

### 2.3 接口与数据契约（serves: BUG-1, BUG-2）

#### 2.3.1 诊断日志数据契约（serves: BUG-1）

```typescript
// 日志事件结构
interface CaptureLogEvent {
  node: 1 | 2 | 3 | 4 | 5;
  windowKey?: string;
  timestamp: string;
  status: 'triggered' | 'skipped' | 'error';
  details: Record<string, any>;
}
```

#### 2.3.2 修复后行为契约（serves: BUG-2）

```typescript
// 正常流程保证
interface CaptureFlow {
  // 输入：unbound 窗口 + 新工作意图消息
  input: {
    windowBound: false;
    hasPendingSuggestion: false;
    messageText: string; // 包含 "修复/新增/实现" 等关键词
  };
  
  // 输出：LLM 收到动态提示词
  output: {
    systemPromptContains: string; // capturePromptForMessage 的输出
    agentFirstToolCall: 'reqboard_capture';
  };
  
  // 性能要求
  performance: {
    diagnosisOverhead: '<5ms'; // 日志开销
    promptInjectionTime: '<50ms'; // 提示词注入
  };
}
```

### 2.4 回滚与兼容设计（serves: BUG-1, BUG-2）

#### 2.4.1 回滚路径（serves: BUG-2）

- **诊断日志**：通过日志级别控制，生产环境可设为 `warn` 以上，降低噪音
- **修复代码**：通过 git 回滚到修复前版本，不涉及数据迁移
- **配置开关**（可选）：如需要，可在 `cordis.yml` 中添加 `enableCaptureHook` 开关

#### 2.4.2 兼容性保证（serves: BUG-1, BUG-2）

- **现有流程**：不影响已 bound 窗口的正常推进流程
- **其他 systemPrompt sections**：日志和修复不影响其他 section 的组装
- **工具调用**：`reqboard_capture` 工具签名不变，兼容现有调用

---

## 3. 验收口径（serves: BUG-1, BUG-2）

### 3.1 诊断验收（serves: BUG-1）

**执行命令**：

```bash
# 1. 启动 DSH（确保日志级别为 debug）
cd agent-dh && ./scripts/start.sh

# 2. 在 unbound 窗口发送测试消息
# （通过 Web UI 或 CLI 发送："修复 XX 问题"）

# 3. 查看日志输出
tail -f .dsh-data/logs/agent-os.log | grep "\[reqboard-capture\]"
```

**期望输出**：

```
[INFO] [reqboard-capture] Hook subscribed successfully
[DEBUG] [reqboard-capture] Event received, type: user/message
[DEBUG] [reqboard-capture] shouldCapture check, windowKey: w-xxx, result: true
[INFO] [reqboard-capture] Pending capture registered, windowKey: w-xxx, pendingSize: 1
[DEBUG] [reqboard-capture] Section.text called, windowKey: w-xxx, hasPending: true
[INFO] [reqboard-capture] Prompt generated, windowKey: w-xxx, promptLength: 583
```

**验收标准**：
- ✅ 5 个节点的日志都出现
- ✅ 日志中 windowKey 一致
- ✅ pendingSize > 0 且 hasPending = true
- ✅ promptLength > 0（提示词已生成）
- ❌ 任一节点日志缺失 → 定位到该节点，继续诊断

### 3.2 修复验收（serves: BUG-2）

**执行命令**：

```bash
# 1. 应用修复代码并重启
cd agent-dh
pnpm build  # 如果有必要
./scripts/start.sh

# 2. 连续 3 次测试
for i in {1..3}; do
  echo "=== 测试 $i ==="
  # 在 Web UI 创建新会话窗口
  # 发送："修复登录按钮不响应的问题"
  # 观察 Agent 的第一个工具调用
done

# 3. 检查工具调用日志
grep "tool.*reqboard_capture" .dsh-data/logs/agent-os.log
```

**期望输出**：

```
测试 1: ✅ Agent 第一个工具调用 = reqboard_capture
测试 2: ✅ Agent 第一个工具调用 = reqboard_capture
测试 3: ✅ Agent 第一个工具调用 = reqboard_capture

成功率: 3/3 = 100%
```

**验收标准**：
- ✅ 3 次测试全部成功（100% 成功率）
- ✅ Agent 的第一个工具调用确实是 `reqboard_capture`
- ✅ 弹框内容引用了用户消息原文
- ✅ 用户作答后立项成功，需求进入 brainstorming 状态

### 3.3 回归验证（serves: BUG-1, BUG-2）

**执行命令**：

```bash
# 1. 验证 bound 窗口不受影响
# 在已绑定需求的窗口发送消息，确认不会再次弹框

# 2. 验证性能无明显下降
# 记录修复前后 systemPrompt 组装时间
time curl -X POST http://localhost:13080/api/chat -d '{"message":"test"}'

# 3. 验证其他功能正常
cd agent-dh
pnpm test  # 如果有单元测试
```

**期望输出**：

```
bound 窗口: ✅ 不触发立项弹框，正常对话
性能: ✅ systemPrompt 组装时间 < 100ms（与修复前相当）
回归: ✅ 现有单元测试全部通过
```

---

## 4. 相关文件清单（serves: BUG-1, BUG-2）

- `packages/pages/dsh-pmboard/src/index.ts`（第 233-312 行）
- `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`（第 164-309 行）
- `packages/pages/dsh-pmboard/src/gate-wiring.ts`（第 88-119 行）
- `packages/pages/dsh-pmboard/src/application/internal/capture-section.ts`（第 52-283 行）
- `packages/pages/dsh-pmboard/src/application/internal/window.ts`（第 29-88 行）

---

## 5. 风险与限制（serves: BUG-1, BUG-2）

### 5.1 风险（serves: BUG-1, BUG-2）

- **日志噪音**：5 个节点的 debug 日志可能在生产环境产生噪音
  - **缓解**：生产环境日志级别设为 `info` 或 `warn`
  
- **windowKey 提取失败**：如果 AssembleContext 结构变化，可能导致提取失败
  - **缓解**：添加防御性检查和回退逻辑

### 5.2 限制（serves: BUG-1, BUG-2）

- **不改变工具签名**：`reqboard_capture` 工具保持现有签名，不添加新参数
- **不引入新依赖**：诊断和修复只在现有代码基础上进行
- **不改变业务逻辑**：只修复技术问题，不改变立项流程的业务规则

---

## 6. 测试策略（serves: BUG-1, BUG-2）

### 6.1 单元测试（可选）（serves: BUG-1）

```typescript
// 测试 shouldCaptureWindow 判断逻辑
describe('shouldCaptureWindow', () => {
  it('should return true for unbound window without pending', () => {
    const ledger = mockLedger({ requirements: [], triages: [] });
    expect(shouldCaptureWindow(ledger, 'w-123')).toBe(true);
  });

  it('should return false for bound window', () => {
    const ledger = mockLedger({ 
      requirements: [{ id: 'REQ-1', sourceSessionId: 'w-123', status: 'brainstorming' }] 
    });
    expect(shouldCaptureWindow(ledger, 'w-123')).toBe(false);
  });
});
```

### 6.2 集成测试（serves: BUG-1, BUG-2）

- **手动测试**：按验收口径 3.1 和 3.2 执行
- **自动化测试**（可选）：编写 E2E 测试脚本，模拟用户发送消息并检查工具调用

### 6.3 性能测试（serves: BUG-1, BUG-2）

```bash
# 测量 systemPrompt 组装时间（修复前后对比）
hyperfine --warmup 3 'curl -X POST http://localhost:13080/api/chat -d "{"message":"test"}"'
```

---

**文档版本**: v1.0  
**创建日期**: 2026-09-21  
**作者**: Claude (设计节点)