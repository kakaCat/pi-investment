package config

import (
	"os"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestConfig_Validate(t *testing.T) {
	tests := []struct {
		name    string
		config  Config
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid config",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 8080,
				},
				Database: DatabaseConfig{
					Host:    "localhost",
					Port:    5432,
					User:    "testuser",
					DBName:  "testdb",
					SSLMode: "disable",
				},
				Log: LogConfig{
					Level:      "info",
					Format:     "json",
					OutputPath: "stdout",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
					DB:   0,
				},
			},
			wantErr: false,
		},
		{
			name: "invalid server port - too low",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 0,
				},
				Database: DatabaseConfig{
					Host:   "localhost",
					Port:   5432,
					User:   "testuser",
					DBName: "testdb",
				},
				Log: LogConfig{
					Level:  "info",
					Format: "json",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
				},
			},
			wantErr: true,
			errMsg:  "invalid server port",
		},
		{
			name: "invalid server port - too high",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 70000,
				},
				Database: DatabaseConfig{
					Host:   "localhost",
					Port:   5432,
					User:   "testuser",
					DBName: "testdb",
				},
				Log: LogConfig{
					Level:  "info",
					Format: "json",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
				},
			},
			wantErr: true,
			errMsg:  "invalid server port",
		},
		{
			name: "missing database host",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 8080,
				},
				Database: DatabaseConfig{
					Host:   "",
					Port:   5432,
					User:   "testuser",
					DBName: "testdb",
				},
				Log: LogConfig{
					Level:  "info",
					Format: "json",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
				},
			},
			wantErr: true,
			errMsg:  "database host is required",
		},
		{
			name: "missing database user",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 8080,
				},
				Database: DatabaseConfig{
					Host:   "localhost",
					Port:   5432,
					User:   "",
					DBName: "testdb",
				},
				Log: LogConfig{
					Level:  "info",
					Format: "json",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
				},
			},
			wantErr: true,
			errMsg:  "database user is required",
		},
		{
			name: "invalid log level",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 8080,
				},
				Database: DatabaseConfig{
					Host:   "localhost",
					Port:   5432,
					User:   "testuser",
					DBName: "testdb",
				},
				Log: LogConfig{
					Level:  "invalid",
					Format: "json",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
				},
			},
			wantErr: true,
			errMsg:  "invalid log level",
		},
		{
			name: "invalid log format",
			config: Config{
				Server: ServerConfig{
					Host: "127.0.0.1",
					Port: 8080,
				},
				Database: DatabaseConfig{
					Host:   "localhost",
					Port:   5432,
					User:   "testuser",
					DBName: "testdb",
				},
				Log: LogConfig{
					Level:  "info",
					Format: "invalid",
				},
				Redis: RedisConfig{
					Host: "localhost",
					Port: 6379,
				},
			},
			wantErr: true,
			errMsg:  "invalid log format",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				require.Error(t, err)
				assert.Contains(t, err.Error(), tt.errMsg)
			} else {
				require.NoError(t, err)
			}
		})
	}
}

func TestGetDefaultConfig(t *testing.T) {
	// Test without DB_USER env var
	os.Unsetenv("DB_USER")
	config := getDefaultConfig()

	assert.NotEmpty(t, config.Database.User)
	assert.Equal(t, "agent_os", config.Database.DBName)
	assert.Equal(t, 8080, config.Server.Port)
	assert.Equal(t, "info", config.Log.Level)

	// Test with DB_USER env var
	os.Setenv("DB_USER", "custom_user")
	defer os.Unsetenv("DB_USER")

	config = getDefaultConfig()
	assert.Equal(t, "custom_user", config.Database.User)
}

func TestLoad(t *testing.T) {
	// Create a temporary config file
	tmpFile := "/tmp/test_config.yaml"
	configContent := `
server:
  host: "0.0.0.0"
  port: 9090

database:
  host: "db.example.com"
  port: 5433
  user: "testuser"
  password: "testpass"
  dbname: "testdb"
  sslmode: "require"

log:
  level: "debug"
  format: "text"
  output_path: "/var/log/agent-os.log"

redis:
  host: "redis.example.com"
  port: 6380
  password: "redispass"
  db: 1
`
	err := os.WriteFile(tmpFile, []byte(configContent), 0644)
	require.NoError(t, err)
	defer os.Remove(tmpFile)

	// Reset global config
	cfg = nil
	once = *new(sync.Once)

	// Load config
	err = Load(tmpFile)
	require.NoError(t, err)

	// Verify loaded config
	loadedCfg := Get()
	assert.Equal(t, "0.0.0.0", loadedCfg.Server.Host)
	assert.Equal(t, 9090, loadedCfg.Server.Port)
	assert.Equal(t, "db.example.com", loadedCfg.Database.Host)
	assert.Equal(t, 5433, loadedCfg.Database.Port)
	assert.Equal(t, "testuser", loadedCfg.Database.User)
	assert.Equal(t, "testdb", loadedCfg.Database.DBName)
	assert.Equal(t, "debug", loadedCfg.Log.Level)
	assert.Equal(t, "text", loadedCfg.Log.Format)
}
