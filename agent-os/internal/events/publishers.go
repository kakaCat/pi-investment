package events

import (
	"context"
	"log"

	"github.com/google/uuid"
)

// GlobalEventBus is the global event bus instance
var GlobalEventBus *EventBus

// InitGlobalEventBus initializes the global event bus
func InitGlobalEventBus(eb *EventBus) {
	GlobalEventBus = eb
}

// PublishTaskCompleted publishes a task.completed event
func PublishTaskCompleted(ctx context.Context, taskID uuid.UUID, taskName string, agentID string) {
	if GlobalEventBus == nil {
		return // Event bus not initialized
	}

	event := Event{
		Type:    EventTaskCompleted,
		AgentID: agentID,
		Data: map[string]interface{}{
			"task_id":   taskID.String(),
			"task_name": taskName,
			"status":    "completed",
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish task.completed event: %v", err)
	}
}

// PublishTaskFailed publishes a task.failed event
func PublishTaskFailed(ctx context.Context, taskID uuid.UUID, taskName string, agentID string, errorMsg string) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventTaskFailed,
		AgentID: agentID,
		Data: map[string]interface{}{
			"task_id":   taskID.String(),
			"task_name": taskName,
			"status":    "failed",
			"error":     errorMsg,
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish task.failed event: %v", err)
	}
}

// PublishTaskStarted publishes a task.started event
func PublishTaskStarted(ctx context.Context, taskID uuid.UUID, taskName string, agentID string) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventTaskStarted,
		AgentID: agentID,
		Data: map[string]interface{}{
			"task_id":   taskID.String(),
			"task_name": taskName,
			"status":    "started",
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish task.started event: %v", err)
	}
}

// PublishDecisionRecorded publishes a decision.recorded event
func PublishDecisionRecorded(ctx context.Context, decisionID uuid.UUID, agentID string, action string) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventDecisionRecorded,
		AgentID: agentID,
		Data: map[string]interface{}{
			"decision_id": decisionID.String(),
			"action":      action,
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish decision.recorded event: %v", err)
	}
}

// PublishDecisionUpdated publishes a decision.updated event
func PublishDecisionUpdated(ctx context.Context, decisionID uuid.UUID, agentID string, outcome string) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventDecisionUpdated,
		AgentID: agentID,
		Data: map[string]interface{}{
			"decision_id": decisionID.String(),
			"outcome":     outcome,
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish decision.updated event: %v", err)
	}
}

// PublishMemoryCreated publishes a memory.created event
func PublishMemoryCreated(ctx context.Context, memoryID uuid.UUID, agentID string, category string) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventMemoryCreated,
		AgentID: agentID,
		Data: map[string]interface{}{
			"memory_id": memoryID.String(),
			"category":  category,
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish memory.created event: %v", err)
	}
}

// PublishQuotaExceeded publishes a quota.exceeded event
func PublishQuotaExceeded(ctx context.Context, agentID string, resourceType string, limit int64) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventQuotaExceeded,
		AgentID: agentID,
		Data: map[string]interface{}{
			"resource_type": resourceType,
			"limit":         limit,
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish quota.exceeded event: %v", err)
	}
}

// PublishQuotaWarning publishes a quota.warning event
func PublishQuotaWarning(ctx context.Context, agentID string, resourceType string, usage int64, limit int64) {
	if GlobalEventBus == nil {
		return
	}

	event := Event{
		Type:    EventQuotaWarning,
		AgentID: agentID,
		Data: map[string]interface{}{
			"resource_type": resourceType,
			"usage":         usage,
			"limit":         limit,
			"percentage":    float64(usage) / float64(limit) * 100,
		},
	}

	if err := GlobalEventBus.Publish(ctx, event); err != nil {
		log.Printf("Failed to publish quota.warning event: %v", err)
	}
}
