# 飞书通知系统设计

**日期:** 2026-05-15  
**状态:** 已批准  
**目标:** 将飞书打造为统一的 agent 通信和通知模块

---

## 概述

本设计将飞书建立为 Pi Investment agent 的主要输入输出接口和通知系统。系统提供解耦、可扩展的架构，允许 agent 发送丰富的通知（交易信号、市场简报、风险警告），同时保持未来添加其他通知渠道的灵活性。

---

## 架构设计

### 核心组件

```
NotificationService (统一接口)
    ↓
NotificationChannel (抽象基类)
    ↓
FeishuChannel (飞书实现)
```

### 组件职责

**NotificationService**
- 提供统一的通知 API (`send`, `sendCard`, `sendImage`)
- 管理多个 channel 实例
- 处理通知重试和降级逻辑
- 将消息路由到合适的渠道

**NotificationChannel (抽象)**
- 定义所有 channel 必须实现的接口
- 标准化消息格式转换
- 提供可用性检查

**FeishuChannel**
- 封装 Lark SDK 调用
- 实现卡片、富文本、图片等格式
- 处理飞书特有的限制（字符长度、频率限制）
- 管理消息队列和批量发送

### 数据流

```
Agent Tool → NotificationService.send() 
    → FeishuChannel.send() 
    → Lark SDK 
    → 飞书服务器
```

---

## 接口设计

### NotificationService API

```typescript
interface NotificationMessage {
  title?: string;
  content: string;
  type: 'text' | 'markdown' | 'card';
  metadata?: Record<string, any>;
}

interface NotificationOptions {
  channel?: string;  // default 'feishu'
  chatId?: string;   // override default chatId
  priority?: 'low' | 'normal' | 'high';
}

class NotificationService {
  // 基础文本消息
  async send(message: string, options?: NotificationOptions): Promise<void>
  
  // 富文本卡片（交易信号、市场简报等）
  async sendCard(message: NotificationMessage, options?: NotificationOptions): Promise<void>
  
  // 图片/图表
  async sendImage(imageUrl: string, caption?: string, options?: NotificationOptions): Promise<void>
  
  // 批量发送（避免频率限制）
  async sendBatch(messages: NotificationMessage[], options?: NotificationOptions): Promise<void>
}
```

### NotificationChannel 抽象类

```typescript
abstract class NotificationChannel {
  abstract send(message: NotificationMessage): Promise<void>
  abstract sendImage(imageUrl: string, caption?: string): Promise<void>
  abstract isAvailable(): boolean  // 检查配置是否完整
}
```

### Agent 工具调用示例

```typescript
// 交易信号
await notificationService.sendCard({
  title: '🟢 买入信号',
  content: '**贵州茅台** (600519)\n当前价: ¥1850\n...',
  type: 'card',
  metadata: { signal_type: 'buy', symbol: '600519' }
})

// 简单文本
await notificationService.send('市场监控已启动')
```

---

## FeishuChannel 实现

### 飞书特有功能

**1. 卡片消息格式**
- 支持 Markdown 渲染
- 蓝色标题头（Pi Investment 品牌）
- 自动处理 28000 字符限制（分片发送）

**2. 消息类型映射**
```typescript
NotificationMessage.type → Feishu msg_type
  'text' → 'text'
  'markdown' → 'text' (plain text)
  'card' → 'interactive' (rich card)
```

**3. 错误处理**
- 飞书 API 失败 → 降级为纯文本
- 频率限制 → 自动排队延迟发送
- 配置缺失 → 静默失败 + 日志警告

### 配置管理

```typescript
// 从环境变量读取
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_DEFAULT_CHAT_ID  // 默认发送目标

// FeishuChannel 初始化
const feishuChannel = new FeishuChannel({
  appId: process.env.FEISHU_APP_ID,
  appSecret: process.env.FEISHU_APP_SECRET,
  defaultChatId: process.env.FEISHU_DEFAULT_CHAT_ID
})
```

### 与现有代码的关系

**保留:**
- `src/api/feishu.ts` - WebSocket Bot（接收消息）
- `FeishuSessionManager` - 会话管理

**重构:**
- `src/services/notification/feishu-service.ts` → 改为 `FeishuChannel`
- `send_feishu_alert` 工具 → 调用 `NotificationService`

**新增:**
- `src/services/notification/notification-service.ts`
- `src/services/notification/notification-channel.ts`
- `src/services/notification/feishu-channel.ts`

---

## Agent 工具集成

### 更新现有工具

**`send_feishu_alert` → `send_notification`**

```typescript
// 新工具定义
{
  name: "send_notification",
  description: "发送通知消息（交易信号、市场提醒等）",
  parameters: {
    type: 'text' | 'card',
    title?: string,
    content: string,
    metadata?: object
  }
}

// 实现
execute: async (params) => {
  await notificationService.sendCard({
    title: params.title,
    content: params.content,
    type: params.type,
    metadata: params.metadata
  })
}
```

### 新增便捷工具

**1. `send_trade_signal`** - 专门用于交易信号
```typescript
parameters: {
  action: 'buy' | 'sell',
  symbol: string,
  price: number,
  reason: string,
  confidence: number
}
// 内部格式化为标准卡片
```

**2. `send_market_brief`** - 市场简报
```typescript
parameters: {
  summary: string,
  highlights: string[],
  risks?: string[]
}
```

**3. `send_risk_warning`** - 风险警告
```typescript
parameters: {
  level: 'low' | 'medium' | 'high',
  message: string
}
```

### 工具注册

```typescript
// src/tools/notification-tools.ts
export const notificationTools = [
  sendNotificationTool,
  sendTradeSignalTool,
  sendMarketBriefTool,
  sendRiskWarningTool
]

// src/infrastructure/tools/index.ts
import { notificationTools } from '../tools/notification-tools.js'
export const allCustomTools = [
  ...notificationTools,
  // ... other tools
]
```

---

## 错误处理

### 策略

**1. 配置缺失**
```typescript
// FeishuChannel.isAvailable() 返回 false
// NotificationService 静默跳过，记录警告日志
console.warn('[Notification] Feishu channel not configured, skipping')
```

**2. 发送失败**
```typescript
// 重试 3 次，指数退避（1s, 2s, 4s）
// 最终失败 → 记录错误，不阻塞 agent 执行
console.error('[Notification] Failed to send after 3 retries:', error)
```

**3. 频率限制**
```typescript
// 飞书限制：20 条/分钟
// 内置队列，自动延迟发送
// 队列溢出 → 丢弃旧消息，保留最新
```

---

## 测试策略

### 单元测试

- `NotificationService` - mock channel，验证路由逻辑
- `FeishuChannel` - mock Lark SDK，验证消息格式转换
- 工具函数 - 验证参数校验和格式化

### 集成测试

```typescript
// src/services/notification/feishu-channel.test.ts
// 使用真实飞书测试群
describe('FeishuChannel', () => {
  it('should send card message', async () => {
    const channel = new FeishuChannel({...testConfig})
    await channel.send({
      title: 'Test',
      content: 'Integration test',
      type: 'card'
    })
  })
})
```

### 手动测试脚本

```typescript
// src/scripts/test-notification.ts
// 快速验证飞书配置和消息格式
```

---

## 实现文件清单

### 新增文件

1. `src/services/notification/notification-channel.ts` - 抽象基类
2. `src/services/notification/notification-service.ts` - 统一服务
3. `src/services/notification/feishu-channel.ts` - 飞书实现
4. `src/tools/notification-tools.ts` - Agent 工具
5. `src/scripts/test-notification.ts` - 手动测试脚本

### 修改文件

1. `src/services/notification/feishu-service.ts` - 重构为 FeishuChannel
2. `src/tools/monitor-tools.ts` - 更新为使用 NotificationService
3. `src/infrastructure/tools/index.ts` - 注册通知工具

### 保留文件

1. `src/api/feishu.ts` - WebSocket Bot（不变）
2. `src/api/feishu-session-manager.ts` - 会话管理（不变）

---

## 实施路径

### 阶段 1: 核心基础设施
1. 创建 `NotificationChannel` 抽象类
2. 创建 `NotificationService` 及基础发送方法
3. 实现 `FeishuChannel`，支持文本和卡片

### 阶段 2: 工具集成
1. 创建新的通知工具
2. 更新现有 `send_feishu_alert` 使用 NotificationService
3. 在工具注册表中注册工具

### 阶段 3: 测试与验证
1. 编写所有组件的单元测试
2. 创建真实飞书的集成测试
3. 构建手动测试脚本
4. 用真实 agent 工作流验证

### 阶段 4: 清理
1. 如果完全替换，删除旧的 `FeishuService`
2. 更新文档
3. 添加使用示例到 README

---

## 未来扩展

### 额外渠道
- 钉钉 channel
- 企业微信 channel
- 邮件 channel
- 短信 channel

### 增强功能
- 消息模板
- 定时通知
- 通知历史/审计日志
- 用户偏好管理（每用户通知设置）

### 高级能力
- 带按钮的交互式卡片
- 文件附件
- 语音消息
- 视频通知

---

## 成功标准

1. ✅ Agent 可以通过统一 API 发送文本、卡片、图片通知
2. ✅ 飞书集成在失败时不阻塞 agent 执行
3. ✅ 系统优雅处理频率限制
4. ✅ 代码与特定通知提供商解耦
5. ✅ 所有现有通知用例继续工作
6. ✅ 新代码测试覆盖率 ≥ 80%
7. ✅ 手动测试脚本验证端到端流程

---

## 非目标

- 实时双向通信（已由 WebSocket Bot 处理）
- 消息线程/会话管理
- 用户认证/授权
- 分析/指标收集（可后续添加）
