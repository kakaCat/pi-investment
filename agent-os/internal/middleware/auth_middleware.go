package middleware

import (
	"fmt"
	"os"
	"strings"

	"github.com/pi-investment/agent-os/internal/auth"
	"github.com/spf13/cobra"
)

var authManager *auth.AuthManager

// InitAuth initializes the authentication manager
func InitAuth(configPath string) error {
	var err error
	authManager, err = auth.NewAuthManager(configPath)
	if err != nil {
		return fmt.Errorf("failed to initialize auth: %w", err)
	}
	return nil
}

// AuthMiddleware is a Cobra PreRunE middleware that checks permissions
func AuthMiddleware(cmd *cobra.Command, args []string) error {
	// Skip auth check if not initialized (e.g., version, help commands)
	if authManager == nil {
		return nil
	}

	// Get agent ID from environment variable
	agentID := os.Getenv("AGENT_ID")
	if agentID == "" {
		// Default to admin for CLI usage without AGENT_ID
		agentID = "system-admin"
	}

	// Build command path (e.g., "scheduler:list")
	commandPath := getCommandPath(cmd)

	// Check permission
	return authManager.CheckPermission(agentID, commandPath)
}

// getCommandPath builds a command path from Cobra command tree
// Example: "scheduler list" -> "scheduler:list"
func getCommandPath(cmd *cobra.Command) string {
	parts := []string{}

	// Walk up the command tree to build the path
	current := cmd
	for current != nil && current.Use != "" {
		// Extract command name (before any spaces in Use string)
		cmdName := strings.Split(current.Use, " ")[0]

		// Skip root command (usually "agent-os")
		if current.Parent() != nil {
			parts = append([]string{cmdName}, parts...)
		}

		current = current.Parent()
	}

	// Join with ":"
	return strings.Join(parts, ":")
}

// GetAuthManager returns the initialized auth manager (for testing)
func GetAuthManager() *auth.AuthManager {
	return authManager
}
