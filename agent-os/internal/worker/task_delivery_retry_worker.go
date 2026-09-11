package worker

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/pkg/logger"
)

// TaskDeliveryRetryWorker 补投定时任务的 webhook 投递（2026-09-11 w-f4aa1f6a）。
//
// 背景：scheduler 的 webhook 投递只有内存内重试（MaxRetries=2 + 连接失败递增退避
// ≈90s 窗口）。2026-09-11 09:27-11:02 DSH 因内存压力长时间不可达（>90s），重试耗尽后
// 任务被直接丢弃（含 09-10 19:00 晚间例行），只剩一条 error_event 无人补。
//
// 本 worker 每 interval 扫一次 task_delivery_backlog 的到期行并重投：
//   - 成功（2xx）→ 标记 delivered
//   - 失败 → attempts+1，按 nextBackoff 退避（30s/1m/2m/4m/8m/16m/30m... 封顶 30m），
//     超过 max_attempts 置 failed 并打 ERROR 日志（被错误事件采集器收走→进入处置闭环）
//
// 与 notification_retry_worker 的分工：那个重投**通知**，本 worker 重投**任务投递**。
type TaskDeliveryRetryWorker struct {
	repo     *repository.TaskDeliveryBacklogRepository
	client   *http.Client
	interval time.Duration
	stopCh   chan struct{}
	doneCh   chan struct{}
}

func NewTaskDeliveryRetryWorker(repo *repository.TaskDeliveryBacklogRepository) *TaskDeliveryRetryWorker {
	return &TaskDeliveryRetryWorker{
		repo:     repo,
		client:   &http.Client{Timeout: 60 * time.Second},
		interval: 60 * time.Second,
		stopCh:   make(chan struct{}),
		doneCh:   make(chan struct{}),
	}
}

// Start 启动后台补投循环（非阻塞）。
func (w *TaskDeliveryRetryWorker) Start() error {
	ctx := context.Background()
	if n, err := w.repo.CountPending(ctx); err != nil {
		logger.Warn("Failed to count pending task deliveries at startup", "error", err)
	} else if n > 0 {
		logger.Warn("Task delivery backlog has pending entries at startup", "pending", n)
	}

	go w.loop(ctx)
	logger.Info("Task delivery retry worker started", "interval", w.interval.String())
	return nil
}

// Stop 停止循环并等待退出。
func (w *TaskDeliveryRetryWorker) Stop() {
	close(w.stopCh)
	<-w.doneCh
}

func (w *TaskDeliveryRetryWorker) loop(ctx context.Context) {
	defer close(w.doneCh)
	ticker := time.NewTicker(w.interval)
	defer ticker.Stop()

	for {
		select {
		case <-w.stopCh:
			return
		case <-ticker.C:
			if n, err := w.deliverDue(ctx); err != nil {
				logger.Error("Task delivery retry pass failed", "error", err)
			} else if n > 0 {
				logger.Info("Task delivery retry pass completed", "delivered", n)
			}
		}
	}
}

// deliverDue 处理一批到期记录，返回成功投递条数。
func (w *TaskDeliveryRetryWorker) deliverDue(ctx context.Context) (int, error) {
	entries, err := w.repo.ListDue(ctx, 20)
	if err != nil {
		return 0, err
	}

	delivered := 0
	for _, e := range entries {
		statusCode, body, postErr := w.post(ctx, e.WebhookURL, e.Payload)
		attempts := e.Attempts + 1

		if postErr == nil && statusCode >= 200 && statusCode < 300 {
			if err := w.repo.MarkDelivered(ctx, e.UUID); err != nil {
				logger.Error("Failed to mark delivery as delivered", "id", e.UUID, "error", err)
				continue
			}
			delivered++
			logger.Info("Backlog task delivery succeeded",
				"task_name", e.TaskName, "attempts", attempts, "webhook_url", e.WebhookURL)
			continue
		}

		failure := postErr
		if failure == nil {
			failure = fmt.Errorf("non-2xx status %d (body: %s)", statusCode, truncate(body, 200))
		}
		nextAt := time.Now().Add(nextBackoff(attempts))
		if err := w.repo.MarkAttemptFailed(ctx, e.UUID, attempts, nextAt, failure.Error()); err != nil {
			logger.Error("Failed to record delivery attempt failure", "id", e.UUID, "error", err)
			continue
		}

		if attempts >= e.MaxAttempts {
			// 打 ERROR 日志：错误事件采集器会收走 → 进入处置闭环（不再静默丢失）
			logger.Error("Backlog task delivery exhausted attempts",
				"task_name", e.TaskName, "attempts", attempts,
				"webhook_url", e.WebhookURL, "error", failure.Error())
		} else {
			logger.Warn("Backlog task delivery failed, will retry",
				"task_name", e.TaskName, "attempts", attempts,
				"next_attempt_at", nextAt.Format(time.RFC3339), "error", failure.Error())
		}
	}
	return delivered, nil
}

func (w *TaskDeliveryRetryWorker) post(ctx context.Context, url string, payload []byte) (int, string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(payload))
	if err != nil {
		return 0, "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "Agent-OS-DeliveryRetry/1.0")

	resp, err := w.client.Do(req)
	if err != nil {
		return 0, "", err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(body), nil
}

// nextBackoff 指数退避：30s, 1m, 2m, 4m, 8m, 16m, 30m(封顶)。
func nextBackoff(attempts int) time.Duration {
	if attempts < 1 {
		attempts = 1
	}
	d := 30 * time.Second * time.Duration(1<<(attempts-1))
	if d > 30*time.Minute || d <= 0 {
		d = 30 * time.Minute
	}
	return d
}
