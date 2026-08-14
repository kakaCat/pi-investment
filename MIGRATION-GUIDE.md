# 飞书通知迁移指南

**日期**: 2026-08-14  
**状态**: 新系统已上线，旧系统标记为 deprecated

---

## 📋 迁移概览

### **旧系统**
- Python feishu-driver (Agent OS)
- feishu_notify 工具 (Agent-ts)

### **新系统**
- Go notification system (Agent OS)
- notification_send 工具 (Agent-ts)

---

## 🔄 迁移对照

### **Agent OS CLI**

#### **旧方式** (Python)

```bash
python drivers/feishu-driver/main.py send \
  --user yunpeng \
  --title "Test" \
  --message "Hello World"

python drivers/feishu-driver/main.py send \
  --channel general \
  --title "Alert" \
  --message "System status"
```

#### **新方式** (Go)

```bash
agent-os notify send \
  --channel trading \
  --title "Test" \
  --content "Hello World"

agent-os notify send \
  --channel alerts \
  --title "Alert" \
  --content "System status"
```

**差异**:
- ✅ `--message` → `--content`
- ✅ `--user yunpeng` → `--channel trading`
- ✅ 内置到 agent-os 二进制

---

### **Agent-ts 工具**

#### **旧方式** (feishu_notify)

```typescript
// 发送卡片
await agent.call('feishu_notify', {
  messageType: 'card',
  title: '📊 每日报告',
  content: '**总资产**: ¥1,050,000\n**持仓**: 11只'
});

// 发送告警
await agent.call('feishu_notify', {
  messageType: 'alert',
  title: '⚠️ 风险告警',
  content: '大盘下跌 2%',
  urgency: 'high'
});
```

#### **新方式** (notification_send)

```typescript
// 发送卡片
await agent.call('notification_send', {
  channel: 'trading',
  title: '📊 每日报告',
  content: '**总资产**: ¥1,050,000\n**持仓**: 11只',
  color: 'blue'
});

// 发送告警
await agent.call('notification_send', {
  channel: 'alerts',
  title: '⚠️ 风险告警',
  content: '大盘下跌 2%',
  color: 'red'
});
```

**差异**:
- ✅ `messageType` → `channel` (更清晰的渠道语义)
- ✅ `urgency` → `color` (视觉反馈)
- ✅ 统一的 Markdown 格式

---

## 🎯 渠道映射

### **旧的 user/channel 映射**

```python
# Python driver
user_webhooks = {
    'yunpeng': FEISHU_WEBHOOK_URL  # 个人通知
}

channel_webhooks = {
    'general': FEISHU_WEBHOOK_TRADING,  # 通用通知
    'trading': FEISHU_WEBHOOK_TRADING,  # 交易通知
    'alerts': FEISHU_WEBHOOK_ALERTS     # 告警通知
}
```

### **新的 channels**

```sql
SELECT code, name, description FROM notification_channels;

 code    | name   | description
---------|--------|----------------------------------
 trading | 交易群 | 接收交易信号和执行确认
 alerts  | 告警群 | 接收风险预警和系统异常
 reports | 报告群 | 接收每日报告和周报
```

**迁移规则**:
- `--user yunpeng` → `--channel trading`
- `--channel general` → `--channel trading`
- `--channel alerts` → `--channel alerts`

---

## 📝 实际代码迁移示例

### **示例 1: 每日报告**

**旧代码**:
```typescript
// src/services/feishu-notification.service.ts
const feishuService = getFeishuService();
await feishuService.sendDailyReport({
  date: '2026-08-14',
  total_assets: 1050000,
  cash: 200000,
  holdings_count: 11
});
```

**新代码**:
```typescript
// Agent 生成报告
const report = await agent.generate(`
生成每日报告...
数据: ${JSON.stringify(data)}
`);

// 发送通知
await agent.call('notification_send', {
  channel: 'trading',
  title: '📊 每日报告 - 2026-08-14',
  content: report,
  color: 'blue'
});
```

---

### **示例 2: 交易信号**

**旧代码**:
```typescript
await agent.call('feishu_notify', {
  messageType: 'alert',
  title: '🚨 交易信号',
  content: `**股票**: 600519.SH\n**信号**: 买入\n**价格**: ¥1,205`,
  urgency: 'high'
});
```

**新代码**:
```typescript
await agent.call('notification_send', {
  channel: 'alerts',
  title: '🚨 交易信号',
  content: `**股票**: 600519.SH\n**信号**: 买入\n**价格**: ¥1,205`,
  color: 'red'
});
```

---

### **示例 3: 盘前准备**

**旧代码**:
```typescript
const feishuService = getFeishuService();
await feishuService.sendMessage(
  'yunpeng',
  '🌅 盘前准备',
  '今日机会: 600519.SH, 000858.SZ'
);
```

**新代码**:
```typescript
await agent.call('notification_send', {
  channel: 'trading',
  title: '🌅 盘前准备',
  content: '今日机会: 600519.SH, 000858.SZ',
  color: 'blue'
});
```

---

## ✅ 新系统优势

### **1. 数据库驱动**
```bash
# 查看所有渠道
agent-os notify list

# 添加新渠道（SQL）
INSERT INTO notification_channels (code, name, config) VALUES
('vip', 'VIP 客户群', '{"webhook": "https://..."}');
```

无需改代码！

---

### **2. 完整日志**
```bash
# 查看发送历史
agent-os notify logs --limit 10

# 统计成功率
SELECT
  channel_id,
  COUNT(*) as total,
  SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as success
FROM notification_logs
GROUP BY channel_id;
```

---

### **3. 统一接口**
```typescript
// 同一个工具，不同渠道
await agent.call('notification_send', { channel: 'trading', ... });
await agent.call('notification_send', { channel: 'alerts', ... });
await agent.call('notification_send', { channel: 'reports', ... });
```

---

### **4. 易于扩展**
```sql
-- 添加 Slack
INSERT INTO notification_providers (code, name) VALUES ('slack', 'Slack');

-- 添加邮件
INSERT INTO notification_providers (code, name) VALUES ('email', '邮件');
```

只需实现 Provider 接口！

---

## 📅 迁移时间表

### **现在 (2026-08-14)**
- ✅ 新系统已上线
- ✅ 旧系统标记为 deprecated
- ✅ 两套系统并存

### **两周后 (2026-08-28)**
- 🔄 开始迁移现有调用
- 🔄 更新所有 Agent 脚本

### **一个月后 (2026-09-14)**
- ❌ 删除 Python feishu-driver
- ❌ 删除 feishu_notify 工具
- ❌ 删除旧服务代码

---

## 🚀 立即行动

### **优先迁移**
1. 定时任务（每日报告、盘前准备）
2. 告警通知（风险预警、系统异常）
3. 手动调用（测试脚本）

### **如何迁移**
1. 找到所有 `feishu_notify` 调用
   ```bash
   grep -r "feishu_notify" agent-ts/src/
   ```

2. 逐个替换为 `notification_send`

3. 测试验证

4. 提交代码

---

## 📞 遇到问题？

- 查看文档: `/NOTIFICATION-SYSTEM-FINAL-REPORT.md`
- 查看代码: `/agent-os/internal/cmd/notify.go`
- 查看工具: `/agent-ts/src/infrastructure/tools/notification/notification-tools.ts`

---

**开始迁移吧！新系统更强大、更灵活、更易维护！** 🎉
