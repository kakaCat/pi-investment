package cmd

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/spf13/cobra"
	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
)

var (
	// Flags for notify send
	notifyChannel string
	notifyTitle   string
	notifyContent string
	notifyColor   string
	notifyUrgency string

	// Flags for notify logs
	notifyLogsLimit int

	// Flags for output format
	notifyOutputJSON bool

	// API URL
	agentOsAPIURL string
)

var notifyCmd = &cobra.Command{
	Use:   "notify",
	Short: "Notification management",
	Long:  "Manage notifications through Agent OS notification system",
}

var notifySendCmd = &cobra.Command{
	Use:   "send",
	Short: "Send a notification",
	Long:  "Send a notification to a specified channel (trading, alerts, reports)",
	RunE: func(cmd *cobra.Command, args []string) error {
		// Build request
		req := map[string]interface{}{
			"channel": notifyChannel,
			"title":   notifyTitle,
			"content": notifyContent,
		}
		if notifyColor != "" {
			req["color"] = notifyColor
		}
		if notifyUrgency != "" {
			req["urgency"] = notifyUrgency
		}

		// Try HTTP API first
		apiURL := getAPIURL()
		if apiURL != "" {
			result, err := sendViaAPI(apiURL, req)
			if err == nil {
				if result["success"].(bool) {
					fmt.Println("✅ Notification sent successfully")
					if logID, ok := result["log_id"].(string); ok {
						fmt.Printf("   Log ID: %s\n", logID)
					}
				} else {
					fmt.Println("❌ Failed to send notification")
					if errMsg, ok := result["error"].(string); ok {
						fmt.Printf("   Error: %s\n", errMsg)
					}
				}
				return nil
			}
			// API failed, fall back to direct service call
			fmt.Fprintf(os.Stderr, "⚠️  API unavailable (%v), using direct service call\n", err)
		}

		// Fallback: direct service call
		return sendViaService(req)
	},
}

var notifyListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available channels",
	Long:  "List all available notification channels",
	RunE: func(cmd *cobra.Command, args []string) error {
		// Try HTTP API first
		apiURL := getAPIURL()
		if apiURL != "" {
			channels, err := listChannelsViaAPI(apiURL)
			if err == nil {
				displayChannels(channels)
				return nil
			}
			fmt.Fprintf(os.Stderr, "⚠️  API unavailable (%v), using direct service call\n", err)
		}

		// Fallback: direct service call
		return listChannelsViaService()
	},
}

var notifyLogsCmd = &cobra.Command{
	Use:   "logs",
	Short: "View notification logs",
	Long:  "View recent notification logs",
	RunE: func(cmd *cobra.Command, args []string) error {
		// Try HTTP API first
		apiURL := getAPIURL()
		if apiURL != "" {
			logs, err := getLogsViaAPI(apiURL, notifyLogsLimit)
			if err == nil {
				displayLogs(logs)
				return nil
			}
			fmt.Fprintf(os.Stderr, "⚠️  API unavailable (%v), using direct service call\n", err)
		}

		// Fallback: direct service call
		return getLogsViaService(notifyLogsLimit)
	},
}

func init() {
	// Send flags
	notifySendCmd.Flags().StringVar(&notifyChannel, "channel", "", "Channel code (trading, alerts, reports)")
	notifySendCmd.Flags().StringVar(&notifyTitle, "title", "", "Notification title")
	notifySendCmd.Flags().StringVar(&notifyContent, "content", "", "Notification content (Markdown)")
	notifySendCmd.Flags().StringVar(&notifyColor, "color", "blue", "Card color (blue, green, red, orange, grey, purple)")
	notifySendCmd.Flags().StringVar(&notifyUrgency, "urgency", "normal", "Urgency level (low, normal, high, critical)")
	notifySendCmd.MarkFlagRequired("channel")
	notifySendCmd.MarkFlagRequired("title")
	notifySendCmd.MarkFlagRequired("content")

	// List flags
	notifyListCmd.Flags().BoolVar(&notifyOutputJSON, "json", false, "Output as JSON")

	// Logs flags
	notifyLogsCmd.Flags().IntVar(&notifyLogsLimit, "limit", 10, "Number of logs to retrieve")
	notifyLogsCmd.Flags().BoolVar(&notifyOutputJSON, "json", false, "Output as JSON")

	// Add subcommands
	notifyCmd.AddCommand(notifySendCmd)
	notifyCmd.AddCommand(notifyListCmd)
	notifyCmd.AddCommand(notifyLogsCmd)

	rootCmd.AddCommand(notifyCmd)
}

// getAPIURL returns the Agent OS API URL from environment or empty if not set
func getAPIURL() string {
	return os.Getenv("AGENT_OS_API_URL")
}

// sendViaAPI sends notification via HTTP API
func sendViaAPI(apiURL string, req map[string]interface{}) (map[string]interface{}, error) {
	body, _ := json.Marshal(req)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Post(apiURL+"/api/v1/notifications/send", "application/json", bytes.NewBuffer(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	return result, nil
}

// listChannelsViaAPI lists channels via HTTP API
func listChannelsViaAPI(apiURL string) ([]map[string]interface{}, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(apiURL + "/api/v1/notifications/channels")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	var channels []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&channels); err != nil {
		return nil, err
	}

	return channels, nil
}

// getLogsViaAPI gets logs via HTTP API
func getLogsViaAPI(apiURL string, limit int) ([]map[string]interface{}, error) {
	client := &http.Client{Timeout: 10 * time.Second}
	url := fmt.Sprintf("%s/api/v1/notifications/logs?limit=%d", apiURL, limit)
	resp, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	var logs []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&logs); err != nil {
		return nil, err
	}

	return logs, nil
}

// sendViaService sends notification via direct service call (fallback)
func sendViaService(req map[string]interface{}) error {
	svc, err := getNotificationService()
	if err != nil {
		return err
	}

	sendReq := &domain.SendRequest{
		Channel: req["channel"].(string),
		Title:   req["title"].(string),
		Content: req["content"].(string),
	}
	if color, ok := req["color"].(string); ok {
		sendReq.Color = color
	}
	if urgency, ok := req["urgency"].(string); ok {
		sendReq.Urgency = urgency
	}

	result, err := svc.Send(context.Background(), sendReq)
	if err != nil {
		return err
	}

	if result.Success {
		fmt.Println("✅ Notification sent successfully")
		fmt.Printf("   Log ID: %s\n", result.LogID)
	} else {
		fmt.Println("❌ Failed to send notification")
		fmt.Printf("   Error: %s\n", result.Error)
	}

	return nil
}

// listChannelsViaService lists channels via direct service call (fallback)
func listChannelsViaService() error {
	svc, err := getNotificationService()
	if err != nil {
		return err
	}

	channels, err := svc.ListChannels(context.Background())
	if err != nil {
		return err
	}

	// Convert to map format
	channelMaps := make([]map[string]interface{}, len(channels))
	for i, ch := range channels {
		channelMaps[i] = map[string]interface{}{
			"code":          ch.Code,
			"name":          ch.Name,
			"provider_code": ch.ProviderCode,
			"enabled":       ch.Enabled,
		}
	}

	displayChannels(channelMaps)
	return nil
}

// getLogsViaService gets logs via direct service call (fallback)
func getLogsViaService(limit int) error {
	svc, err := getNotificationService()
	if err != nil {
		return err
	}

	logs, err := svc.GetRecentLogs(context.Background(), limit)
	if err != nil {
		return err
	}

	// Convert to map format
	logMaps := make([]map[string]interface{}, len(logs))
	for i, log := range logs {
		logMaps[i] = map[string]interface{}{
			"created_at": log.CreatedAt.Format("2006-01-02 15:04:05"),
			"title":      log.Title,
			"status":     log.Status,
			"error":      log.Error,
		}
	}

	displayLogs(logMaps)
	return nil
}

// displayChannels displays channels in table format
func displayChannels(channels []map[string]interface{}) {
	if notifyOutputJSON {
		json.NewEncoder(os.Stdout).Encode(channels)
		return
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 3, ' ', 0)
	fmt.Fprintln(w, "CODE\tNAME\tPROVIDER\tSTATUS")
	fmt.Fprintln(w, strings.Repeat("─", 40))

	for _, ch := range channels {
		code := ch["code"].(string)
		name := ch["name"].(string)
		provider := ch["provider_code"].(string)
		enabled := ch["enabled"].(bool)
		status := "✅"
		if !enabled {
			status = "❌"
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", code, name, provider, status)
	}

	w.Flush()
	fmt.Printf("\nTotal: %d channels\n", len(channels))
}

// displayLogs displays logs in table format
func displayLogs(logs []map[string]interface{}) {
	if notifyOutputJSON {
		json.NewEncoder(os.Stdout).Encode(logs)
		return
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 3, ' ', 0)
	fmt.Fprintln(w, "TIME\tTITLE\tSTATUS\tCHANNEL")
	fmt.Fprintln(w, strings.Repeat("─", 60))

	for _, log := range logs {
		time := log["created_at"].(string)
		title := log["title"].(string)
		if len(title) > 20 {
			title = title[:17] + "..."
		}
		status := log["status"].(string)
		statusIcon := "✅ sent"
		if status == "failed" {
			statusIcon = "❌ failed"
		} else if status == "pending" {
			statusIcon = "⏳ pending"
		}

		fmt.Fprintf(w, "%s\t%s\t%s\t\n", time, title, statusIcon)
		if status == "failed" {
			if errMsg, ok := log["error"].(string); ok && errMsg != "" {
				if len(errMsg) > 60 {
					errMsg = errMsg[:57] + "..."
				}
				fmt.Fprintf(w, "\t   Error: %s\n", errMsg)
			}
		}
	}

	w.Flush()
}

// getNotificationService creates notification service (fallback)
func getNotificationService() (*service.NotificationService, error) {
	cfg := config.Get()
	connStr := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.DBName,
		cfg.Database.SSLMode,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	repo := repository.NewNotificationRepository(db)
	svc := service.NewNotificationService(repo)

	return svc, nil
}
