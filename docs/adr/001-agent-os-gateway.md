# Agent OS 定位与架构决策

**核心问题**: Agent OS 是做**大网关（统一入口）**还是**各自对接**？

---

## 🤔 两种架构方向

### **方向 A: Agent OS 作为大网关（统一入口）**

```
┌─────────────────────────────────────────────────────────┐
│  所有客户端都通过 Agent OS                               │
│  ┌──────────┬──────────┬──────────┬──────────────────┐  │
│  │ Agent-ts │ Web 应用 │ 飞书应用 │ 其他应用         │  │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────────────┘  │
│       │          │          │          │                 │
│       └──────────┴──────────┴──────────┘                 │
│                    ↓                                     │
│         ┌─────────────────────────┐                      │
│         │   Agent OS (大网关)      │                      │
│         │   - HTTP API             │                      │
│         │   - CLI (HTTP wrapper)   │                      │
│         │   - WebSocket            │                      │
│         │   - gRPC (可选)          │                      │
│         └──────────┬───────────────┘                      │
└────────────────────┼────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│  统一服务层                                              │
│  - 认证/授权                                             │
│  - 限流/熔断                                             │
│  - 日志/监控                                             │
│  - 通知路由                                              │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│  Provider Layer                                          │
│  Feishu | Slack | Email | SMS | ...                     │
└─────────────────────────────────────────────────────────┘
```

**特点**:
- ✅ **统一入口**: 所有应用都通过 Agent OS
- ✅ **统一配置**: 渠道配置在 Agent OS
- ✅ **统一监控**: 所有通知都有日志
- ✅ **统一治理**: 认证、限流、熔断
- ✅ **Provider 抽象**: 底层实现统一管理

---

### **方向 B: 各自对接（分散式）**

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Agent-ts    │  │  Web 应用     │  │  飞书应用     │
│  自己对接     │  │  自己对接     │  │  自己对接     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ↓                 ↓                 ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Feishu API   │  │ Slack API    │  │ Email SMTP   │
└──────────────┘  └──────────────┘  └──────────────┘
```

**特点**:
- ❌ 配置分散
- ❌ 日志分散
- ❌ 重复实现
- ❌ 难以统一治理

---

## 🎯 推荐：Agent OS 作为大网关

### **理由**

#### **1. OpenClaw 的设计理念**

OpenClaw 就是一个**统一的消息路由网关**：
```
所有应用 → OpenClaw → 各种 Channel (Telegram/Discord/Slack...)
```

#### **2. 微服务最佳实践**

**API Gateway 模式**:
```
前端应用、移动端、第三方 → API Gateway → 后端服务
```

通知系统也应该是一个 Gateway。

#### **3. 统一治理的需求**

**需要统一管理**:
- 渠道配置（webhook URLs、credentials）
- 发送日志（谁、什么时候、发了什么）
- 限流控制（防止刷屏）
- 错误重试（失败自动重试）
- 监控告警（发送成功率）

**如果各自对接**:
- ❌ 每个应用都要实现一遍
- ❌ 配置散落各处
- ❌ 无法统一监控

---

## 🏗️ 最终架构设计

### **层次结构**

```
┌─────────────────────────────────────────────────────────┐
│  Access Layer（访问层）                                  │
│  ┌────────────────────────────────────────────────────┐ │
│  │  HTTP API (主要)                                   │ │
│  │  - RESTful endpoints                               │ │
│  │  - WebSocket (实时推送)                            │ │
│  │  - gRPC (高性能场景)                               │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────┐ │
│  │  CLI (HTTP wrapper)                                │ │
│  │  - 内部调用 HTTP API                               │ │
│  │  - 简化命令行操作                                  │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Gateway Layer（网关层）                                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │  认证/授权      │  限流/熔断    │  日志/监控        │ │
│  │  API Key        │  Rate Limit   │  Metrics          │ │
│  │  JWT Token      │  Circuit      │  Logging          │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Service Layer（业务层）                                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │  NotificationService                               │ │
│  │  - 通知路由                                        │ │
│  │  - 重试机制                                        │ │
│  │  - 异步队列                                        │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Provider Registry（提供商注册中心）                     │
│  - 动态加载 Provider                                     │
│  - 支持插件机制                                          │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Provider Layer（提供商层）                              │
│  Feishu | Slack | Email | SMS | Telegram | Discord      │
└─────────────────────────────────────────────────────────┘
```

---

### **调用链路**

#### **Agent-ts 调用**

```typescript
// Agent 工具
await agent.call('notification_send', {
  channel: 'trading',
  title: 'Test',
  content: 'Hello'
});

↓

// 工具内部 (优先 HTTP)
fetch('http://agent-os:8080/api/v1/notifications/send', {
  method: 'POST',
  body: JSON.stringify({...})
});

↓

// Agent OS HTTP API
router.POST("/api/v1/notifications/send", handler)

↓

// NotificationService
service.Send(ctx, req)

↓

// Provider Registry
provider := registry.Get("feishu")

↓

// Feishu Provider
provider.Send(config, message)

↓

// 飞书 Webhook
POST https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

---

#### **CLI 调用（HTTP wrapper）**

```bash
agent-os notify send --channel trading --title "Test" --content "Hello"

↓

// CLI 内部实现
func (cmd *notifySendCmd) Run() {
    // 调用 HTTP API
    client := &http.Client{}
    resp, err := client.Post(
        "http://localhost:8080/api/v1/notifications/send",
        "application/json",
        body
    )
    // ...
}

↓

// 后续同上
```

**CLI 是 HTTP 的包装器，不直接调用 Service**。

---

#### **Web 应用调用**

```javascript
// 前端调用
fetch('http://agent-os-api.company.com/api/v1/notifications/send', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer token',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    channel: 'trading',
    title: 'Test',
    content: 'Hello'
  })
});

↓

// 后续同上
```

---

#### **飞书应用调用**

```python
# 飞书机器人收到消息
@app.route('/webhook', methods=['POST'])
def handle_feishu_webhook():
    # 调用 Agent OS API
    requests.post(
        'http://agent-os:8080/api/v1/notifications/send',
        json={
            'channel': 'trading',
            'title': '用户反馈',
            'content': message
        }
    )
```

---

## 🔧 实施细节

### **1. HTTP API Server**

```go
// internal/api/server.go

type Server struct {
    service *service.NotificationService
    config  *config.Config
}

func (s *Server) Start() error {
    r := gin.Default()
    
    // 中间件
    r.Use(middleware.Logger())
    r.Use(middleware.RateLimit())
    r.Use(middleware.Auth())
    
    // API routes
    v1 := r.Group("/api/v1")
    {
        v1.POST("/notifications/send", s.handleSend)
        v1.GET("/notifications/channels", s.handleListChannels)
        v1.GET("/notifications/logs", s.handleGetLogs)
        v1.GET("/notifications/providers", s.handleListProviders)
    }
    
    return r.Run(":8080")
}
```

---

### **2. CLI 作为 HTTP Wrapper**

```go
// internal/cmd/notify.go

var notifySendCmd = &cobra.Command{
    Use:   "send",
    Short: "Send a notification",
    RunE: func(cmd *cobra.Command, args []string) error {
        channel, _ := cmd.Flags().GetString("channel")
        title, _ := cmd.Flags().GetString("title")
        content, _ := cmd.Flags().GetString("content")
        
        // 构建请求
        req := map[string]interface{}{
            "channel": channel,
            "title":   title,
            "content": content,
        }
        
        // 调用 HTTP API
        apiURL := os.Getenv("AGENT_OS_API_URL")
        if apiURL == "" {
            apiURL = "http://localhost:8080"
        }
        
        body, _ := json.Marshal(req)
        resp, err := http.Post(
            apiURL+"/api/v1/notifications/send",
            "application/json",
            bytes.NewBuffer(body),
        )
        
        if err != nil {
            return fmt.Errorf("failed to call API: %w", err)
        }
        
        // 解析响应
        var result map[string]interface{}
        json.NewDecoder(resp.Body).Decode(&result)
        
        if result["success"].(bool) {
            fmt.Println("✅ Notification sent successfully")
        } else {
            fmt.Printf("❌ Failed: %s\n", result["error"])
        }
        
        return nil
    },
}
```

**关键**: CLI 不直接调用 Service，而是调用 HTTP API。

---

### **3. Agent 工具也调用 HTTP API**

```typescript
// agent-ts/src/infrastructure/tools/notification/notification-tools.ts

export const notificationSendTool: ToolDefinition = {
  name: "notification_send",
  
  async execute(_toolCallId, params: any) {
    const agentOsUrl = process.env.AGENT_OS_API_URL || 'http://localhost:8080';
    
    try {
      const response = await fetch(`${agentOsUrl}/api/v1/notifications/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      
      const result = await response.json();
      
      return {
        content: [{ 
          type: "text" as const, 
          text: result.success 
            ? `✅ 通知已发送到 ${params.channel} 群` 
            : `❌ 发送失败: ${result.error}` 
        }]
      };
    } catch (error) {
      return {
        content: [{ 
          type: "text" as const, 
          text: `❌ 无法连接到 Agent OS API: ${error.message}` 
        }]
      };
    }
  }
};
```

**无降级到 CLI**，因为 CLI 本身也是调用 HTTP API。

---

## ✅ 这个架构的优势

### **1. 统一入口**
- 所有客户端都通过 HTTP API
- 配置集中管理
- 日志集中收集

### **2. 标准化**
- RESTful API（行业标准）
- 任何语言都能调用
- 易于集成第三方

### **3. 可扩展**
- 添加新 Provider 无需改客户端
- 水平扩展（多实例）
- 负载均衡

### **4. 易于治理**
- 统一认证（API Key / JWT）
- 统一限流（防止滥用）
- 统一监控（Prometheus/Grafana）

### **5. CLI 简化**
- CLI 只是 HTTP 包装器
- 减少重复代码
- 保持 CLI 简单

---

## 📋 实施计划

### **Phase 4: 重构为大网关架构（3-4 天）**

**Day 1: HTTP API Server**
- [ ] 创建 HTTP Server
- [ ] 实现 API endpoints
- [ ] 中间件（日志、认证、限流）

**Day 2: CLI 改为 HTTP Wrapper**
- [ ] 重构 CLI 命令调用 HTTP API
- [ ] 添加环境变量配置
- [ ] 错误处理

**Day 3: Agent 工具改造**
- [ ] 移除 CLI 调用
- [ ] 只调用 HTTP API
- [ ] 错误处理

**Day 4: Provider 抽象**
- [ ] Provider 接口
- [ ] Provider Registry
- [ ] Feishu/Slack/Email Provider

---

## 🎯 最终回答

### **你的想法是对的！**

> "cli->http cli 是包裹http的对外包"

✅ **完全正确！**

> "os 是要做大网关还是agent，飞书类应用，web 分别做对接，还是做统一"

✅ **应该做统一大网关！**

**所有客户端 → Agent OS HTTP API → Provider**

---

**需要我立即开始重构为大网关架构吗？**
