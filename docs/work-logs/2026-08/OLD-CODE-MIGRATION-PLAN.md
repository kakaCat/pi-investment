# 旧代码迁移计划

**日期**: 2026-08-14  
**目标**: 处理旧的飞书集成代码

---

## 📊 现状分析

### **Agent OS 侧**

#### **旧代码: Python feishu-driver**

```
agent-os/drivers/feishu-driver/
├── main.py                          # Python CLI
├── api/feishu_api.py               # Feishu API client
├── manager/notification_manager.py  # User/channel routing
└── requirements.txt
```

**功能**:
```bash
python main.py send --user yunpeng --title "Test" --message "Hello"
python main.py send --channel general --title "Alert" --message "..."
```

**问题**:
- ❌ 硬编码 user/channel 映射
- ❌ 环境变量配置
- ❌ 需要 Python 环境

---

#### **新代码: Go notification system**

```
agent-os/internal/
├── domain/notification.go
├── repository/notification_repository.go
├── service/notification_service.go
└── cmd/notify.go
```

**功能**:
```bash
agent-os notify send --channel trading --title "Test" --content "Hello"
agent-os notify list
agent-os notify logs
```

**优势**:
- ✅ 数据库驱动
- ✅ 动态配置
- ✅ 完整日志
- ✅ 无需额外环境

---

### **Agent-ts 侧**

#### **旧代码**

```
src/services/feishu-notification.service.ts  # 旧服务
src/infrastructure/tools/notification/feishu-notify-tool.ts  # 旧工具
```

**功能**:
```typescript
await feishuService.sendDailyReport(data);
await feishuService.sendAlert({...});
```

**问题**:
- ⚠️ 直接调用飞书 API
- ⚠️ 硬编码 Webhook URL
- ⚠️ 没有统一的通知抽象

---

#### **新代码**

```
src/infrastructure/tools/notification/notification-tools.ts  # 新工具
```

**功能**:
```typescript
await agent.call('notification_send', {
  channel: 'trading',
  title: 'Test',
  content: 'Hello'
});
```

**优势**:
- ✅ 统一的通知接口
- ✅ 数据库配置
- ✅ 调用 Agent OS

---

## 🎯 处理方案

### **方案 A: 完全替换（推荐）**

**Agent OS**:
1. ✅ 保留新的 Go 实现
2. ✅ 废弃 Python feishu-driver
3. ✅ 添加废弃说明文档

**Agent-ts**:
1. ✅ 保留新的 notification_send 工具
2. ⚠️ 保留旧的 feishu_notify 工具（向后兼容）
3. ✅ 更新文档，推荐使用新工具

**迁移路径**:
```typescript
// 旧代码（保留，但标记为 deprecated）
await agent.call('feishu_notify', {...});  // 向后兼容

// 新代码（推荐）
await agent.call('notification_send', {...});  // 推荐使用
```

---

### **方案 B: 逐步迁移**

**Phase 1**: 新旧并存（当前）
- 新工具可用
- 旧工具继续工作

**Phase 2**: 废弃旧代码（1-2 周后）
- 标记 feishu_notify 为 deprecated
- 更新所有调用为 notification_send

**Phase 3**: 删除旧代码（1 个月后）
- 确认无使用
- 删除 Python feishu-driver
- 删除 feishu_notify 工具

---

## 📋 具体行动

### **立即执行（今天）**

#### **1. Agent OS: 废弃 Python driver**

```bash
# 添加废弃说明
mv agent-os/drivers/feishu-driver/README.md \
   agent-os/drivers/feishu-driver/README.DEPRECATED.md
```

创建新的 README：
```markdown
# Feishu Driver (DEPRECATED)

⚠️ **This Python driver is deprecated.**

Please use the new Go-based notification system:

\`\`\`bash
# New way
agent-os notify send --channel trading --title "Test" --content "Hello"

# Old way (deprecated)
python main.py send --user yunpeng --title "Test" --message "Hello"
\`\`\`

See: `../../internal/cmd/notify.go`
```

---

#### **2. Agent-ts: 更新 feishu_notify 工具**

**标记为 deprecated**:
```typescript
// feishu-notify-tool.ts
export const feishuNotifyTool: ToolDefinition = {
  name: "feishu_notify",
  label: "飞书通知 (Deprecated)",
  description: `⚠️ **DEPRECATED**: Please use 'notification_send' instead.

发送飞书通知给用户。支持文本、卡片、报告、告警等消息类型。

**Recommended**: Use 'notification_send' tool for new code.`,
  // ... 其余代码保持不变
};
```

---

#### **3. 更新文档**

**创建迁移指南**:
```markdown
# 飞书通知迁移指南

## 旧方式 → 新方式

### Agent OS

**旧方式** (Python):
\`\`\`bash
python drivers/feishu-driver/main.py send \
  --user yunpeng \
  --title "Test" \
  --message "Hello"
\`\`\`

**新方式** (Go):
\`\`\`bash
agent-os notify send \
  --channel trading \
  --title "Test" \
  --content "Hello"
\`\`\`

### Agent-ts

**旧方式**:
\`\`\`typescript
await agent.call('feishu_notify', {
  messageType: 'card',
  title: 'Test',
  content: 'Hello'
});
\`\`\`

**新方式**:
\`\`\`typescript
await agent.call('notification_send', {
  channel: 'trading',
  title: 'Test',
  content: 'Hello'
});
\`\`\`

## 优势

- ✅ 统一的通知接口
- ✅ 数据库驱动配置
- ✅ 完整的日志追溯
- ✅ 易于扩展（Slack、Email）
\`\`\`
```

---

### **下周执行**

#### **4. 更新所有调用**

查找所有使用旧工具的地方：
```bash
grep -r "feishu_notify" agent-ts/src/
grep -r "feishu-driver" agent-os/
```

逐个更新为新工具。

---

#### **5. 删除 feishu_notify 从 catalog**

```typescript
// catalog.ts
const CORE_TOOL_NAMES = new Set([
  // ...
  "market_alert",
  // "feishu_notify",  // 删除
  "notification_send",  // 保留
  // ...
]);
```

---

### **下月执行**

#### **6. 完全删除旧代码**

```bash
# 删除 Python driver
rm -rf agent-os/drivers/feishu-driver/

# 删除旧工具
rm agent-ts/src/infrastructure/tools/notification/feishu-notify-tool.ts

# 删除旧服务（如果不再使用）
rm agent-ts/src/services/feishu-notification.service.ts
```

---

## ✅ 当前建议（最小改动）

### **今天做什么**

1. **添加废弃标记**
   - ✅ 在 Python driver 添加 DEPRECATED 说明
   - ✅ 在 feishu_notify 工具添加 deprecated 注释

2. **文档更新**
   - ✅ 创建迁移指南
   - ✅ 更新主 README

3. **保持向后兼容**
   - ✅ 旧代码继续工作
   - ✅ 新代码可以使用

### **暂不做什么**

- ❌ 不删除任何代码（避免破坏现有功能）
- ❌ 不强制迁移（给时间适应）
- ❌ 不修改现有调用（逐步迁移）

---

## 🎯 推荐方案

**采用方案 A（完全替换 + 向后兼容）**:

1. ✅ 新系统已完成并可用
2. ✅ 旧代码标记为 deprecated
3. ✅ 保持向后兼容
4. ✅ 文档指导迁移
5. ⏰ 1-2 个月后删除旧代码

**理由**:
- 不破坏现有功能
- 给足够时间迁移
- 新旧可以并存
- 逐步过渡

---

**你希望我立即执行哪些步骤？**
1. 添加 DEPRECATED 标记？
2. 创建迁移指南？
3. 还是先保持现状？
