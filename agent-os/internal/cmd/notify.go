package cmd

import (
	"context"
	"database/sql"
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
)

var notifyCmd = &cobra.Command{
	Use:   "notify",
	Short: "Notification management",
	Long:  "Send and manage notifications through configured channels",
}

var notifySendCmd = &cobra.Command{
	Use:   "send",
	Short: "Send a notification",
	Long:  "Send a notification to a specified channel",
	RunE: func(cmd *cobra.Command, args []string) error {
		channel, _ := cmd.Flags().GetString("channel")
		title, _ := cmd.Flags().GetString("title")
		content, _ := cmd.Flags().GetString("content")
		color, _ := cmd.Flags().GetString("color")

		// Get notification service
		svc, err := getNotificationService()
		if err != nil {
			return err
		}

		// Send notification
		result, err := svc.Send(context.Background(), &domain.SendRequest{
			Channel: channel,
			Title:   title,
			Content: content,
			Color:   color,
		})
		if err != nil {
			return fmt.Errorf("failed to send notification: %w", err)
		}

		if result.Success {
			fmt.Printf("✅ Notification sent successfully\n")
			fmt.Printf("   Log ID: %s\n", result.LogID)
			if result.MessageID != "" {
				fmt.Printf("   Message ID: %s\n", result.MessageID)
			}
		} else {
			fmt.Printf("❌ Failed to send notification\n")
			fmt.Printf("   Error: %s\n", result.Error)
			os.Exit(1)
		}

		return nil
	},
}

var notifyListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available channels",
	Long:  "List all available notification channels",
	RunE: func(cmd *cobra.Command, args []string) error {
		// Get notification service
		svc, err := getNotificationService()
		if err != nil {
			return err
		}

		// List channels
		channels, err := svc.ListChannels(context.Background())
		if err != nil {
			return fmt.Errorf("failed to list channels: %w", err)
		}

		if len(channels) == 0 {
			fmt.Println("No channels configured")
			return nil
		}

		fmt.Println("CODE       NAME       PROVIDER   STATUS")
		fmt.Println("──────────────────────────────────────────")
		for _, ch := range channels {
			status := "✅"
			if !ch.Enabled {
				status = "❌"
			}
			fmt.Printf("%-10s %-10s %-10s %s\n", ch.Code, ch.Name, ch.ProviderName, status)
		}
		fmt.Printf("\nTotal: %d channels\n", len(channels))

		return nil
	},
}

var notifyLogsCmd = &cobra.Command{
	Use:   "logs",
	Short: "View recent notification logs",
	Long:  "View recent notification sending logs",
	RunE: func(cmd *cobra.Command, args []string) error {
		limit, _ := cmd.Flags().GetInt("limit")

		// Get notification service
		svc, err := getNotificationService()
		if err != nil {
			return err
		}

		// Get logs
		logs, err := svc.GetRecentLogs(context.Background(), limit)
		if err != nil {
			return fmt.Errorf("failed to get logs: %w", err)
		}

		if len(logs) == 0 {
			fmt.Println("No logs found")
			return nil
		}

		fmt.Println("TIME                 TITLE                STATUS   CHANNEL")
		fmt.Println("────────────────────────────────────────────────────────────")
		for _, log := range logs {
			statusIcon := "⏳"
			switch log.Status {
			case "sent":
				statusIcon = "✅"
			case "failed":
				statusIcon = "❌"
			}
			fmt.Printf("%s  %-20s %-8s\n",
				log.CreatedAt.Format("2006-01-02 15:04:05"),
				truncate(log.Title, 20),
				fmt.Sprintf("%s %s", statusIcon, log.Status),
			)
			if log.Error != "" {
				fmt.Printf("   Error: %s\n", truncate(log.Error, 60))
			}
		}

		return nil
	},
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}

func getNotificationService() (*service.NotificationService, error) {
	// Get config
	cfg := config.Get()

	// Build connection string
	connStr := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.DBName,
		cfg.Database.SSLMode,
	)

	// Connect to database
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Create repository and service
	repo := repository.NewNotificationRepository(db)
	svc := service.NewNotificationService(repo)

	return svc, nil
}

func init() {
	// notify send flags
	notifySendCmd.Flags().String("channel", "", "Channel code (required)")
	notifySendCmd.Flags().String("title", "", "Notification title (required)")
	notifySendCmd.Flags().String("content", "", "Notification content (required)")
	notifySendCmd.Flags().String("color", "blue", "Card color (blue/green/red/orange/grey/purple)")
	notifySendCmd.MarkFlagRequired("channel")
	notifySendCmd.MarkFlagRequired("title")
	notifySendCmd.MarkFlagRequired("content")

	// notify logs flags
	notifyLogsCmd.Flags().Int("limit", 10, "Number of logs to show")

	// Add subcommands
	notifyCmd.AddCommand(notifySendCmd)
	notifyCmd.AddCommand(notifyListCmd)
	notifyCmd.AddCommand(notifyLogsCmd)

	// Add to root
	rootCmd.AddCommand(notifyCmd)
}
