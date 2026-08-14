package main

import (
	"encoding/json"
	"flag"
	"log"
	"os"
	"os/signal"
	"time"

	"github.com/gorilla/websocket"
)

var addr = flag.String("addr", "localhost:8081", "WebSocket server address")
var filters = flag.String("filters", "*", "Event filters (comma-separated)")
var agentID = flag.String("agent", "", "Filter by agent ID")

func main() {
	flag.Parse()
	log.SetFlags(0)

	// Build WebSocket URL
	url := "ws://" + *addr + "/ws/events?filters=" + *filters
	if *agentID != "" {
		url += "&agent_id=" + *agentID
	}

	log.Printf("Connecting to %s", url)

	// Connect to WebSocket server
	c, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		log.Fatal("dial:", err)
	}
	defer c.Close()

	// Channel for interrupt signal
	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt)

	// Channel for incoming messages
	done := make(chan struct{})

	// Read messages from server
	go func() {
		defer close(done)
		for {
			_, message, err := c.ReadMessage()
			if err != nil {
				log.Println("read:", err)
				return
			}

			// Pretty print JSON
			var event map[string]interface{}
			if err := json.Unmarshal(message, &event); err != nil {
				log.Printf("Received: %s", message)
			} else {
				prettyJSON, _ := json.MarshalIndent(event, "", "  ")
				log.Printf("\n📨 Event received:\n%s\n", string(prettyJSON))
			}
		}
	}()

	// Wait for interrupt
	for {
		select {
		case <-done:
			return
		case <-interrupt:
			log.Println("\nInterrupted, closing connection...")

			// Send close message
			err := c.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
			if err != nil {
				log.Println("write close:", err)
				return
			}

			select {
			case <-done:
			case <-time.After(time.Second):
			}
			return
		}
	}
}
