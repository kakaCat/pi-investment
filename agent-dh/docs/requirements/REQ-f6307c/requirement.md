# REQ-f6307c · 修复 Agent 多次跳过立项弹框的问题

## 1. 问题概述

### 1.1 现象描述
Agent 在收到用户包含工作意图的消息时，**经常跳过立项弹框**，不调用 `reqboard_capture` 工具。

### 1.2 预期行为
- 用户发送包含新工作意图的消息（如"修复 XX"、"新增 YY"）
- Hook 检测到 unbound 窗口 → 注入动态提示词（引用用户消息原文）
- Agent 看到提示词中的**强制要求**："第一个工具调用必须是 reqboard_capture"
- Agent 调用弹框，用户作答，立项完成

### 1.3 实际行为
- Hook 机制已实现，但可能未生效
- Agent 只看到静态的工具描述（通用、易被忽略）
- Agent 选择"先回答问题"，跳过立项

---

## 2. 根本原因分析

### 2.1 设计机制（已实现但未生效）

**动态注入提示词机制**：

```
用户消息到达
  ↓
Hook 监听 (session/event: user/message)
  ↓
判断: shouldCaptureWindow(windowKey)
  ├─ 条件1: 窗口未绑定需求 (unbound)
  └─ 条件2: 无遗留建议卡
  ↓ 两个条件都满足
登记 pendingCapture.set(windowKey, {text, capturedAt})
  ↓
Agent 开始推理 → systemPrompt 组装
  ↓
读取 pendingCapture.get(windowKey)
  ↓
注入 capturePromptForMessage(text) 到 systemPrompt
  ↓
LLM 看到动态提示词（引用消息原文 + 强制要求）
  ↓
turn/end: 清除 pendingCapture
```

### 2.2 潜在断链位置

| 节点 | 检查点 | 可能的问题 |
|------|--------|-----------|
| **节点1** | Hook 是否订阅成功 | `on('session/event')` 返回值检查 |
| **节点2** | Hook 是否被触发 | 事件派发是否到达 handler |
| **节点3** | pendingCapture 是否填充 | `shouldCaptureWindow` 判断可能失败 |
| **节点4** | systemPrompt 组装时是否读到 | `windowKeyFromContext` 可能提取失败 |
| **节点5** | 最终文本是否返回 | `captureSectionText` 可能提前返回空串 |

### 2.3 判断逻辑详解

**shouldCaptureWindow 的判断**（确定性窗口状态判断）：

```typescript
// 必须同时满足两个条件
return !isWindowBound(ledger, windowKey) && !hasPendingSuggestion(ledger, windowKey)
```

**条件1：!isWindowBound**（窗口未绑定需求）
- 检查 `requirements` 表：是否存在 `sourceSessionId === windowKey` 且状态为 open 的需求
- 检查 `triages` 表：该窗口的确认记录是否指向仍在 open 的需求
- true（已绑定）→ 不注入（窗口正在推进需求）
- false（未绑定）→ 通过条件1

**条件2：!hasPendingSuggestion**（无遗留建议卡）
- 检查 `triages` 表：是否存在 `sessionId === windowKey && status === 'pending'`
- true（有遗留）→ 不注入（先处理遗留）
- false（无遗留）→ 通过条件2

**关键点**：Hook 不做语义判断（消息是否真的值得立项），只做窗口状态判断。语义判断留给 LLM 根据提示词中的判据自己裁定。

---

## 3. 解决方案

### 3.1 方案选择

**推荐：保持动态注入方案并诊断修复**

**理由**：
1. **Token 效率高**：在典型场景（立项后长期 bound）下，动态方案更省
   - unbound 首次：600 tokens（一次性）
   - bound 后续：0 tokens（不注入）
   - 静态方案：每次 LLM 调用都发送 200 tokens
2. **效果更好**：引用消息原文 + 强制要求 = 更难被忽略
3. **代码已完整**：机制已实现，只需诊断为什么没生效

### 3.2 Token 消耗对比

| 场景 | 动态注入 | 静态描述 | 优势方 |
|------|---------|---------|--------|
| unbound 窗口首次 | 600 tokens | 200 tokens | 静态 |
| bound 窗口 10 轮对话 | 0 tokens | 2000 tokens | **动态（省 2000）** |
| 典型工作流（立项后长期推进） | ~600 tokens | ~10000+ tokens | **动态（省 90%+）** |
| 引用用户消息原文 | ✅ | ❌ | 动态 |
| 强制要求首次调用 | ✅ | ❌ | 动态 |

---


### 3.3 实现方式对比：LLM判断 vs Hook判断

**关键问题**：Hook 注入提示词后，LLM 如何知道"这条消息需要立项"？

#### 方式1：LLM 自己判断（当前实现）

**流程**：
```
Hook 检查窗口状态（unbound）
  ↓
注入通用提示词："你必须先做一次显式裁定"
  ↓
LLM 看消息内容 → 自己判断是否值得立项
  ├─ 值得 → 调 reqboard_capture
  └─ 不值得 → 写"本条不立项：<理由>"
```

**优点**：Hook 简单、灵活、避免误判
**缺点**：LLM 可能跳过裁定

#### 方式2：Hook 里加判断（用户建议）

**流程**：
```
Hook 分析消息内容
  ├─ 包含"修复/新增"+ 具体对象
  │   → 注入强提示："这条消息需要立项，必须调 reqboard_capture"
  └─ 纯提问/闲聊
      → 不注入或注入弱提示
```

**优点**：LLM 收到明确指令、更难跳过、闲聊零消耗
**缺点**：Hook 需要 NLP 判断、误判风险高、不易调整

#### 推荐：混合方案（方式2改进版）

Hook 用**简单规则**快速分类，保留 LLM 裁定能力：

```typescript
function classifyMessageIntent(text: string): "strong" | "medium" | "weak" {
  // 高置信度：明确动词 + 要/需要/帮我
  const strongPatterns = [
    /(?:修复|改|新增|实现).*(?:bug|功能|模块)/
    /(?:帮我|需要|要求).*(?:修复|改|新增)/
  ]
  
  // 中置信度：有工作动词但不确定
  const mediumPatterns = [
    /(?:修复|改|新增|实现|重构|优化)/
    /(?:有问题|不work|能不能)/
  ]
  
  if (strongPatterns.some(p => p.test(text))) return "strong"
  if (mediumPatterns.some(p => p.test(text))) return "medium"
  return "weak"
}

// 根据置信度注入不同强度提示词
const intent = classifyMessageIntent(text)
if (intent === "strong") {
  // 强提示：这条消息需要立项，第一个工具调用必须是 reqboard_capture
} else if (intent === "medium") {
  // 中等提示：可能包含工作意图，请先裁定是否立项（仍需 LLM 判断）
} else {
  // 不注入或弱提示（零消耗）
}
```

**优势**：
- 高置信度直接指令（"必须立项"），更难跳过
- 中置信度仍需裁定，避免误判
- 低置信度不注入，节省 token
- 简单规则（正则匹配），不需要复杂 NLP

## 4. 功能需求

### BUG-1: 诊断 Hook 注入链路断链问题

**目标**：找到链路中哪个环节没有生效

**实现方式**：在 5 个关键节点添加日志

| 节点 | 位置 | 日志内容 |
|------|------|---------|
| 节点1 | `index.ts` 订阅处 | Hook 订阅是否成功（返回值检查） |
| 节点2 | `CaptureHook.ts` handler 入口 | `user/message` 事件是否到达 |
| 节点3 | `CaptureHook.ts` 填充后 | `pendingCapture.size`、当前 windowKey |
| 节点4 | `gate-wiring.ts` section.text | assembleContext 的 windowKey、pending 是否存在 |
| 节点5 | `capture-section.ts` 返回前 | 最终文本长度、返回空串的原因 |

**验收标准**：
- 测试用例：在 unbound 窗口发送"修复 XX"消息
- 日志清晰显示每个环节的状态（触发/未触发、值/undefined）
- 找到断链位置（哪个环节返回 false/empty/undefined）

---

### BUG-2: 修复断链问题使注入生效

**目标**：根据 BUG-1 的诊断结果修复问题

**潜在修复方向**（按诊断结果决定）：

1. **windowKey 提取失败**
   - 问题：`windowKeyFromContext(assembleContext)` 返回 undefined
   - 修复：检查 assembleContext 的结构，确保正确提取 agent.id 或 scope

2. **snapshot() 状态不一致**
   - 问题：hook 判定时 unbound，systemPrompt 组装时已 bound
   - 修复：确保 pendingCapture 的生命周期跨越状态变化

3. **判断逻辑问题**
   - 问题：`shouldCaptureWindow` 误判
   - 修复：调整判断条件或添加容错

**验收标准**：
- 修复后重新测试相同用例
- 日志显示所有 5 个节点都正常
- LLM 确实看到了动态注入的提示词
- Agent 在收到新工作意图时，第一个工具调用是 `reqboard_capture`
- 连续测试 3 次，100% 成功率

---



## 5. 实现细节

### 5.1 判断逻辑的关键代码

**shouldCaptureWindow**（`src/application/internal/window.ts` 第 86-88 行）：
```typescript
export function shouldCaptureWindow(ledger: View, windowKey: string): boolean {
  return !isWindowBound(ledger, windowKey) && !hasPendingSuggestion(ledger, windowKey)
}
```

**isWindowBound**（第 29-42 行）：
```typescript
export function isWindowBound(ledger: View, windowKey: string): boolean {
  // 规则1：直接立项
  if (ledger.requirements.some(r => r.sourceSessionId === windowKey && isOpenReq(r))) 
    return true
  
  // 规则2：triage 绑定
  for (const tri of ledger.triages) {
    if (tri.sessionId !== windowKey) continue
    const anchorIds = [tri.resultRequirementId, ...(tri.resultRequirementIds || [])]
    for (const reqId of anchorIds) {
      const req = ledger.requirements.find(r => r.id === reqId)
      if (req && isOpenReq(req)) return true
    }
  }
  return false
}
```

### 5.2 注入内容详解

**动态提示词**（`capturePromptForMessage`）包含：
- 用户消息原文节选（最多 300 字）
- 明确判据："修复/改/新增/实现..."+ 具体对象 = 立项
- 强制要求："本回合的第一个工具调用必须是 reqboard_capture"
- 不立项时的要求："在回复第一行写明「本条不立项：<理由>」"

**总 token 数**：约 500-600 tokens（固定文本 350-400 + 消息节选 150-200）

### 5.3 清除时机

`turn/end` 事件触发时：
```typescript
if (type === 'turn/end') {
  const consumed = pending.get(windowKey)
  if (consumed !== undefined) {
    pending.delete(windowKey)
    debug('reqboard-capture: turn/end consumes pending capture')
  }
}
```

---

## 6. 非功能需求

### 6.1 性能要求
- 日志添加不应显著影响性能（< 1ms per log）
- pendingCapture 是内存 Map，不涉及 I/O

### 6.2 可维护性
- 日志格式统一，便于后续排查
- 诊断代码可在修复完成后保留（便于未来排障）

### 6.3 兼容性
- 修复不应影响已有的 bound 窗口推进流程
- 不应影响其他 systemPrompt sections

---

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| BUG-1 | 🔴 **未被接收** | — |
| BUG-2 | 🔴 **未被接收** | — |

> 🔴 **未被接收（2 条）**：BUG-1、BUG-2

<!-- reqboard:marks:end -->

## 7. 验收标准（总体）

### 7.1 诊断阶段（BUG-1）
- [ ] 5 个关键节点的日志已添加
- [ ] 测试用例：unbound 窗口发送"修复 XX"
- [ ] 日志输出完整且易读
- [ ] 找到断链位置

### 7.2 修复阶段（BUG-2）
- [ ] 根据诊断结果实施修复
- [ ] 相同测试用例通过（LLM 看到提示词）
- [ ] Agent 调用 reqboard_capture
- [ ] 连续 3 次测试 100% 成功

### 7.3 回归测试
- [ ] bound 窗口推进流程正常
- [ ] 其他 systemPrompt sections 不受影响
- [ ] 性能无明显下降

---

## 8. 边界

- `packages/pages/dsh-pmboard/src/index.ts`（第 233-312 行）：Hook 订阅与装配
- `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`（第 164-309 行）：事件处理器
- `packages/pages/dsh-pmboard/src/gate-wiring.ts`（第 88-119 行）：systemPrompt section 注册
- `packages/pages/dsh-pmboard/src/application/internal/capture-section.ts`（第 52-283 行）：提示词生成
- `packages/pages/dsh-pmboard/src/application/internal/window.ts`

---

### 8.1 设计文档说明

本需求虽标记为 feature，但**本质是 bug 修复**（Hook 注入链路断链），以下 feature 类型必填的设计文档不适用：

| 设计文档 | 不适用原因 |
|---------|-----------|
| **design/architecture.md** | 无架构变更，仅在现有 Hook 链路上添加日志和修复断链。架构设计已在 diagnostic-and-fix.md §2.1 诊断链路设计中说明 |
| **design/data-model.md** | 无数据模型变更，不涉及数据库表结构、存储格式、数据迁移 |
| **design/interfaces.md** | 无接口变更，不涉及新增/修改 API 端点、消息格式、协议规范 |
| **design/test-cases.md** | 测试用例已完整覆盖在 decomposition.md 各任务的 acceptance 字段中（T1-T4 均有明确的可证伪验收标准） |

**实际交付的设计文档**：
- **design/diagnostic-and-fix.md**（451 行）：
  - §2.1 诊断链路设计（5 个节点布局、日志格式、数据契约）
  - §2.2 修复方案（决策树、常见问题修复）
  - §2.3 数据契约（诊断日志、修复后行为）
  - §2.4 安全与兼容（回滚路径、兼容性保证）
  - §6 测试策略（单元/集成/性能测试）

该文档已完整覆盖 bug 修复所需的全部设计信息，无需额外的架构/数据模型/接口设计文档。（第 29-88 行）：窗口状态判断

---

## 9. 附录：设计优势

### 9.1 为什么采用动态注入而非静态描述？

**动态注入的优势**：
1. **针对性强**：引用用户消息原文，LLM 无法忽视
2. **措辞可强化**：可以用"必须"、"第一个"等强制措辞
3. **零噪音**：bound 窗口不注入，不浪费 token
4. **自动清除**：turn/end 后清除，不会跨回合重复

**静态描述的问题**：
1. 通用性太强，易被忽略
2. 无法引用消息原文
3. 每次 LLM 调用都发送（token 累积）
4. 无法强制要求调用顺序

### 9.2 为什么不在 Hook 层做语义判断？

**确定性判断（窗口状态）+ 语义判断（LLM）的分离设计**：
1. **确定性触发**：只要窗口 unbound，用户消息一定触发评估
2. **语义灵活**：判据在提示词里，可以随时调整（措辞硬化）
3. **用户决策**：最终立项由用户在弹框里确认（人工 gate）
4. **避免误判**：不在 Hook 层做 NLP 判断（容易误判或漏判）

**对比旧方案**（已废弃）：
- ❌ SessionSyncService：Hook 自动分类（LLM）并自动立项 → 228 条垃圾评论
- ✅ 当前设计：Hook 触发 + LLM 裁定 + 用户确认 → 三道关卡

---

## 产品定义

**产品**：reqboard 立项弹框（reqboard_capture 工具）

**当前问题**：Agent 在收到包含工作意图的消息时，经常跳过立项弹框

**预期行为**：
1. 用户在 unbound 窗口发送新工作意图消息
2. Hook 检测并注入动态提示词（引用消息原文 + 强制要求）
3. LLM 看到提示词，第一个工具调用是 reqboard_capture
4. 弹框显示，用户作答，立项完成

**修复目标**：通过诊断定位链路断链位置并修复，使注入机制 100% 生效

---

## 用户与角色

| 角色 | 描述 | 交互方式 |
|------|------|---------|
| **Agent（投资脑窗口）** | 接收用户消息，执行工具调用 | 被动接收动态提示词，主动调用 reqboard_capture |
| **用户** | 在 GUI 中发送消息 | 输入包含工作意图的消息，在弹框中作答 |
| **Hook 机制** | 监听 user/message 事件 | 自动判断窗口状态，注入/不注入提示词 |
| **开发者/排障者** | 查看日志定位问题 | 读取诊断日志，分析断链位置 |

---

## 功能点

⚠️ **注意**：本需求虽标记为 feature，实为 bug 修复，使用 BUG-x 编号：

### BUG-1：诊断 Hook 注入链路断链问题
- 在 5 个关键节点添加诊断日志
- 执行测试收集日志
- 定位断链位置

### BUG-2：修复断链问题使注入生效
- 根据诊断结果选择修复方向
- 实施最小化改动
- 验证修复后 100% 成功率

详见需求文档 §4（第 186-233 行）