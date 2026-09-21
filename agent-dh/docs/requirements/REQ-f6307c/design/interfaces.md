# REQ-f6307c · 接口设计

## 说明（serves: BUG-1, BUG-2）

本需求为 **bug 修复**，无接口变更。

## 涉及的内部接口（serves: BUG-1, BUG-2）

### CaptureHook 事件监听（serves: BUG-1, BUG-2）

```typescript
ctx.on('session/event', handler)
```

**本次修复**：不改变接口签名。

### systemPrompt section（serves: BUG-2）

```typescript
ctx.systemPrompt.section(name, order, text)
```

**本次修复**：不改变接口，只修复 text 生成逻辑。

## 结论（serves: BUG-1, BUG-2）

无新增/修改 API 端点、无消息格式变更、无协议规范变更。