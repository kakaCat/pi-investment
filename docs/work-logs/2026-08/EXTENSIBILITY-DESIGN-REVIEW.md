# 通知系统可扩展性设计审视

**日期**: 2026-08-14  
**问题**: 当前设计的可扩展性不足

---

## 🔍 当前设计的问题

### **问题 1: Provider 实现不完整**

**当前代码**:
```go
// service/notification_service.go
switch provider.Code {
case "feishu":
    messageID, sendErr = s.sendFeishu(channel.Config, req)
default:
    sendErr = fmt.Errorf("unsupported provider: %s", provider.Code)
}
```

**问题**:
- ❌ 硬编码 switch case
- ❌ 添加新 Provider 需要改 Service 代码
- ❌ 没有真正的 Provider 接口抽象

---

### **问题 2: 没有对外应用接口**

**当前架构**:
```
Agent-ts → Agent OS CLI → Service → Feishu
```

**缺失**:
- ❌ 没有 HTTP API（对外应用无法调用）
- ❌ 没有 gRPC/REST 接口
- ❌ 外部应用无法使用通知系统

---

## 🎯 OpenClaw 的架构（参考）

### **OpenClaw Channels 架构**

```
┌─────────────────────────────────────────┐
│  Application Layer                       │
│  - HTTP API                              │
│  - gRPC API                              │
│  - CLI                                   │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Channel Manager                         │
│  - Route messages                        │
│  - Load adapters dynamically             │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Adapter Interface                       │
│  - send(channel, message)                │
│  - verify(channel)                       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Concrete Adapters                       │
│  - TelegramAdapter                       │
│  - DiscordAdapter                        │
│  - SlackAdapter                          │
│  - EmailAdapter                          │
└─────────────────────────────────────────┘
```

**关键设计**:
1. ✅ **动态加载**: Adapters 通过插件机制加载
2. ✅ **统一接口**: 所有 Adapter 实现相同接口
3. ✅ **配置驱动**: Channel 配置决定使用哪个 Adapter
4. ✅ **多协议**: HTTP API、gRPC、CLI 都可以调用

---

## 🏗️ 重新设计：可扩展的通知系统

### **架构图**

```
┌─────────────────────────────────────────────────────────┐
│  Access Layer（访问层）                                  │
│  ┌────────────┬────────────┬────────────┬─────────────┐ │
│  │ HTTP API   │ gRPC API   │ CLI        │ SDK (Go/TS) │ │
│  └────────────┴────────────┴────────────┴─────────────┘ │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Service Layer（服务层）                                 │
│  ┌──────────────────────────────────────────────────┐   │
│  │  NotificationService                             │   │
│  │  - Send(channel, message)                        │   │
│  │  - ListChannels()                                │   │
│  │  - GetLogs()                                     │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Provider Registry（提供商注册中心）                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │  registry.Register("feishu", FeishuProvider)     │   │
│  │  registry.Register("slack", SlackProvider)       │   │
│  │  registry.Register("email", EmailProvider)       │   │
│  │  registry.Get("feishu") → FeishuProvider         │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Provider Interface（提供商接口）                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  type Provider interface {                       │   │
│  │    Send(config, message) Result                  │   │
│  │    Verify(config) bool                           │   │
│  │    Name() string                                 │   │
│  │  }                                               │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  Concrete Providers（具体实现）                          │
│  ┌──────────┬──────────┬──────────┬──────────────────┐  │
│  │ Feishu   │ Slack    │ Email    │ Telegram/Discord │  │
│  │ Provider │ Provider │ Provider │ Provider         │  │
│  └──────────┴──────────┴──────────┴──────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│  External Services（外部服务）                           │
│  ┌──────────┬──────────┬──────────┬──────────────────┐  │
│  │ 飞书     │ Slack    │ SMTP     │ Telegram/Discord │  │
│  │ Webhook  │ Webhook  │ Server   │ API              │  │
│  └──────────┴──────────┴──────────┴──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 重新设计的实现

### **1. Provider 接口（真正的抽象）**

```go
// internal/provider/provider.go

package provider

import "context"

// Message 统一消息格式
type Message struct {
    Title    string
    Content  string
    Format   string  // markdown, html, plain
    Priority string  // low, normal, high, critical
    Metadata map[string]interface{}
}

// Result 发送结果
type Result struct {
    Success   bool
    MessageID string
    Error     error
}

// Provider 提供商接口
type Provider interface {
    // Name 提供商名称
    Name() string
    
    // Send 发送消息
    Send(ctx context.Context, config map[string]interface{}, msg *Message) (*Result, error)
    
    // Verify 验证配置是否有效
    Verify(ctx context.Context, config map[string]interface{}) error
    
    // SupportedFormats 支持的消息格式
    SupportedFormats() []string
}
```

---

### **2. Provider Registry（注册中心）**

```go
// internal/provider/registry.go

package provider

import (
    "fmt"
    "sync"
)

var (
    registry = &Registry{
        providers: make(map[string]Provider),
    }
)

type Registry struct {
    mu        sync.RWMutex
    providers map[string]Provider
}

// Register 注册提供商
func Register(provider Provider) {
    registry.mu.Lock()
    defer registry.mu.Unlock()
    registry.providers[provider.Name()] = provider
}

// Get 获取提供商
func Get(name string) (Provider, error) {
    registry.mu.RLock()
    defer registry.mu.RUnlock()
    
    provider, ok := registry.providers[name]
    if !ok {
        return nil, fmt.Errorf("provider %s not found", name)
    }
    return provider, nil
}

// List 列出所有提供商
func List() []string {
    registry.mu.RLock()
    defer registry.mu.RUnlock()
    
    names := make([]string, 0, len(registry.providers))
    for name := range registry.providers {
        names = append(names, name)
    }
    return names
}
```

---

### **3. Feishu Provider 实现**

```go
// internal/provider/feishu/feishu.go

package feishu

import (
    "context"
    "github.com/pi-investment/agent-os/internal/provider"
)

type FeishuProvider struct{}

func init() {
    // 自动注册
    provider.Register(&FeishuProvider{})
}

func (p *FeishuProvider) Name() string {
    return "feishu"
}

func (p *FeishuProvider) Send(ctx context.Context, config map[string]interface{}, msg *provider.Message) (*provider.Result, error) {
    webhook := config["webhook"].(string)
    
    // 构建飞书卡片
    card := buildFeishuCard(msg)
    
    // 发送 HTTP 请求
    // ...
    
    return &provider.Result{
        Success:   true,
        MessageID: "msg_xxx",
    }, nil
}

func (p *FeishuProvider) Verify(ctx context.Context, config map[string]interface{}) error {
    webhook, ok := config["webhook"].(string)
    if !ok || webhook == "" {
        return fmt.Errorf("webhook URL is required")
    }
    return nil
}

func (p *FeishuProvider) SupportedFormats() []string {
    return []string{"markdown", "html"}
}
```

---

### **4. Slack Provider 实现**

```go
// internal/provider/slack/slack.go

package slack

import (
    "context"
    "github.com/pi-investment/agent-os/internal/provider"
)

type SlackProvider struct{}

func init() {
    provider.Register(&SlackProvider{})
}

func (p *SlackProvider) Name() string {
    return "slack"
}

func (p *SlackProvider) Send(ctx context.Context, config map[string]interface{}, msg *provider.Message) (*provider.Result, error) {
    // Slack 实现
    // ...
}

func (p *SlackProvider) Verify(ctx context.Context, config map[string]interface{}) error {
    // 验证 Slack 配置
    // ...
}

func (p *SlackProvider) SupportedFormats() []string {
    return []string{"markdown"}
}
```

---

### **5. Email Provider 实现**

```go
// internal/provider/email/email.go

package email

import (
    "context"
    "github.com/pi-investment/agent-os/internal/provider"
    "net/smtp"
)

type EmailProvider struct{}

func init() {
    provider.Register(&EmailProvider{})
}

func (p *EmailProvider) Name() string {
    return "email"
}

func (p *EmailProvider) Send(ctx context.Context, config map[string]interface{}, msg *provider.Message) (*provider.Result, error) {
    // SMTP 发送
    smtpHost := config["smtp_host"].(string)
    smtpPort := config["smtp_port"].(int)
    // ...
}

func (p *EmailProvider) Verify(ctx context.Context, config map[string]interface{}) error {
    // 验证 SMTP 配置
    // ...
}

func (p *EmailProvider) SupportedFormats() []string {
    return []string{"html", "plain"}
}
```

---

### **6. Service 层改造**

```go
// internal/service/notification_service.go

func (s *NotificationService) Send(ctx context.Context, req *domain.SendRequest) (*domain.SendResult, error) {
    // 1. 获取 channel
    channel, err := s.repo.GetChannelByCode(ctx, req.Channel)
    if err != nil {
        return nil, err
    }
    
    // 2. 获取 provider 配置
    providerConfig, err := s.repo.GetProvider(ctx, channel.ProviderID)
    if err != nil {
        return nil, err
    }
    
    // 3. 从注册中心获取 provider 实例
    provider, err := provider.Get(providerConfig.Code)
    if err != nil {
        return nil, err
    }
    
    // 4. 发送消息
    msg := &provider.Message{
        Title:    req.Title,
        Content:  req.Content,
        Format:   "markdown",
        Priority: req.Urgency,
    }
    
    result, err := provider.Send(ctx, channel.Config, msg)
    if err != nil {
        // 记录日志
        return &domain.SendResult{Success: false, Error: err.Error()}, nil
    }
    
    // 5. 记录日志
    // ...
    
    return &domain.SendResult{
        Success:   result.Success,
        MessageID: result.MessageID,
    }, nil
}
```

---

### **7. HTTP API（对外应用接口）**

```go
// internal/api/http_server.go

package api

import (
    "github.com/gin-gonic/gin"
    "github.com/pi-investment/agent-os/internal/service"
)

type HTTPServer struct {
    service *service.NotificationService
}

func NewHTTPServer(service *service.NotificationService) *HTTPServer {
    return &HTTPServer{service: service}
}

func (s *HTTPServer) Start(addr string) error {
    r := gin.Default()
    
    // API routes
    api := r.Group("/api/v1")
    {
        api.POST("/notifications/send", s.handleSend)
        api.GET("/notifications/channels", s.handleListChannels)
        api.GET("/notifications/logs", s.handleGetLogs)
        api.GET("/notifications/providers", s.handleListProviders)
    }
    
    return r.Run(addr)
}

func (s *HTTPServer) handleSend(c *gin.Context) {
    var req domain.SendRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(400, gin.H{"error": err.Error()})
        return
    }
    
    result, err := s.service.Send(c.Request.Context(), &req)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(200, result)
}
```

---

### **8. CLI 启动 HTTP Server**

```go
// internal/cmd/serve.go

var serveCmd = &cobra.Command{
    Use:   "serve",
    Short: "Start HTTP API server",
    RunE: func(cmd *cobra.Command, args []string) error {
        port, _ := cmd.Flags().GetInt("port")
        
        // 初始化 service
        service := getNotificationService()
        
        // 启动 HTTP server
        server := api.NewHTTPServer(service)
        addr := fmt.Sprintf(":%d", port)
        
        fmt.Printf("Starting HTTP API server on %s\n", addr)
        return server.Start(addr)
    },
}

func init() {
    serveCmd.Flags().Int("port", 8080, "HTTP port")
    rootCmd.AddCommand(serveCmd)
}
```

---

## 🎯 重新设计后的优势

### **1. 真正的可扩展性**

**添加新 Provider 无需改动核心代码**:
```go
// 只需实现 Provider 接口
type TelegramProvider struct{}

func init() {
    provider.Register(&TelegramProvider{})
}

// 实现 Send/Verify/SupportedFormats
```

---

### **2. 对外应用支持**

**HTTP API**:
```bash
# 外部应用调用
curl -X POST http://localhost:8080/api/v1/notifications/send \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "trading",
    "title": "Test",
    "content": "Hello"
  }'
```

**gRPC API** (可选):
```protobuf
service NotificationService {
  rpc Send(SendRequest) returns (SendResult);
  rpc ListChannels(Empty) returns (ChannelList);
}
```

---

### **3. 多种访问方式**

```
CLI      → NotificationService
HTTP API → NotificationService
gRPC API → NotificationService
SDK      → NotificationService
```

---

## ✅ 重新实施计划

### **Phase 4: 真正的可扩展架构（2-3 天）**

**Day 1: Provider 抽象**
- [ ] 创建 Provider 接口
- [ ] 创建 Provider Registry
- [ ] 重构 Feishu 为 Provider
- [ ] 添加 Slack Provider
- [ ] 添加 Email Provider

**Day 2: HTTP API**
- [ ] 创建 HTTP Server
- [ ] 实现 API endpoints
- [ ] 添加 serve 命令
- [ ] API 文档

**Day 3: 测试和文档**
- [ ] 集成测试
- [ ] 性能测试
- [ ] 完善文档

---

**你希望我立即开始 Phase 4（真正的可扩展架构）吗？**
