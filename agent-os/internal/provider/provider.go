package provider

import "context"

// Message 统一消息格式
type Message struct {
	Title    string                 `json:"title"`
	Content  string                 `json:"content"`
	Format   string                 `json:"format"`   // markdown, html, plain
	Priority string                 `json:"priority"` // low, normal, high, critical
	Color    string                 `json:"color"`    // blue, green, red, orange, grey, purple
	Metadata map[string]interface{} `json:"metadata"`
}

// Result 发送结果
type Result struct {
	Success   bool   `json:"success"`
	MessageID string `json:"message_id,omitempty"`
	Error     error  `json:"-"`
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
