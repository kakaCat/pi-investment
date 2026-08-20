package config

import (
	"fmt"
	"os"
	"os/user"
	"sync"

	"github.com/pi-investment/agent-os/pkg/types"
	"github.com/spf13/viper"
)

var (
	cfg  *Config
	once sync.Once
)

// Config holds all configuration for Agent OS
type Config struct {
	Server   ServerConfig   `mapstructure:"server"`
	Database DatabaseConfig `mapstructure:"database"`
	Log      LogConfig      `mapstructure:"log"`
	Redis    RedisConfig    `mapstructure:"redis"`
	// Services registers local services that scheduled tasks can bind to
	// (task.service_name). Entries override the scheduler's built-in
	// defaults (e.g. quantsys-v2) by name.
	Services map[string]types.ServiceDefinition `mapstructure:"services"`
}

// ServerConfig holds server configuration
type ServerConfig struct {
	Host string `mapstructure:"host"`
	Port int    `mapstructure:"port"`
}

// DatabaseConfig holds database configuration
type DatabaseConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	User     string `mapstructure:"user"`
	Password string `mapstructure:"password"`
	DBName   string `mapstructure:"dbname"`
	SSLMode  string `mapstructure:"sslmode"`
}

// LogConfig holds logging configuration
type LogConfig struct {
	Level      string `mapstructure:"level"`
	Format     string `mapstructure:"format"`
	OutputPath string `mapstructure:"output_path"`
}

// RedisConfig holds Redis configuration
type RedisConfig struct {
	Host     string `mapstructure:"host"`
	Port     int    `mapstructure:"port"`
	Password string `mapstructure:"password"`
	DB       int    `mapstructure:"db"`
}

// Load loads configuration from file
func Load(cfgFile string) error {
	v := viper.New()

	// Set defaults
	setDefaults(v)

	// Set config file
	if cfgFile != "" {
		v.SetConfigFile(cfgFile)
	} else {
		v.SetConfigName("config")
		v.SetConfigType("yaml")
		v.AddConfigPath(".")
		v.AddConfigPath("./configs")
		v.AddConfigPath("$HOME/.agent-os")
	}

	// Read from environment variables
	v.SetEnvPrefix("AGENT_OS")
	v.AutomaticEnv()

	// Read config file (optional)
	if err := v.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return fmt.Errorf("failed to read config file: %w", err)
		}
		// Config file not found; ignore error and use defaults
	}

	// Unmarshal config
	var c Config
	if err := v.Unmarshal(&c); err != nil {
		return fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Validate config
	if err := c.Validate(); err != nil {
		return fmt.Errorf("invalid config: %w", err)
	}

	once.Do(func() {
		cfg = &c
	})

	return nil
}

// Get returns the global config instance
func Get() *Config {
	if cfg == nil {
		// Return default config if not loaded
		return getDefaultConfig()
	}
	return cfg
}

// getDefaultConfig returns a default configuration
func getDefaultConfig() *Config {
	// Get username from environment, fallback to current user
	dbUser := os.Getenv("DB_USER")
	if dbUser == "" {
		if u, err := user.Current(); err == nil {
			dbUser = u.Username
		} else {
			dbUser = "postgres" // final fallback
		}
	}

	return &Config{
		Server: ServerConfig{
			Host: "127.0.0.1",
			Port: 8080,
		},
		Database: DatabaseConfig{
			Host:    "127.0.0.1",
			Port:    5432,
			User:    dbUser,
			DBName:  "agent_os",
			SSLMode: "disable",
		},
		Log: LogConfig{
			Level:      "info",
			Format:     "json",
			OutputPath: "stdout",
		},
		Redis: RedisConfig{
			Host: "127.0.0.1",
			Port: 6379,
			DB:   0,
		},
	}
}

// Validate validates the configuration
func (c *Config) Validate() error {
	// Validate server config
	if c.Server.Port < 1 || c.Server.Port > 65535 {
		return fmt.Errorf("invalid server port: %d (must be between 1 and 65535)", c.Server.Port)
	}

	// Validate database config
	if c.Database.Host == "" {
		return fmt.Errorf("database host is required")
	}
	if c.Database.Port < 1 || c.Database.Port > 65535 {
		return fmt.Errorf("invalid database port: %d (must be between 1 and 65535)", c.Database.Port)
	}
	if c.Database.User == "" {
		return fmt.Errorf("database user is required")
	}
	if c.Database.DBName == "" {
		return fmt.Errorf("database name is required")
	}

	// Validate log config
	validLevels := map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
	if !validLevels[c.Log.Level] {
		return fmt.Errorf("invalid log level: %s (must be one of: debug, info, warn, error)", c.Log.Level)
	}

	validFormats := map[string]bool{"json": true, "text": true}
	if !validFormats[c.Log.Format] {
		return fmt.Errorf("invalid log format: %s (must be one of: json, text)", c.Log.Format)
	}

	// Validate Redis config
	if c.Redis.Port < 1 || c.Redis.Port > 65535 {
		return fmt.Errorf("invalid redis port: %d (must be between 1 and 65535)", c.Redis.Port)
	}

	return nil
}

// setDefaults sets default configuration values
func setDefaults(v *viper.Viper) {
	// Server defaults
	v.SetDefault("server.host", "127.0.0.1")
	v.SetDefault("server.port", 8080)

	// Database defaults
	v.SetDefault("database.host", "127.0.0.1")
	v.SetDefault("database.port", 5432)
	v.SetDefault("database.user", "yunpeng")
	v.SetDefault("database.password", "")
	v.SetDefault("database.dbname", "quant_investment")
	v.SetDefault("database.sslmode", "disable")

	// Log defaults
	v.SetDefault("log.level", "info")
	v.SetDefault("log.format", "json")
	v.SetDefault("log.output_path", "stdout")

	// Redis defaults
	v.SetDefault("redis.host", "127.0.0.1")
	v.SetDefault("redis.port", 6379)
	v.SetDefault("redis.password", "")
	v.SetDefault("redis.db", 0)
}
