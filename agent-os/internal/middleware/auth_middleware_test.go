package middleware

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/spf13/cobra"
)

func createTestConfig(t *testing.T) string {
	t.Helper()

	content := `
roles:
  admin:
    permissions:
      - "*"

  trading:
    permissions:
      - "scheduler:*"
      - "trading:*"

  memory:
    permissions:
      - "memory:*"

agents:
  fin-agent:
    role: trading

  memory-agent:
    role: memory

  system-admin:
    role: admin
`

	tmpDir := t.TempDir()
	configPath := filepath.Join(tmpDir, "permissions.yaml")
	if err := os.WriteFile(configPath, []byte(content), 0644); err != nil {
		t.Fatalf("Failed to create test config: %v", err)
	}

	return configPath
}

func TestInitAuth(t *testing.T) {
	configPath := createTestConfig(t)

	err := InitAuth(configPath)
	if err != nil {
		t.Fatalf("InitAuth() failed: %v", err)
	}

	if authManager == nil {
		t.Fatal("authManager is nil after InitAuth")
	}
}

func TestInitAuth_InvalidPath(t *testing.T) {
	err := InitAuth("/nonexistent/path.yaml")
	if err == nil {
		t.Fatal("Expected error for invalid path, got nil")
	}
}

func TestGetCommandPath(t *testing.T) {
	tests := []struct {
		name     string
		buildCmd func() *cobra.Command
		want     string
	}{
		{
			name: "single level command",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				scheduler := &cobra.Command{Use: "scheduler"}
				root.AddCommand(scheduler)
				return scheduler
			},
			want: "scheduler",
		},
		{
			name: "two level command",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				scheduler := &cobra.Command{Use: "scheduler"}
				list := &cobra.Command{Use: "list"}
				root.AddCommand(scheduler)
				scheduler.AddCommand(list)
				return list
			},
			want: "scheduler:list",
		},
		{
			name: "three level command",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				resource := &cobra.Command{Use: "resource"}
				quota := &cobra.Command{Use: "quota"}
				get := &cobra.Command{Use: "get"}
				root.AddCommand(resource)
				resource.AddCommand(quota)
				quota.AddCommand(get)
				return get
			},
			want: "resource:quota:get",
		},
		{
			name: "command with args in Use",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				scheduler := &cobra.Command{Use: "scheduler"}
				trigger := &cobra.Command{Use: "trigger [task-id]"}
				root.AddCommand(scheduler)
				scheduler.AddCommand(trigger)
				return trigger
			},
			want: "scheduler:trigger",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cmd := tt.buildCmd()
			got := getCommandPath(cmd)
			if got != tt.want {
				t.Errorf("getCommandPath() = %q, want %q", got, tt.want)
			}
		})
	}
}

func TestAuthMiddleware_NoAuthManager(t *testing.T) {
	// Reset authManager
	authManager = nil

	cmd := &cobra.Command{Use: "test"}
	err := AuthMiddleware(cmd, []string{})
	if err != nil {
		t.Errorf("AuthMiddleware() should not error when authManager is nil, got: %v", err)
	}
}

func TestAuthMiddleware_DefaultAdmin(t *testing.T) {
	configPath := createTestConfig(t)
	InitAuth(configPath)

	// Clear AGENT_ID env var
	os.Unsetenv("AGENT_ID")

	root := &cobra.Command{Use: "agent-os"}
	scheduler := &cobra.Command{Use: "scheduler"}
	list := &cobra.Command{Use: "list"}
	root.AddCommand(scheduler)
	scheduler.AddCommand(list)

	err := AuthMiddleware(list, []string{})
	if err != nil {
		t.Errorf("AuthMiddleware() should allow admin by default, got error: %v", err)
	}
}

func TestAuthMiddleware_WithAgentID(t *testing.T) {
	configPath := createTestConfig(t)
	InitAuth(configPath)

	tests := []struct {
		name     string
		agentID  string
		buildCmd func() *cobra.Command
		wantErr  bool
	}{
		{
			name:    "fin-agent can execute scheduler:list",
			agentID: "fin-agent",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				scheduler := &cobra.Command{Use: "scheduler"}
				list := &cobra.Command{Use: "list"}
				root.AddCommand(scheduler)
				scheduler.AddCommand(list)
				return list
			},
			wantErr: false,
		},
		{
			name:    "memory-agent cannot execute trading:order",
			agentID: "memory-agent",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				trading := &cobra.Command{Use: "trading"}
				order := &cobra.Command{Use: "order"}
				root.AddCommand(trading)
				trading.AddCommand(order)
				return order
			},
			wantErr: true,
		},
		{
			name:    "memory-agent can execute memory:write",
			agentID: "memory-agent",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				memory := &cobra.Command{Use: "memory"}
				write := &cobra.Command{Use: "write"}
				root.AddCommand(memory)
				memory.AddCommand(write)
				return write
			},
			wantErr: false,
		},
		{
			name:    "system-admin can execute anything",
			agentID: "system-admin",
			buildCmd: func() *cobra.Command {
				root := &cobra.Command{Use: "agent-os"}
				trading := &cobra.Command{Use: "trading"}
				order := &cobra.Command{Use: "order"}
				root.AddCommand(trading)
				trading.AddCommand(order)
				return order
			},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			os.Setenv("AGENT_ID", tt.agentID)
			defer os.Unsetenv("AGENT_ID")

			cmd := tt.buildCmd()
			err := AuthMiddleware(cmd, []string{})
			if (err != nil) != tt.wantErr {
				t.Errorf("AuthMiddleware() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestGetAuthManager(t *testing.T) {
	configPath := createTestConfig(t)
	InitAuth(configPath)

	am := GetAuthManager()
	if am == nil {
		t.Error("GetAuthManager() returned nil")
	}
}
