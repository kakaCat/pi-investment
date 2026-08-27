package events

import (
	"context"
	"encoding/json"
	"github.com/pi-investment/agent-os/internal/logger"
	"net/http"
	"strings"
	"time"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		// Allow all origins for now (restrict in production)
		return true
	},
}

// WebSocketServer manages WebSocket connections for event streaming
type WebSocketServer struct {
	eventBus *EventBus
	addr     string
}

// NewWebSocketServer creates a new WebSocket server
func NewWebSocketServer(eventBus *EventBus, addr string) *WebSocketServer {
	return &WebSocketServer{
		eventBus: eventBus,
		addr:     addr,
	}
}

// Start starts the WebSocket server
func (wss *WebSocketServer) Start() error {
	http.HandleFunc("/ws/events", wss.handleWebSocket)

	logger.L().Info("WebSocket server listening", logger.String("addr", wss.addr))
	return http.ListenAndServe(wss.addr, nil)
}

// handleWebSocket handles a WebSocket connection
func (wss *WebSocketServer) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	// Upgrade HTTP connection to WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		logger.L().Error("WebSocket upgrade failed", logger.Error(err))
		return
	}
	defer conn.Close()

	// Parse query parameters
	agentID := r.URL.Query().Get("agent_id")
	filtersParam := r.URL.Query().Get("filters")

	var filters []string
	if filtersParam != "" {
		filters = strings.Split(filtersParam, ",")
	} else {
		filters = []string{"*"} // Default: subscribe to all events
	}

	// Subscribe to events
	ctx, cancel := context.WithCancel(r.Context())
	defer cancel()

	eventChan, err := wss.eventBus.Subscribe(ctx, filters)
	if err != nil {
		logger.L().Error("Failed to subscribe", logger.Error(err))
		return
	}

	// Set up ping/pong to keep connection alive
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	// Send initial connection success message
	welcomeMsg := map[string]interface{}{
		"type":    "connected",
		"message": "WebSocket connection established",
		"filters": filters,
	}
	if err := conn.WriteJSON(welcomeMsg); err != nil {
		logger.L().Warn("Failed to send welcome message", logger.Error(err))
		return
	}

	// Start goroutine to read from client (to detect disconnect)
	done := make(chan struct{})
	go func() {
		defer close(done)
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				return
			}
		}
	}()

	// Forward events to WebSocket client
	for {
		select {
		case event, ok := <-eventChan:
			if !ok {
				// Channel closed
				return
			}

			// Filter by agent_id if specified
			if agentID != "" && event.AgentID != agentID {
				continue
			}

			// Send event to client
			conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := conn.WriteJSON(event); err != nil {
				logger.L().Warn("Failed to write event", logger.Error(err))
				return
			}

		case <-ticker.C:
			// Send ping to keep connection alive
			conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				logger.L().Warn("Failed to send ping", logger.Error(err))
				return
			}

		case <-done:
			// Client disconnected
			logger.L().Info("Client disconnected")
			return

		case <-ctx.Done():
			// Context cancelled
			return
		}
	}
}

// HandleHTTPSubscribe handles HTTP long-polling subscription (alternative to WebSocket)
func (wss *WebSocketServer) HandleHTTPSubscribe(w http.ResponseWriter, r *http.Request) {
	// Parse query parameters
	agentID := r.URL.Query().Get("agent_id")
	filtersParam := r.URL.Query().Get("filters")
	timeoutParam := r.URL.Query().Get("timeout")

	var filters []string
	if filtersParam != "" {
		filters = strings.Split(filtersParam, ",")
	} else {
		filters = []string{"*"}
	}

	timeout := 30 * time.Second
	if timeoutParam != "" {
		if d, err := time.ParseDuration(timeoutParam); err == nil {
			timeout = d
		}
	}

	// Subscribe to events
	ctx, cancel := context.WithTimeout(r.Context(), timeout)
	defer cancel()

	eventChan, err := wss.eventBus.Subscribe(ctx, filters)
	if err != nil {
		http.Error(w, "Failed to subscribe", http.StatusInternalServerError)
		return
	}

	// Wait for first event or timeout
	select {
	case event, ok := <-eventChan:
		if !ok {
			http.Error(w, "Subscription closed", http.StatusInternalServerError)
			return
		}

		// Filter by agent_id if specified
		if agentID != "" && event.AgentID != agentID {
			// No matching event, return empty
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte("{}"))
			return
		}

		// Return event as JSON
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(event)

	case <-ctx.Done():
		// Timeout
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte("{}"))
	}
}
