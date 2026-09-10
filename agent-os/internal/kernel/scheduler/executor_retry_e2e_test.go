package scheduler

import (
	"context"
	"net"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/pkg/types"
)

// End-to-end check of the production failure path: a webhook task pointing at a
// port nothing listens on must be classified as a connection failure, so the
// executor applies the escalating backoff instead of burning both retries in 10s.
func TestExecuteWebhook_RefusedPortIsConnectionFailure(t *testing.T) {
	// Bind then immediately close: the address is guaranteed free but real.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	addr := ln.Addr().String()
	if err := ln.Close(); err != nil {
		t.Fatalf("close listener: %v", err)
	}

	e := &Executor{config: &types.SchedulerConfig{
		MaxConcurrentTasks: 1,
		DefaultTimeout:     3 * time.Second,
		MaxRetries:         2,
		RetryDelay:         5 * time.Second,
	}}
	task := &types.Task{
		ID:         uuid.New(),
		Name:       "connection-refused-probe",
		WebhookURL: "http://" + addr + "/agent-os-trigger",
	}
	run := &types.TaskRun{TaskID: task.ID, TriggeredBy: types.TriggerSourceManual}

	_, err = e.executeWebhook(context.Background(), task, run)
	if err == nil {
		t.Fatal("expected webhook against a closed port to fail")
	}
	if !IsConnectionFailure(err) {
		t.Fatalf("refused connection not classified as connection failure: %v", err)
	}
	if got := RetryDelayFor(1, err, e.config.RetryDelay); got != 30*time.Second {
		t.Fatalf("retry delay after refused connection = %v, want 30s", got)
	}
	if got := RetryDelayFor(2, err, e.config.RetryDelay); got != 60*time.Second {
		t.Fatalf("second retry delay after refused connection = %v, want 60s", got)
	}
}
