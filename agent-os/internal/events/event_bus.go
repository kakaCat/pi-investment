package events

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// EventType represents the type of event
type EventType string

const (
	EventTaskCompleted    EventType = "task.completed"
	EventTaskFailed       EventType = "task.failed"
	EventTaskStarted      EventType = "task.started"
	EventDecisionRecorded EventType = "decision.recorded"
	EventDecisionUpdated  EventType = "decision.updated"
	EventMemoryCreated    EventType = "memory.created"
	EventMemoryUpdated    EventType = "memory.updated"
	EventQuotaExceeded    EventType = "quota.exceeded"
	EventQuotaWarning     EventType = "quota.warning"
)

// Event represents a system event
type Event struct {
	Type      EventType              `json:"type"`
	Data      map[string]interface{} `json:"data"`
	Timestamp time.Time              `json:"timestamp"`
	AgentID   string                 `json:"agent_id,omitempty"`
}

// EventBus manages event publishing and subscription
type EventBus struct {
	db        *pgxpool.Pool
	listeners map[string][]chan Event // event_type -> channels
	mu        sync.RWMutex
	ctx       context.Context
	cancel    context.CancelFunc
}

// NewEventBus creates a new EventBus
func NewEventBus(db *pgxpool.Pool) *EventBus {
	ctx, cancel := context.WithCancel(context.Background())
	return &EventBus{
		db:        db,
		listeners: make(map[string][]chan Event),
		ctx:       ctx,
		cancel:    cancel,
	}
}

// Publish publishes an event to all subscribers
func (eb *EventBus) Publish(ctx context.Context, event Event) error {
	// Set timestamp if not already set
	if event.Timestamp.IsZero() {
		event.Timestamp = time.Now()
	}

	// Marshal event to JSON
	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Publish via PostgreSQL NOTIFY
	_, err = eb.db.Exec(ctx, "SELECT pg_notify('agent_os_events', $1)", string(payload))
	if err != nil {
		return fmt.Errorf("failed to publish event: %w", err)
	}

	// Also broadcast to in-memory listeners
	eb.broadcast(event)

	return nil
}

// Subscribe creates a subscription to events matching the given filters
// filters can be event types (e.g., "task.*", "task.completed")
func (eb *EventBus) Subscribe(ctx context.Context, filters []string) (<-chan Event, error) {
	eventChan := make(chan Event, 100) // Buffered channel

	eb.mu.Lock()
	defer eb.mu.Unlock()

	// Register listener for each filter
	for _, filter := range filters {
		eb.listeners[filter] = append(eb.listeners[filter], eventChan)
	}

	// Start cleanup goroutine
	go func() {
		<-ctx.Done()
		eb.unsubscribe(eventChan, filters)
		close(eventChan)
	}()

	return eventChan, nil
}

// unsubscribe removes a channel from all filter lists
func (eb *EventBus) unsubscribe(ch chan Event, filters []string) {
	eb.mu.Lock()
	defer eb.mu.Unlock()

	for _, filter := range filters {
		listeners := eb.listeners[filter]
		for i, listener := range listeners {
			if listener == ch {
				// Remove from slice
				eb.listeners[filter] = append(listeners[:i], listeners[i+1:]...)
				break
			}
		}
	}
}

// broadcast sends an event to all matching listeners
func (eb *EventBus) broadcast(event Event) {
	eb.mu.RLock()
	defer eb.mu.RUnlock()

	eventType := string(event.Type)

	// Send to exact match listeners
	if channels, ok := eb.listeners[eventType]; ok {
		for _, ch := range channels {
			select {
			case ch <- event:
			default:
				// Channel full, skip
			}
		}
	}

	// Send to wildcard listeners (e.g., "task.*")
	for filter, channels := range eb.listeners {
		if matchEventFilter(filter, eventType) {
			for _, ch := range channels {
				select {
				case ch <- event:
				default:
					// Channel full, skip
				}
			}
		}
	}
}

// matchEventFilter checks if an event type matches a filter pattern
// Supports wildcards: "task.*" matches "task.completed", "task.failed", etc.
func matchEventFilter(filter, eventType string) bool {
	if filter == "*" {
		return true
	}

	if filter == eventType {
		return true
	}

	// Wildcard matching: "task.*" matches "task.completed"
	if len(filter) > 2 && filter[len(filter)-2:] == ".*" {
		prefix := filter[:len(filter)-2]
		if len(eventType) > len(prefix) && eventType[:len(prefix)] == prefix && eventType[len(prefix)] == '.' {
			return true
		}
	}

	return false
}

// Start begins listening for PostgreSQL NOTIFY events
func (eb *EventBus) Start(ctx context.Context) error {
	// Acquire a dedicated connection for LISTEN
	conn, err := eb.db.Acquire(ctx)
	if err != nil {
		return fmt.Errorf("failed to acquire connection: %w", err)
	}

	// Execute LISTEN command
	_, err = conn.Exec(ctx, "LISTEN agent_os_events")
	if err != nil {
		conn.Release()
		return fmt.Errorf("failed to execute LISTEN: %w", err)
	}

	// Start listen loop in background
	go eb.listenLoop(conn)

	return nil
}

// listenLoop continuously waits for NOTIFY events
func (eb *EventBus) listenLoop(conn *pgxpool.Conn) {
	defer conn.Release()

	for {
		select {
		case <-eb.ctx.Done():
			return
		default:
		}

		// Wait for notification (with timeout)
		notification, err := conn.Conn().WaitForNotification(eb.ctx)
		if err != nil {
			// Context cancelled or connection error
			if eb.ctx.Err() != nil {
				return
			}
			// Log error and continue
			continue
		}

		// Parse event
		var event Event
		if err := json.Unmarshal([]byte(notification.Payload), &event); err != nil {
			// Invalid event payload, skip
			continue
		}

		// Broadcast to listeners
		eb.broadcast(event)
	}
}

// Stop stops the event bus
func (eb *EventBus) Stop() {
	eb.cancel()
}
