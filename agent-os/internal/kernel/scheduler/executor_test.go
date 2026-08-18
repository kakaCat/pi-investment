package scheduler

import (
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/pkg/types"
)

// The webhook payload must satisfy the contract expected by webhook receivers
// such as quantsys-v2 /internal/scheduler/webhook (WP-15):
//
//	{
//	  "job_id":       "<task uuid>",
//	  "job_name":     "<task name>",
//	  "trigger_time": "<RFC3339 timestamp>",
//	  "metadata":     { ...task payload..., "run_id": ..., "owner": ..., "triggered_by": ... }
//	}
func TestBuildWebhookPayload_MatchesReceiverContract(t *testing.T) {
	taskID := uuid.New()
	runID := uuid.New()
	task := &types.Task{
		ID:    taskID,
		Name:  "kline_update",
		Owner: "quantsys-v2",
		Payload: map[string]interface{}{
			"job_type":    "kline_update",
			"description": "Update daily K-line data",
		},
	}
	run := &types.TaskRun{
		ID:          runID,
		TaskID:      taskID,
		TriggeredBy: types.TriggerSourceScheduler,
	}

	payload := buildWebhookPayload(task, run)

	// Required top-level fields (receiver marks all four as required)
	if payload["job_id"] != taskID.String() {
		t.Errorf("job_id = %v, want %v", payload["job_id"], taskID.String())
	}
	if payload["job_name"] != "kline_update" {
		t.Errorf("job_name = %v, want kline_update", payload["job_name"])
	}
	triggerTime, ok := payload["trigger_time"].(string)
	if !ok || triggerTime == "" {
		t.Fatalf("trigger_time missing or not a string: %v", payload["trigger_time"])
	}
	if _, err := time.Parse(time.RFC3339, triggerTime); err != nil {
		t.Errorf("trigger_time %q not RFC3339: %v", triggerTime, err)
	}

	// metadata must carry the task payload (receiver dispatches on metadata.job_type)
	metadata, ok := payload["metadata"].(map[string]interface{})
	if !ok {
		t.Fatalf("metadata missing or not an object: %v", payload["metadata"])
	}
	if metadata["job_type"] != "kline_update" {
		t.Errorf("metadata.job_type = %v, want kline_update", metadata["job_type"])
	}
	if metadata["description"] != "Update daily K-line data" {
		t.Errorf("metadata.description = %v", metadata["description"])
	}

	// Run context travels inside metadata, not at top level
	if metadata["run_id"] != runID.String() {
		t.Errorf("metadata.run_id = %v, want %v", metadata["run_id"], runID.String())
	}
	if metadata["owner"] != "quantsys-v2" {
		t.Errorf("metadata.owner = %v, want quantsys-v2", metadata["owner"])
	}
	if metadata["triggered_by"] != string(types.TriggerSourceScheduler) {
		t.Errorf("metadata.triggered_by = %v, want scheduler", metadata["triggered_by"])
	}
}

func TestBuildWebhookPayload_NilTaskPayload(t *testing.T) {
	task := &types.Task{ID: uuid.New(), Name: "ping", Owner: "fin-agent"}
	run := &types.TaskRun{ID: uuid.New(), TaskID: task.ID, TriggeredBy: types.TriggerSourceManual}

	payload := buildWebhookPayload(task, run)

	metadata, ok := payload["metadata"].(map[string]interface{})
	if !ok {
		t.Fatalf("metadata must be present even without task payload: %v", payload["metadata"])
	}
	if metadata["run_id"] != run.ID.String() {
		t.Errorf("metadata.run_id = %v, want %v", metadata["run_id"], run.ID.String())
	}
}
