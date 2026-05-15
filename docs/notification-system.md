# 通知系统使用指南

## 概述

Pi Investment 使用统一的通知系统，支持多种通知渠道。当前已集成飞书作为主要通知渠道。

## 配置

### 环境变量

```bash
# 飞书配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_DEFAULT_CHAT_ID=your_chat_id
```

### 获取飞书配置

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 App ID 和 App Secret
4. 添加机器人到群聊，获取 Chat ID

## Agent 工具使用

### send_notification - 通用通知

```typescript
// 发送文本
await agent.useTool('send_notification', {
  type: 'text',
  content: '市场监控已启动'
});

// 发送卡片
await agent.useTool('send_notification', {
  type: 'card',
  title: '系统通知',
  content: '**重要提醒**\n\n系统将在 10 分钟后维护',
  metadata: { priority: 'high' }
});
```

### send_trade_signal - 交易信号

```typescript
await agent.useTool('send_trade_signal', {
  action: 'buy',
  symbol: '600519',
  name: '贵州茅台',
  price: 1850,
  reason: '技术面突破，成交量放大',
  confidence: 0.85
});
```

### send_market_brief - 市场简报

```typescript
await agent.useTool('send_market_brief', {
  summary: '今日市场整体上涨，科技板块领涨',
  highlights: [
    '上证指数上涨 1.2%',
    '创业板指上涨 2.5%',
    '北向资金净流入 50 亿'
  ],
  risks: ['外部不确定性仍存', '部分板块估值偏高']
});
```

### send_risk_warning - 风险警告

```typescript
await agent.useTool('send_risk_warning', {
  level: 'high',
  message: '市场波动加剧，建议降低仓位'
});
```

## 编程接口

### 直接使用 NotificationService

```typescript
import { getNotificationService } from './tools/notification-tools.js';

const service = getNotificationService();

// 发送文本
await service.send('Hello world');

// 发送卡片
await service.sendCard({
  title: 'Title',
  content: 'Content',
  type: 'card'
});

// 发送图片
await service.sendImage('https://example.com/image.png', 'Caption');
```

## 测试

### 手动测试

```bash
npm run test:notification
```

### 单元测试

```bash
npm test src/services/notification/
npm test src/tools/notification-tools.test.ts
```

## 故障排查

### 消息未发送

1. 检查环境变量配置
2. 检查飞书应用权限（需要 `im:message` 权限）
3. 检查 Chat ID 是否正确
4. 查看日志中的错误信息

### 消息格式异常

1. 检查内容长度（单条消息 < 28000 字符）
2. 检查 Markdown 格式是否正确
3. 使用测试脚本验证

### 频率限制

飞书限制：20 条/分钟

- 系统会自动排队延迟发送
- 避免在循环中频繁发送
- 使用 `sendBatch` 批量发送

## 扩展其他渠道

### 添加新渠道

1. 实现 `NotificationChannel` 接口
2. 在 `initNotificationService` 中注册
3. 通过 `options.channel` 指定渠道

```typescript
class EmailChannel extends NotificationChannel {
  async send(message: NotificationMessage): Promise<void> {
    // 实现邮件发送
  }
  
  async sendImage(imageUrl: string, caption?: string): Promise<void> {
    // 实现图片发送
  }
  
  isAvailable(): boolean {
    return !!process.env.EMAIL_CONFIG;
  }
}

// 注册
service.registerChannel('email', new EmailChannel());

// 使用
await service.send('Message', { channel: 'email' });
```
