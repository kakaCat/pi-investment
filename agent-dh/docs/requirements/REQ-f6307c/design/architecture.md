# REQ-f6307c · 架构设计

## 说明（serves: BUG-1, BUG-2）

本需求为 **bug 修复**（Hook 注入链路断链），无架构变更。

架构设计已在 `diagnostic-and-fix.md` §2.1 诊断链路设计中说明：
- 5 个关键节点的链路结构
- Hook 订阅机制
- systemPrompt 组装流程

## 现有架构（serves: BUG-1, BUG-2）

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

## 本次修复（serves: BUG-1, BUG-2）

**不改变架构**，仅在现有链路上：
1. 添加诊断日志（5 个节点）
2. 修复断链问题（保持架构不变）

详见 `diagnostic-and-fix.md`。