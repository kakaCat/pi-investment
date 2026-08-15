# 统一通知系统设计（参考 OpenClaw）

**日期**: 2026-08-14  
**目标**: 设计数据库驱动的通知抽象层

---

## 🎯 设计理念（参考 OpenClaw）

### OpenClaw 的 Channel 架构

OpenClaw 将不同的通信渠道（Telegram、Discord、Slack 等）抽象为统一的 **Channel** 概念：

1. **Provider/Adapter 模式**: 每个通信平台是一个 Provider
2. **数据库配置**: Channel 配置存储在数据库
3. **统一接口**: 通过统一的 API 发送/接收消息
4. **动态加载**: 运行时动态加载和切换 Channel

---

## 🏗️ Pi Investment 通知系统架构

### 核心概念

```
NotificationChannel (通知渠道)
├── Provider (提供商): Feishu, Slack, Email, SMS...
├── Target (目标): 具体的群/用户/邮箱
├── Template (模板): 消息格式
└── Rule (规则): 什么时候发送什么消息
```

---

## 📊 数据库设计

### 表 1: `notification_providers` (通知提供商)

```sql
CREATE TABLE notification_providers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(32) NOT NULL UNIQUE,  -- 'feishu', 'slack', 'email'
    name VARCHAR(100) NOT NULL,         -- '飞书', 'Slack', '邮件'
    type VARCHAR(32) NOT NULL,          -- 'webhook', 'api', 'smtp'
    enabled BOOLEAN DEFAULT true,
    config JSONB,                        -- 提供商级别配置（如 APP_ID）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 示例数据
INSERT INTO notification_providers (code, name, type, config) VALUES
('feishu', '飞书', 'hybrid', '{
  "bot": {
    "app_id": "cli_xxx",
    "app_secret": "xxx"
  }
}'),
('slack', 'Slack', 'webhook', '{}'),
('email', '邮件', 'smtp', '{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587
}');
```

---

### 表 2: `notification_channels` (通知渠道)

```sql
CREATE TABLE notification_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_id UUID NOT NULL REFERENCES notification_providers(id),
    code VARCHAR(64) NOT NULL UNIQUE,   -- 'trading', 'alerts', 'reports'
    name VARCHAR(100) NOT NULL,          -- '交易群', '告警群'
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL,               -- 渠道级别配置（如 webhook URL）
    metadata JSONB DEFAULT '{}',         -- 额外元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_channels_provider ON notification_channels(provider_id);
CREATE INDEX idx_channels_code ON notification_channels(code);
CREATE INDEX idx_channels_enabled ON notification_channels(enabled);

-- 示例数据
INSERT INTO notification_channels (provider_id, code, name, description, config) VALUES
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'trading',
    '交易群',
    '接收交易信号和执行确认',
    '{
      "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/trading_xxx",
      "chat_id": "oc_trading_xxx"
    }'
),
(
    (SELECT id FROM notification_providers WHERE code='feishu'),
    'alerts',
    '告警群',
    '接收风险预警和系统异常',
    '{
      "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/alerts_xxx",
      "chat_id": "oc_alerts_xxx"
    }'
);
```

---

### 表 3: `notification_templates` (消息模板)

```sql
CREATE TABLE notification_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(64) NOT NULL UNIQUE,    -- 'daily_report', 'trade_signal'
    name VARCHAR(100) NOT NULL,           -- '每日报告', '交易信号'
    provider_id UUID REFERENCES notification_providers(id), -- NULL = 通用
    template JSONB NOT NULL,              -- 模板内容
    variables TEXT[],                     -- 需要的变量
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 示例数据
INSERT INTO notification_templates (code, name, provider_id, template, variables) VALUES
(
    'daily_report',
    '每日报告',
    (SELECT id FROM notification_providers WHERE code='feishu'),
    '{
      "title": "📊 每日投资报告 - {{date}}",
      "color": "blue",
      "sections": [
        {
          "title": "💰 持仓表现",
          "fields": [
            "总资产: {{total_assets}}",
            "可用资金: {{cash}}",
            "持仓数量: {{holdings_count}}只",
            "总盈亏: {{total_pnl}} ({{total_pnl_pct}}%)"
          ]
        },
        {
          "title": "📊 交易情况",
          "fields": [
            "今日交易: {{trades_today}}笔",
            "买入: {{buy_count}}笔",
            "卖出: {{sell_count}}笔"
          ]
        }
      ]
    }',
    ARRAY['date', 'total_assets', 'cash', 'holdings_count', 'total_pnl', 'total_pnl_pct', 'trades_today', 'buy_count', 'sell_count']
);
```

---

### 表 4: `notification_rules` (通知规则)

```sql
CREATE TABLE notification_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(64) NOT NULL UNIQUE,     -- 'daily_report_morning', 'trade_alert'
    name VARCHAR(100) NOT NULL,            -- '每日盘前报告', '交易告警'
    enabled BOOLEAN DEFAULT true,
    trigger_type VARCHAR(32) NOT NULL,     -- 'schedule', 'event', 'manual'
    trigger_config JSONB,                  -- 触发配置
    channel_id UUID NOT NULL REFERENCES notification_channels(id),
    template_id UUID REFERENCES notification_templates(id),
    priority INTEGER DEFAULT 5,            -- 1-10，数字越小优先级越高
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 示例数据
INSERT INTO notification_rules (code, name, trigger_type, trigger_config, channel_id, template_id) VALUES
(
    'daily_report_morning',
    '每日盘前报告',
    'schedule',
    '{
      "cron": "0 8 * * *",
      "timezone": "Asia/Shanghai"
    }',
    (SELECT id FROM notification_channels WHERE code='trading'),
    (SELECT id FROM notification_templates WHERE code='daily_report')
);
```

---

### 表 5: `notification_logs` (通知日志)

```sql
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id UUID NOT NULL REFERENCES notification_channels(id),
    template_id UUID REFERENCES notification_templates(id),
    rule_id UUID REFERENCES notification_rules(id),
    status VARCHAR(32) NOT NULL,           -- 'pending', 'sent', 'failed'
    message_id VARCHAR(255),               -- 提供商返回的消息 ID
    payload JSONB NOT NULL,                -- 发送的内容
    response JSONB,                        -- 提供商响应
    error TEXT,                            -- 错误信息
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logs_channel ON notification_logs(channel_id);
CREATE INDEX idx_logs_status ON notification_logs(status);
CREATE INDEX idx_logs_created ON notification_logs(created_at DESC);
```

---

## 🔧 代码实现架构

### 1. Provider 接口（抽象层）

```typescript
// src/notification/providers/base-provider.ts

export interface NotificationPayload {
  title: string;
  content: string;
  color?: string;
  urgency?: 'low' | 'normal' | 'high' | 'critical';
  metadata?: Record<string, any>;
}

export interface SendResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

export abstract class NotificationProvider {
  abstract readonly code: string;
  abstract readonly name: string;
  
  constructor(protected config: Record<string, any>) {}
  
  abstract async send(
    channelConfig: Record<string, any>,
    payload: NotificationPayload
  ): Promise<SendResult>;
  
  abstract async verify(
    channelConfig: Record<string, any>
  ): Promise<boolean>;
}
```

---

### 2. Feishu Provider 实现

```typescript
// src/notification/providers/feishu-provider.ts

import { NotificationProvider, NotificationPayload, SendResult } from './base-provider.js';
import axios from 'axios';

export class FeishuProvider extends NotificationProvider {
  readonly code = 'feishu';
  readonly name = '飞书';
  
  async send(
    channelConfig: Record<string, any>,
    payload: NotificationPayload
  ): Promise<SendResult> {
    const webhook = channelConfig.webhook;
    if (!webhook) {
      return { success: false, error: 'Missing webhook URL' };
    }
    
    const colorMap = {
      low: 'grey',
      normal: 'blue',
      high: 'orange',
      critical: 'red'
    };
    
    const card = {
      msg_type: 'interactive',
      card: {
        header: {
          title: { tag: 'plain_text', content: payload.title },
          template: colorMap[payload.urgency || 'normal']
        },
        elements: [
          {
            tag: 'div',
            text: { tag: 'lark_md', content: payload.content }
          }
        ]
      }
    };
    
    try {
      const response = await axios.post(webhook, card, {
        timeout: 10000,
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.data.code === 0) {
        return { 
          success: true,
          messageId: response.data.data?.message_id 
        };
      } else {
        return { 
          success: false,
          error: response.data.msg 
        };
      }
    } catch (error: any) {
      return { 
        success: false,
        error: error.message 
      };
    }
  }
  
  async verify(channelConfig: Record<string, any>): Promise<boolean> {
    return !!channelConfig.webhook;
  }
}
```

---

### 3. Provider Registry（注册中心）

```typescript
// src/notification/provider-registry.ts

import { NotificationProvider } from './providers/base-provider.js';
import { FeishuProvider } from './providers/feishu-provider.js';
import { SlackProvider } from './providers/slack-provider.js';
import { EmailProvider } from './providers/email-provider.js';

export class ProviderRegistry {
  private providers: Map<string, typeof NotificationProvider> = new Map();
  
  constructor() {
    this.register(FeishuProvider);
    this.register(SlackProvider);
    this.register(EmailProvider);
  }
  
  register(providerClass: typeof NotificationProvider) {
    const instance = new providerClass({});
    this.providers.set(instance.code, providerClass);
  }
  
  get(code: string): typeof NotificationProvider | undefined {
    return this.providers.get(code);
  }
  
  list(): string[] {
    return Array.from(this.providers.keys());
  }
}

export const providerRegistry = new ProviderRegistry();
```

---

### 4. Notification Service（业务层）

```typescript
// src/notification/notification.service.ts

import { ProviderRegistry } from './provider-registry.js';
import { NotificationRepository } from './notification.repository.js';
import { NotificationPayload } from './providers/base-provider.js';

export class NotificationService {
  constructor(
    private registry: ProviderRegistry,
    private repository: NotificationRepository
  ) {}
  
  async send(channelCode: string, payload: NotificationPayload): Promise<string> {
    // 1. 从数据库获取 channel 配置
    const channel = await this.repository.getChannelByCode(channelCode);
    if (!channel || !channel.enabled) {
      throw new Error(`Channel '${channelCode}' not found or disabled`);
    }
    
    // 2. 从数据库获取 provider 配置
    const provider = await this.repository.getProvider(channel.provider_id);
    if (!provider || !provider.enabled) {
      throw new Error(`Provider for channel '${channelCode}' not available`);
    }
    
    // 3. 实例化 provider
    const ProviderClass = this.registry.get(provider.code);
    if (!ProviderClass) {
      throw new Error(`Provider '${provider.code}' not registered`);
    }
    
    const providerInstance = new ProviderClass(provider.config);
    
    // 4. 创建日志记录（pending）
    const logId = await this.repository.createLog({
      channel_id: channel.id,
      status: 'pending',
      payload: payload
    });
    
    // 5. 发送消息
    try {
      const result = await providerInstance.send(channel.config, payload);
      
      // 6. 更新日志
      await this.repository.updateLog(logId, {
        status: result.success ? 'sent' : 'failed',
        message_id: result.messageId,
        error: result.error,
        sent_at: result.success ? new Date() : undefined
      });
      
      return logId;
    } catch (error: any) {
      await this.repository.updateLog(logId, {
        status: 'failed',
        error: error.message
      });
      throw error;
    }
  }
  
  async sendWithTemplate(
    channelCode: string,
    templateCode: string,
    variables: Record<string, any>
  ): Promise<string> {
    // 1. 从数据库获取模板
    const template = await this.repository.getTemplateByCode(templateCode);
    if (!template) {
      throw new Error(`Template '${templateCode}' not found`);
    }
    
    // 2. 渲染模板
    const payload = this.renderTemplate(template, variables);
    
    // 3. 发送
    return this.send(channelCode, payload);
  }
  
  private renderTemplate(template: any, variables: Record<string, any>): NotificationPayload {
    // 简单的模板渲染（可以用 Handlebars 等库）
    let title = template.template.title;
    let content = '';
    
    // 替换变量
    for (const [key, value] of Object.entries(variables)) {
      const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
      title = title.replace(regex, String(value));
    }
    
    // 渲染 sections
    for (const section of template.template.sections || []) {
      content += `**${section.title}**\n`;
      for (const field of section.fields) {
        let fieldText = field;
        for (const [key, value] of Object.entries(variables)) {
          const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
          fieldText = fieldText.replace(regex, String(value));
        }
        content += `${fieldText}\n`;
      }
      content += '\n';
    }
    
    return {
      title,
      content: content.trim(),
      color: template.template.color
    };
  }
  
  async listChannels(): Promise<any[]> {
    return this.repository.listChannels();
  }
  
  async getChannel(code: string): Promise<any> {
    return this.repository.getChannelByCode(code);
  }
}
```

---

### 5. Repository 层（数据访问）

```typescript
// src/notification/notification.repository.ts

import { Pool } from 'pg';

export class NotificationRepository {
  constructor(private pool: Pool) {}
  
  async getChannelByCode(code: string): Promise<any> {
    const result = await this.pool.query(
      `SELECT c.*, p.code as provider_code, p.config as provider_config
       FROM notification_channels c
       JOIN notification_providers p ON c.provider_id = p.id
       WHERE c.code = $1 AND c.enabled = true`,
      [code]
    );
    return result.rows[0];
  }
  
  async getProvider(id: string): Promise<any> {
    const result = await this.pool.query(
      'SELECT * FROM notification_providers WHERE id = $1 AND enabled = true',
      [id]
    );
    return result.rows[0];
  }
  
  async getTemplateByCode(code: string): Promise<any> {
    const result = await this.pool.query(
      'SELECT * FROM notification_templates WHERE code = $1',
      [code]
    );
    return result.rows[0];
  }
  
  async createLog(log: any): Promise<string> {
    const result = await this.pool.query(
      `INSERT INTO notification_logs (channel_id, status, payload)
       VALUES ($1, $2, $3)
       RETURNING id`,
      [log.channel_id, log.status, JSON.stringify(log.payload)]
    );
    return result.rows[0].id;
  }
  
  async updateLog(id: string, updates: any): Promise<void> {
    const fields: string[] = [];
    const values: any[] = [];
    let paramIndex = 1;
    
    if (updates.status) {
      fields.push(`status = $${paramIndex++}`);
      values.push(updates.status);
    }
    if (updates.message_id) {
      fields.push(`message_id = $${paramIndex++}`);
      values.push(updates.message_id);
    }
    if (updates.error) {
      fields.push(`error = $${paramIndex++}`);
      values.push(updates.error);
    }
    if (updates.sent_at) {
      fields.push(`sent_at = $${paramIndex++}`);
      values.push(updates.sent_at);
    }
    
    values.push(id);
    
    await this.pool.query(
      `UPDATE notification_logs SET ${fields.join(', ')} WHERE id = $${paramIndex}`,
      values
    );
  }
  
  async listChannels(): Promise<any[]> {
    const result = await this.pool.query(
      `SELECT c.*, p.name as provider_name
       FROM notification_channels c
       JOIN notification_providers p ON c.provider_id = p.id
       WHERE c.enabled = true
       ORDER BY c.code`
    );
    return result.rows;
  }
}
```

---

## 🎨 使用示例

### 1. 发送简单通知

```typescript
const notificationService = new NotificationService(registry, repository);

// 发送到交易群
await notificationService.send('trading', {
  title: '🚨 交易信号触发',
  content: '**股票**: 600519.SH\n**信号**: 买入\n**价格**: ¥1,205',
  urgency: 'high'
});
```

### 2. 使用模板发送

```typescript
await notificationService.sendWithTemplate('trading', 'daily_report', {
  date: '2026-08-14',
  total_assets: 1050000,
  cash: 79500,
  holdings_count: 11,
  total_pnl: 50000,
  total_pnl_pct: 5.0,
  trades_today: 2,
  buy_count: 1,
  sell_count: 1
});
```

### 3. Agent OS CLI

```bash
# 列出所有渠道
agent-os notify list

# 输出:
# CODE      NAME    PROVIDER  STATUS
# trading   交易群  飞书      ✅
# alerts    告警群  飞书      ✅
# reports   报告群  飞书      ✅

# 发送通知
agent-os notify send trading "标题" "内容"

# 使用模板
agent-os notify template daily_report --channel trading --var date=2026-08-14 --var total_assets=1050000

# 测试渠道
agent-os notify test trading
```

---

## 📋 数据库管理界面

### Web API 端点

```typescript
// GET /api/notifications/channels
// 列出所有渠道

// GET /api/notifications/channels/:code
// 获取渠道详情

// POST /api/notifications/channels
// 创建新渠道
{
  "code": "vip",
  "name": "VIP 客户群",
  "provider": "feishu",
  "config": {
    "webhook": "https://..."
  }
}

// PUT /api/notifications/channels/:code
// 更新渠道配置

// DELETE /api/notifications/channels/:code
// 删除渠道

// GET /api/notifications/logs?channel=trading&status=failed
// 查询发送日志

// POST /api/notifications/test/:code
// 测试渠道
```

---

## ✅ 优势总结

### 1. **灵活配置**
- ✅ 无需改代码即可添加新渠道
- ✅ 无需重启服务即可修改配置
- ✅ 支持热更新

### 2. **统一抽象**
- ✅ 一套 API 支持多种提供商（飞书、Slack、邮件...）
- ✅ 方便切换提供商
- ✅ 易于扩展新提供商

### 3. **可追溯**
- ✅ 所有通知都有日志
- ✅ 可以查询发送历史
- ✅ 失败重试机制

### 4. **模板化**
- ✅ 业务逻辑与展示分离
- ✅ 可视化配置模板
- ✅ 统一消息风格

### 5. **规则驱动**
- ✅ 定时任务配置在数据库
- ✅ 事件触发规则可配置
- ✅ 动态调整规则

---

## 🚀 实施路线图

### Phase 1: 基础架构（Week 1）
- [ ] 创建数据库表
- [ ] 实现 Provider 接口
- [ ] 实现 Feishu Provider
- [ ] 实现 Notification Service
- [ ] 实现 Repository

### Phase 2: CLI 集成（Week 1）
- [ ] Agent OS CLI 命令
- [ ] 迁移现有 Feishu Driver

### Phase 3: Agent-ts 集成（Week 2）
- [ ] 迁移现有通知代码
- [ ] 使用新的 Notification Service

### Phase 4: 管理界面（Week 2）
- [ ] Web API
- [ ] 管理页面（增删改查渠道）
- [ ] 日志查询界面

### Phase 5: 高级功能（Week 3）
- [ ] 失败重试
- [ ] 消息队列
- [ ] 限流保护
- [ ] 更多 Provider（Slack、Email）

---

**这个设计符合你的期望吗？需要我立即开始实施吗？**
