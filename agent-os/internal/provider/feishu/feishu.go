package feishu

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/pi-investment/agent-os/internal/provider"
)

// FeishuProvider 飞书提供商
type FeishuProvider struct {
	client *http.Client
}

func init() {
	// 自动注册
	provider.Register(&FeishuProvider{
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	})
}

func (p *FeishuProvider) Name() string {
	return "feishu"
}

func (p *FeishuProvider) Send(ctx context.Context, config map[string]interface{}, msg *provider.Message) (*provider.Result, error) {
	webhook, ok := config["webhook"].(string)
	if !ok || webhook == "" {
		return nil, fmt.Errorf("webhook URL not configured")
	}

	// 构建飞书卡片
	card := p.buildCard(msg)

	// 序列化
	body, err := json.Marshal(card)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal card: %w", err)
	}

	// 发送请求
	req, err := http.NewRequestWithContext(ctx, "POST", webhook, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// 解析响应
	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// 检查结果
	code, _ := result["code"].(float64)
	if code != 0 {
		msg, _ := result["msg"].(string)
		return &provider.Result{
			Success: false,
			Error:   fmt.Errorf("feishu error (code=%v): %s", code, msg),
		}, nil
	}

	// 提取 message ID
	var messageID string
	if data, ok := result["data"].(map[string]interface{}); ok {
		if msgID, ok := data["message_id"].(string); ok {
			messageID = msgID
		}
	}

	return &provider.Result{
		Success:   true,
		MessageID: messageID,
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

// buildCard 构建飞书卡片
func (p *FeishuProvider) buildCard(msg *provider.Message) map[string]interface{} {
	// 颜色映射
	colorMap := map[string]string{
		"blue":   "blue",
		"green":  "green",
		"red":    "red",
		"orange": "orange",
		"grey":   "grey",
		"purple": "purple",
	}
	color := colorMap[msg.Color]
	if color == "" {
		color = "blue"
	}

	return map[string]interface{}{
		"msg_type": "interactive",
		"card": map[string]interface{}{
			"header": map[string]interface{}{
				"title": map[string]interface{}{
					"tag":     "plain_text",
					"content": msg.Title,
				},
				"template": color,
			},
			"elements": []map[string]interface{}{
				{
					"tag": "div",
					"text": map[string]interface{}{
						"tag":     "lark_md",
						"content": msg.Content,
					},
				},
			},
		},
	}
}
