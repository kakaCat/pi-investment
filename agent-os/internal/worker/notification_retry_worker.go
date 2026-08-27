package worker

import (
	"context"
	"fmt"
	"github.com/pi-investment/agent-os/internal/logger"
	"time"

	"github.com/pi-investment/agent-os/internal/provider"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
	"github.com/robfig/cron/v3"
)

// NotificationRetryWorker 通知重试 worker
// 功能：定期扫描 pending 状态的通知，重新尝试投递
type NotificationRetryWorker struct {
	repo    *repository.NotificationRepository
	service *service.NotificationService
	cron          *cron.Cron
	lastAlertTime *time.Time
}

// NewNotificationRetryWorker 创建重试 worker
func NewNotificationRetryWorker(
	repo *repository.NotificationRepository,
	service *service.NotificationService,
) *NotificationRetryWorker {
	return &NotificationRetryWorker{
		repo:    repo,
		service: service,
		cron:    cron.New(),
	}
}

// Start 启动 worker（每分钟执行一次）
func (w *NotificationRetryWorker) Start() error {
	// 每分钟检查一次 pending 通知
	_, err := w.cron.AddFunc("@every 1m", func() {
		ctx := context.Background()
		if err := w.retryPendingNotifications(ctx); err != nil {
			logger.L().Error("Failed to retry pending notifications", logger.Error(err))
		}
	})
	if err != nil {
		return fmt.Errorf("failed to schedule retry job: %w", err)
	}

	w.cron.Start()
	logger.L().Info("Notification retry worker started (runs every 1 minute)")
	return nil
}

// Stop 停止 worker
func (w *NotificationRetryWorker) Stop() {
	w.cron.Stop()
	logger.L().Info("Notification retry worker stopped")
}

// retryPendingNotifications 重试所有符合条件的 pending 通知
func (w *NotificationRetryWorker) retryPendingNotifications(ctx context.Context) error {
	// 1. 查询 pending 超过 5 分钟且重试次数 < 3 的通知
	logs, err := w.repo.GetStuckPendingLogs(ctx, 5*time.Minute, 3)
	if err != nil {
		return fmt.Errorf("failed to get stuck pending logs: %w", err)
	}

	if len(logs) == 0 {
		return nil // 没有需要重试的通知
	}

	logger.L().Info("Found stuck pending notifications", logger.Int("count", len(logs)))

	// 🔔 P2-7: pending 积压告警（超过 10 条触发高优告警）
	if len(logs) >= 10 {
		w.sendBacklogAlert(ctx, len(logs))
	}

	// 2. 逐个重试
	successCount := 0
	failedCount := 0
	expiredCount := 0

	for _, notifLog := range logs {
		retryCount := notifLog.RetryCount
		if retryCount >= 3 {
			// 重试次数已达上限，标记为永久失败
			w.repo.UpdateLog(ctx, notifLog.ID, "failed_permanent", "", 
				fmt.Sprintf("Retry exhausted after %d attempts", retryCount), nil)
			expiredCount++
			continue
		}

		// 获取 channel 配置
		repoChannel, err := w.repo.GetChannelByID(ctx, notifLog.ChannelID)
		if err != nil {
			logger.L().Error("Failed to get channel", logger.String("log_id", notifLog.ID), logger.Error(err))
			failedCount++
			continue
		}

		// 转换为本地类型
		channel := &NotificationChannel{
			ID:           repoChannel.ID,
			ProviderCode: repoChannel.ProviderCode,
			Config:       repoChannel.Config,
		}
		localLog := &NotificationLog{
			ID:         notifLog.ID,
			ChannelID:  notifLog.ChannelID,
			Title:      notifLog.Title,
			Content:    notifLog.Content,
			Status:     notifLog.Status,
			RetryCount: notifLog.RetryCount,
			Metadata:   notifLog.Metadata,
		}

		// 重新调用 provider 投递
		result, err := w.retryDelivery(ctx, channel, localLog)
		
		// 更新重试次数（无论成功失败都计数）
		newRetryCount := retryCount + 1
		
		if err != nil || (result != nil && !result.Success) {
			// 投递仍然失败
			errorMsg := "Unknown error"
			if err != nil {
				errorMsg = err.Error()
			} else if result.Error != nil {
				errorMsg = result.Error.Error()
			}
			
			// 更新重试次数和错误信息，状态保持 pending（等待下次重试）
			w.repo.UpdateLogRetry(ctx, notifLog.ID, newRetryCount, errorMsg)
			failedCount++
			
			logger.L().Warn("Notification retry failed", logger.String("log_id", notifLog.ID), logger.Int("retry_count", newRetryCount), logger.String("error", errorMsg))
		} else {
			// 投递成功
			now := time.Now()
			// 先更新 retry_count
			w.repo.UpdateLogRetry(ctx, notifLog.ID, newRetryCount, "")
			w.repo.UpdateLog(ctx, notifLog.ID, "sent", result.MessageID, "", &now)
			successCount++
			
			logger.L().Info("Notification retry succeeded", logger.String("log_id", notifLog.ID), logger.Int("retry_count", newRetryCount))
		}
	}

	logger.L().Info("Retry batch completed", logger.Int("total", len(logs)), logger.Int("success", successCount), logger.Int("failed", failedCount), logger.Int("expired", expiredCount))

	return nil
}

// retryDelivery 重新投递单条通知（直接调用 provider）
func (w *NotificationRetryWorker) retryDelivery(
	ctx context.Context,
	channel *NotificationChannel,
	notifLog *NotificationLog,
) (*DeliveryResult, error) {
	// 1. 从 registry 获取 provider
	providerImpl, err := provider.Get(channel.ProviderCode)
	if err != nil {
		return nil, fmt.Errorf("failed to get provider %s: %w", channel.ProviderCode, err)
	}

	// 2. 构造消息
	msg := &provider.Message{
		Title:   notifLog.Title,
		Content: notifLog.Content,
	}

	// 从 metadata 提取可选字段
	if color, ok := notifLog.Metadata["color"].(string); ok {
		msg.Color = color
	}
	if urgency, ok := notifLog.Metadata["urgency"].(string); ok {
		msg.Priority = urgency
	}

	// 3. 调用 provider 投递（带超时 context）
	deliveryCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()

	result, err := providerImpl.Send(deliveryCtx, channel.Config, msg)
	if err != nil {
		return &DeliveryResult{
			Success: false,
			Error:   err,
		}, nil
	}

	return &DeliveryResult{
		Success:   result.Success,
		MessageID: result.MessageID,
		Error:     result.Error,
	}, nil
}

// NotificationChannel 本地类型（避免循环依赖）
type NotificationChannel struct {
	ID           string
	ProviderCode string
	Config       map[string]interface{}
}

// NotificationLog 本地类型
type NotificationLog struct {
	ID         string
	ChannelID  string
	Title      string
	Content    string
	Status     string
	RetryCount int
	Metadata   map[string]interface{}
}

// DeliveryResult 投递结果
type DeliveryResult struct {
	Success   bool
	MessageID string
	Error     error
}

// sendBacklogAlert 发送 pending 积压告警（高优）
func (w *NotificationRetryWorker) sendBacklogAlert(ctx context.Context, count int) {
	// 避免告警风暴：每小时最多告警一次
	now := time.Now()
	if w.lastAlertTime != nil && now.Sub(*w.lastAlertTime) < time.Hour {
		return
	}

	// 构造告警消息
	alertCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// 直接调用 provider 发送告警（避免递归：通过 service.Send 会创建新 log）
	channel, err := w.repo.GetChannelByCode(alertCtx, "alerts")
	if err != nil {
		logger.L().Error("Failed to get alerts channel for backlog alert", logger.Error(err))
		return
	}

	providerImpl, err := provider.Get(channel.ProviderCode)
	if err != nil {
		logger.L().Error("Failed to get provider for backlog alert", logger.Error(err))
		return
	}

	msg := &provider.Message{
		Title:    "【高优】通知系统积压告警",
		Content:  fmt.Sprintf("当前有 %d 条通知卡在 pending 状态超过 5 分钟，正在自动重试。\n\n**可能原因**：\n1. 飞书 webhook 响应慢/超时\n2. 数据库连接不稳定\n3. Agent OS 重启期间的通知\n\n**已触发**：重试 worker 自动处理中（每条最多重试 3 次）", count),
		Priority: "high",
		Color:    "red",
	}

	result, err := providerImpl.Send(alertCtx, channel.Config, msg)
	if err != nil || (result != nil && !result.Success) {
		logger.L().Error("Failed to send backlog alert", logger.Error(err))
		return
	}

	// 记录告警时间
	w.lastAlertTime = &now
	logger.L().Info("Backlog alert sent successfully", logger.Int("count", count))
}
