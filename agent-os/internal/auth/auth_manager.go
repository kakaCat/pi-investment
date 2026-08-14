package auth

import (
	"fmt"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

// Permission represents a command permission
type Permission string

// Role defines a set of permissions
type Role struct {
	Permissions []Permission `yaml:"permissions"`
}

// AgentConfig maps an agent to a role
type AgentConfig struct {
	Role string `yaml:"role"`
}

// PermissionsConfig is the root configuration structure
type PermissionsConfig struct {
	Roles  map[string]Role        `yaml:"roles"`
	Agents map[string]AgentConfig `yaml:"agents"`
}

// AuthManager handles permission checking
type AuthManager struct {
	config *PermissionsConfig
}

// NewAuthManager creates a new AuthManager from a config file
func NewAuthManager(configPath string) (*AuthManager, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read permissions config: %w", err)
	}

	var config PermissionsConfig
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse permissions config: %w", err)
	}

	return &AuthManager{config: &config}, nil
}

// CheckPermission verifies if an agent has permission to execute a command
func (am *AuthManager) CheckPermission(agentID, command string) error {
	// Get agent's role
	role, err := am.GetAgentRole(agentID)
	if err != nil {
		return fmt.Errorf("permission denied: %w", err)
	}

	// Get role's permissions
	permissions, err := am.GetRolePermissions(role)
	if err != nil {
		return fmt.Errorf("permission denied: %w", err)
	}

	// Check if command matches any permission
	for _, perm := range permissions {
		if matchPermission(perm, command) {
			return nil // Permission granted
		}
	}

	return fmt.Errorf("permission denied: agent '%s' (role '%s') cannot execute '%s'",
		agentID, role, command)
}

// GetAgentRole returns the role for a given agent ID
func (am *AuthManager) GetAgentRole(agentID string) (string, error) {
	agentConfig, ok := am.config.Agents[agentID]
	if !ok {
		return "", fmt.Errorf("unknown agent: %s", agentID)
	}
	return agentConfig.Role, nil
}

// GetRolePermissions returns the permissions for a given role
func (am *AuthManager) GetRolePermissions(role string) ([]Permission, error) {
	roleConfig, ok := am.config.Roles[role]
	if !ok {
		return nil, fmt.Errorf("unknown role: %s", role)
	}
	return roleConfig.Permissions, nil
}

// matchPermission checks if a permission pattern matches a command
// Supports wildcard matching:
// - "*" matches everything
// - "scheduler:*" matches "scheduler:list", "scheduler:trigger", etc.
// - "memory:read" matches exactly "memory:read"
func matchPermission(permission Permission, command string) bool {
	permStr := string(permission)

	// Wildcard: matches everything
	if permStr == "*" {
		return true
	}

	// Exact match
	if permStr == command {
		return true
	}

	// Prefix wildcard: "scheduler:*" matches "scheduler:list"
	if strings.HasSuffix(permStr, ":*") {
		prefix := strings.TrimSuffix(permStr, ":*")
		// Must have something after the colon
		return strings.HasPrefix(command, prefix+":") && len(command) > len(prefix)+1
	}

	return false
}
