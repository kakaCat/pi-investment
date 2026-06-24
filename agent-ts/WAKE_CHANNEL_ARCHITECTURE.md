# Wake Channel 架构说明

## 概述

Wake Channel 是 quantsys-v2 推送通知的接收渠道，采用与飞书机器人相同的架构模式。

## 架构设计

### 渠道模式

```
quantsys-v2 推送
    ↓ HTTP POST
Wake Channel (start-wake-channel.ts)
    ↓
ChannelSessionManager
    ↓
Agent Session
    ↓
执行工具 (feishu_notify, daily_report 等)
```

### 与飞书渠道对比

| 组件 | 飞书渠道 | Wake 渠道 |
|------|---------|-----------|
| 入口 | 飞书 Webhook | HTTP POST /wake |
| 实现文件 | `api/feishu.ts` | `api/wake-channel.ts` |
| Session 管理 | FeishuSessionManager | ChannelSessionManager |
| 会话隔离 | 按 chat_id | 按 session_id |
| 消息队列 | ✅ | ✅ |
| Agent Session | ✅ | ✅ |

## 核心组件

### 1. ChannelSessionManager (通用 Session 管理器)

**职责**：
- 管理多个独立的 Agent Session
- 维护消息队列，确保顺序处理
- 记录会话日志和上下文
- 支持消息去重和中断

**特性**：
- 支持多会话隔离（按 sessionId）
- 自动队列管理
- 会话生命周期管理
- 可复用于其他渠道（CLI、其他 API 等）

### 2. Wake Channel (接收层)

**职责**：
- 接收 quantsys-v2 的 HTTP 推送
- 解析事件类型和数据
- 构造 Agent 提示词
- 调用 ChannelSessionManager 处理

**支持的事件类型**：
- `market_alert` - 市场异动
- `daily_report` - 每日报告
- `weekly_report` - 每周报告
- `position_alert` - 持仓告警
- `signal_generated` - 交易信号
- `premarket_report` - 盘前报告

## API 接口

### POST /wake

接收 quantsys-v2 推送通知

**请求体**：
```json
{
  "event": "market_alert",
  "task_id": 123,
  "task_name": "市场监控",
  "session_id": "optional-session-id",
  "data": {
    "index": "上证指数",
    "sh_change": 0.02,
    "sz_change": 0.015
  }
}
```

**响应**：
```json
{
  "success": true,
  "event": "market_alert",
  "session_id": "optional-session-id",
  "reply": "Agent 处理结果摘要..."
}
```

### POST /wake/abort

中断某个会话的处理

**请求体**：
```json
{
  "session_id": "optional-session-id"
}
```

### GET /wake/health

健康检查

**响应**：
```json
{
  "status": "ok",
  "channel": "wake",
  "timestamp": "2026-06-24T..."
}
```

## 启动方式

```bash
# 开发模式
npm run wake

# 或者
tsx src/api/start-wake-channel.ts

# 自定义端口
WAKE_CHANNEL_PORT=3001 npm run wake
```

## 配置

环境变量：
- `WAKE_CHANNEL_PORT` - 服务端口（默认 3001）
- `CORS_ORIGIN` - CORS 允许的源（默认 *）

## 测试

```bash
# 测试推送
curl -X POST http://127.0.0.1:3001/wake \
  -H "Content-Type: application/json" \
  -d '{
    "event": "market_alert",
    "data": {
      "index": "上证指数",
      "sh_change": 0.025
    }
  }'

# 健康检查
curl http://127.0.0.1:3001/wake/health
```

## 会话管理

### 会话隔离

每个 `session_id` 对应一个独立的 Agent Session：
- 不同的会话历史
- 独立的消息队列
- 独立的日志文件

### 默认会话

如果不指定 `session_id`，使用默认会话 `"default"`。

### 会话存储

会话数据存储在：`.pi-invest/wake-sessions/<session_id>/`

包含：
- `conversation.log` - 对话日志
- `context.json` - 会话上下文
- SDK 生成的会话文件

## 与 Web Server 的区别

**旧设计（错误）**：
```
Web Server → 直接调用工具
```

**新设计（正确）**：
```
Wake Channel → ChannelSessionManager → Agent Session → 工具
```

**关键差异**：
1. ❌ 旧：Web Server 直接调用工具，绕过 Agent
2. ✅ 新：通过 Agent Session，工具调用由 Agent 决策
3. ✅ 新：支持多会话隔离
4. ✅ 新：维护完整的对话上下文
5. ✅ 新：统一的架构模式（与飞书一致）

## 扩展性

### 添加新渠道

复用 `ChannelSessionManager`，只需实现：
1. 消息接收层（HTTP/WebSocket/MQ 等）
2. 事件 → 提示词转换
3. 调用 `channelManager.processMessage()`

示例：
```typescript
const channelManager = new ChannelSessionManager({
  channelName: "YourChannel",
  sessionsRootDir: "/path/to/sessions",
  createSession: async (sessionId, sessionDir) => {
    // 创建 Agent Session
  },
  beforePrompt: async (session, sessionId, text, sessionDir) => {
    // 预处理
  }
});
```

## 注意事项

1. **不要在渠道层直接调用工具** - 所有工具调用必须通过 Agent Session
2. **会话隔离很重要** - 不同的推送源应使用不同的 session_id
3. **消息队列保证顺序** - 同一会话的消息按顺序处理
4. **Agent 有决策权** - Agent 根据上下文决定是否调用工具，如何调用

## 未来改进

1. [ ] 支持 WebSocket 推送（实时性更好）
2. [ ] 支持消息优先级
3. [ ] 支持批量推送
4. [ ] 会话持久化和恢复
5. [ ] 监控和指标统计
