package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/pi-investment/agent-os/internal/events"
)

var connStr = flag.String("conn", "postgres://localhost:5432/agent_os?sslmode=disable", "PostgreSQL connection string")
var eventType = flag.String("type", "task.completed", "Event type to publish")
var agentID = flag.String("agent", "test-agent", "Agent ID")
var count = flag.Int("count", 5, "Number of events to publish")
var interval = flag.Duration("interval", 2*time.Second, "Interval between events")

func main() {
	flag.Parse()

	ctx := context.Background()

	// Connect to database
	pool, err := pgxpool.New(ctx, *connStr)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer pool.Close()

	// Create event bus
	eventBus := events.NewEventBus(pool)

	log.Printf("Publishing %d events of type %s every %s", *count, *eventType, *interval)

	// Publish events
	for i := 0; i < *count; i++ {
		taskID := uuid.New()
		taskName := fmt.Sprintf("test-task-%d", i+1)

		event := events.Event{
			Type:    events.EventType(*eventType),
			AgentID: *agentID,
			Data: map[string]interface{}{
				"task_id":   taskID.String(),
				"task_name": taskName,
				"status":    "completed",
				"iteration": i + 1,
			},
		}

		if err := eventBus.Publish(ctx, event); err != nil {
			log.Printf("Failed to publish event: %v", err)
		} else {
			log.Printf("✅ Published event #%d: %s (task: %s)", i+1, *eventType, taskName)
		}

		if i < *count-1 {
			time.Sleep(*interval)
		}
	}

	log.Printf("✅ All %d events published successfully", *count)
}
