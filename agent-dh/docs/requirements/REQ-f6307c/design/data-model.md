# REQ-f6307c · 数据模型

## 说明（serves: BUG-1, BUG-2）

本需求为 **bug 修复**，无数据模型变更。

## 涉及的数据结构（serves: BUG-1）

### pendingCapture (内存 Map)（serves: BUG-1）

```typescript
Map<string, { text: string; capturedAt: number }>
```

- **用途**：临时存储待注入的消息
- **生命周期**：user/message 事件触发时填充，turn/end 时清除
- **本次修复**：不改变数据结构

### ledger (View)（serves: BUG-1）

数据库快照，包含：
- `requirements`: 需求表
- `triages`: 确认记录表

**本次修复**：只读，不修改数据结构。

## 结论（serves: BUG-1, BUG-2）

无数据库表变更、无存储格式变更、无数据迁移。