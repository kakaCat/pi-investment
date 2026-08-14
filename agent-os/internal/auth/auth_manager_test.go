package auth

import (
	"os"
	"path/filepath"
	"testing"
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
      - "decision:*"
      - "data:*"
      - "memory:read"

  memory:
    permissions:
      - "memory:*"
      - "resource:*"

  readonly:
    permissions:
      - "scheduler:list"
      - "scheduler:get"
      - "memory:search"

agents:
  fin-agent:
    role: trading

  memory-agent:
    role: memory

  web-frontend:
    role: readonly

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

func TestNewAuthManager(t *testing.T) {
	configPath := createTestConfig(t)

	am, err := NewAuthManager(configPath)
	if err != nil {
		t.Fatalf("Failed to create AuthManager: %v", err)
	}

	if am == nil {
		t.Fatal("AuthManager is nil")
	}

	if am.config == nil {
		t.Fatal("AuthManager config is nil")
	}
}

func TestNewAuthManager_InvalidPath(t *testing.T) {
	_, err := NewAuthManager("/nonexistent/path.yaml")
	if err == nil {
		t.Fatal("Expected error for invalid path, got nil")
	}
}

func TestGetAgentRole(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	tests := []struct {
		name     string
		agentID  string
		wantRole string
		wantErr  bool
	}{
		{"fin-agent", "fin-agent", "trading", false},
		{"memory-agent", "memory-agent", "memory", false},
		{"web-frontend", "web-frontend", "readonly", false},
		{"system-admin", "system-admin", "admin", false},
		{"unknown agent", "unknown", "", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			role, err := am.GetAgentRole(tt.agentID)
			if (err != nil) != tt.wantErr {
				t.Errorf("GetAgentRole() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if role != tt.wantRole {
				t.Errorf("GetAgentRole() = %v, want %v", role, tt.wantRole)
			}
		})
	}
}

func TestGetRolePermissions(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	tests := []struct {
		name    string
		role    string
		wantErr bool
	}{
		{"admin role", "admin", false},
		{"trading role", "trading", false},
		{"memory role", "memory", false},
		{"readonly role", "readonly", false},
		{"unknown role", "unknown", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			perms, err := am.GetRolePermissions(tt.role)
			if (err != nil) != tt.wantErr {
				t.Errorf("GetRolePermissions() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !tt.wantErr && len(perms) == 0 {
				t.Errorf("GetRolePermissions() returned empty permissions for role %s", tt.role)
			}
		})
	}
}

func TestMatchPermission(t *testing.T) {
	tests := []struct {
		name       string
		permission Permission
		command    string
		want       bool
	}{
		{"wildcard matches everything", "*", "scheduler:list", true},
		{"wildcard matches any command", "*", "trading:order", true},
		{"exact match", "memory:read", "memory:read", true},
		{"exact mismatch", "memory:read", "memory:write", false},
		{"prefix wildcard matches", "scheduler:*", "scheduler:list", true},
		{"prefix wildcard matches multiple", "scheduler:*", "scheduler:trigger", true},
		{"prefix wildcard mismatch", "scheduler:*", "memory:list", false},
		{"prefix wildcard exact prefix", "scheduler:*", "scheduler:", false},
		{"trading wildcard", "trading:*", "trading:order", true},
		{"data wildcard", "data:*", "data:quote", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := matchPermission(tt.permission, tt.command); got != tt.want {
				t.Errorf("matchPermission(%q, %q) = %v, want %v",
					tt.permission, tt.command, got, tt.want)
			}
		})
	}
}

func TestCheckPermission_Admin(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	commands := []string{
		"scheduler:list",
		"scheduler:trigger",
		"trading:order",
		"memory:write",
		"decision:record",
		"data:quote",
	}

	for _, cmd := range commands {
		t.Run(cmd, func(t *testing.T) {
			err := am.CheckPermission("system-admin", cmd)
			if err != nil {
				t.Errorf("Admin should have permission for %s, got error: %v", cmd, err)
			}
		})
	}
}

func TestCheckPermission_TradingAgent(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	tests := []struct {
		name    string
		command string
		wantErr bool
	}{
		{"scheduler list allowed", "scheduler:list", false},
		{"scheduler trigger allowed", "scheduler:trigger", false},
		{"trading order allowed", "trading:order", false},
		{"decision record allowed", "decision:record", false},
		{"data quote allowed", "data:quote", false},
		{"memory read allowed", "memory:read", false},
		{"memory write denied", "memory:write", true},
		{"memory delete denied", "memory:delete", true},
		{"resource quota denied", "resource:quota", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := am.CheckPermission("fin-agent", tt.command)
			if (err != nil) != tt.wantErr {
				t.Errorf("CheckPermission(%q) error = %v, wantErr %v", tt.command, err, tt.wantErr)
			}
		})
	}
}

func TestCheckPermission_MemoryAgent(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	tests := []struct {
		name    string
		command string
		wantErr bool
	}{
		{"memory write allowed", "memory:write", false},
		{"memory read allowed", "memory:read", false},
		{"memory search allowed", "memory:search", false},
		{"resource quota allowed", "resource:quota", false},
		{"trading order denied", "trading:order", true},
		{"scheduler trigger denied", "scheduler:trigger", true},
		{"decision record denied", "decision:record", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := am.CheckPermission("memory-agent", tt.command)
			if (err != nil) != tt.wantErr {
				t.Errorf("CheckPermission(%q) error = %v, wantErr %v", tt.command, err, tt.wantErr)
			}
		})
	}
}

func TestCheckPermission_ReadonlyAgent(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	tests := []struct {
		name    string
		command string
		wantErr bool
	}{
		{"scheduler list allowed", "scheduler:list", false},
		{"scheduler get allowed", "scheduler:get", false},
		{"memory search allowed", "memory:search", false},
		{"scheduler trigger denied", "scheduler:trigger", true},
		{"memory write denied", "memory:write", true},
		{"trading order denied", "trading:order", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := am.CheckPermission("web-frontend", tt.command)
			if (err != nil) != tt.wantErr {
				t.Errorf("CheckPermission(%q) error = %v, wantErr %v", tt.command, err, tt.wantErr)
			}
		})
	}
}

func TestCheckPermission_UnknownAgent(t *testing.T) {
	configPath := createTestConfig(t)
	am, _ := NewAuthManager(configPath)

	err := am.CheckPermission("unknown-agent", "scheduler:list")
	if err == nil {
		t.Error("Expected error for unknown agent, got nil")
	}
}
