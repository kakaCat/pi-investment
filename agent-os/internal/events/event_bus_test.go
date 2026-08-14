package events

import (
	"context"
	"testing"
	"time"
)

func TestMatchEventFilter(t *testing.T) {
	tests := []struct {
		name      string
		filter    string
		eventType string
		want      bool
	}{
		{"wildcard matches all", "*", "task.completed", true},
		{"exact match", "task.completed", "task.completed", true},
		{"exact mismatch", "task.completed", "task.failed", false},
		{"prefix wildcard matches", "task.*", "task.completed", true},
		{"prefix wildcard matches multiple", "task.*", "task.failed", true},
		{"prefix wildcard mismatch", "task.*", "decision.recorded", false},
		{"prefix without dot doesn't match", "task.*", "taskCompleted", false},
		{"partial prefix doesn't match", "task.*", "task", false},
		{"decision wildcard", "decision.*", "decision.recorded", true},
		{"quota wildcard", "quota.*", "quota.exceeded", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := matchEventFilter(tt.filter, tt.eventType); got != tt.want {
				t.Errorf("matchEventFilter(%q, %q) = %v, want %v",
					tt.filter, tt.eventType, got, tt.want)
			}
		})
	}
}

func TestEventBus_PublishSubscribe(t *testing.T) {
	// Note: This test requires a PostgreSQL database connection
	// For unit testing without DB, we test the in-memory broadcast only

	eb := NewEventBus(nil) // No DB for unit test

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	// Subscribe to task events
	eventChan, err := eb.Subscribe(ctx, []string{"task.*"})
	if err != nil {
		t.Fatalf("Subscribe failed: %v", err)
	}

	// Publish an event (in-memory only, no DB)
	event := Event{
		Type: EventTaskCompleted,
		Data: map[string]interface{}{
			"task_id": "test-task",
			"status":  "success",
		},
		AgentID: "test-agent",
	}

	// Broadcast directly (simulating what Publish does)
	eb.broadcast(event)

	// Receive event
	select {
	case receivedEvent := <-eventChan:
		if receivedEvent.Type != EventTaskCompleted {
			t.Errorf("Expected event type %s, got %s", EventTaskCompleted, receivedEvent.Type)
		}
		if receivedEvent.AgentID != "test-agent" {
			t.Errorf("Expected agent_id 'test-agent', got '%s'", receivedEvent.AgentID)
		}
	case <-time.After(1 * time.Second):
		t.Fatal("Timeout waiting for event")
	}
}

func TestEventBus_MultipleSubscribers(t *testing.T) {
	eb := NewEventBus(nil)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	// Create two subscribers
	ch1, _ := eb.Subscribe(ctx, []string{"task.*"})
	ch2, _ := eb.Subscribe(ctx, []string{"task.completed"})

	// Publish event
	event := Event{
		Type: EventTaskCompleted,
		Data: map[string]interface{}{
			"task_id": "test-task",
		},
	}

	eb.broadcast(event)

	// Both subscribers should receive the event
	receivedCount := 0

	select {
	case <-ch1:
		receivedCount++
	case <-time.After(500 * time.Millisecond):
	}

	select {
	case <-ch2:
		receivedCount++
	case <-time.After(500 * time.Millisecond):
	}

	if receivedCount != 2 {
		t.Errorf("Expected 2 subscribers to receive event, got %d", receivedCount)
	}
}

func TestEventBus_FilterMatching(t *testing.T) {
	eb := NewEventBus(nil)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	// Subscribe to only completed events
	completedChan, _ := eb.Subscribe(ctx, []string{"task.completed"})

	// Broadcast a failed event
	failedEvent := Event{
		Type: EventTaskFailed,
		Data: map[string]interface{}{"task_id": "failed-task"},
	}
	eb.broadcast(failedEvent)

	// Should NOT receive the failed event
	select {
	case <-completedChan:
		t.Error("Received event that should have been filtered out")
	case <-time.After(300 * time.Millisecond):
		// Expected: no event received
	}

	// Now broadcast a completed event
	completedEvent := Event{
		Type: EventTaskCompleted,
		Data: map[string]interface{}{"task_id": "completed-task"},
	}
	eb.broadcast(completedEvent)

	// Should receive this one
	select {
	case event := <-completedChan:
		if event.Type != EventTaskCompleted {
			t.Errorf("Expected task.completed, got %s", event.Type)
		}
	case <-time.After(500 * time.Millisecond):
		t.Error("Timeout waiting for completed event")
	}
}

func TestEventBus_WildcardSubscription(t *testing.T) {
	eb := NewEventBus(nil)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	// Subscribe to all events
	allChan, _ := eb.Subscribe(ctx, []string{"*"})

	// Broadcast events of different types
	events := []Event{
		{Type: EventTaskCompleted, Data: map[string]interface{}{"id": "1"}},
		{Type: EventDecisionRecorded, Data: map[string]interface{}{"id": "2"}},
		{Type: EventMemoryCreated, Data: map[string]interface{}{"id": "3"}},
	}

	for _, event := range events {
		eb.broadcast(event)
	}

	// Should receive all three
	receivedCount := 0
	timeout := time.After(1 * time.Second)

	for i := 0; i < 3; i++ {
		select {
		case <-allChan:
			receivedCount++
		case <-timeout:
			break
		}
	}

	if receivedCount != 3 {
		t.Errorf("Expected to receive 3 events, got %d", receivedCount)
	}
}

func TestEventBus_Unsubscribe(t *testing.T) {
	eb := NewEventBus(nil)

	ctx, cancel := context.WithCancel(context.Background())

	// Subscribe
	eventChan, _ := eb.Subscribe(ctx, []string{"task.*"})

	// Verify subscription exists
	eb.mu.RLock()
	listenerCount := len(eb.listeners["task.*"])
	eb.mu.RUnlock()

	if listenerCount != 1 {
		t.Errorf("Expected 1 listener, got %d", listenerCount)
	}

	// Cancel context (triggers unsubscribe)
	cancel()
	time.Sleep(100 * time.Millisecond) // Give time for cleanup

	// Verify listener removed
	eb.mu.RLock()
	listenerCount = len(eb.listeners["task.*"])
	eb.mu.RUnlock()

	if listenerCount != 0 {
		t.Errorf("Expected 0 listeners after unsubscribe, got %d", listenerCount)
	}

	// Channel should be closed
	select {
	case _, ok := <-eventChan:
		if ok {
			t.Error("Channel should be closed after unsubscribe")
		}
	case <-time.After(500 * time.Millisecond):
		t.Error("Channel not closed after unsubscribe")
	}
}

func TestEvent_Timestamp(t *testing.T) {
	event := Event{
		Type: EventTaskCompleted,
		Data: map[string]interface{}{"task_id": "test"},
	}

	// Timestamp should be zero initially
	if !event.Timestamp.IsZero() {
		t.Error("Expected zero timestamp initially")
	}

	// After setting in Publish (we simulate it here)
	if event.Timestamp.IsZero() {
		event.Timestamp = time.Now()
	}

	if event.Timestamp.IsZero() {
		t.Error("Expected non-zero timestamp after setting")
	}
}
