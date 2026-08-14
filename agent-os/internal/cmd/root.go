package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/middleware"
	"github.com/pi-investment/agent-os/pkg/logger"
	"github.com/spf13/cobra"
)

var (
	cfgFile string
	log     *logger.Logger
)

// rootCmd represents the base command when called without any subcommands
var rootCmd = &cobra.Command{
	Use:   "agent-os",
	Short: "Agent OS - Operating System for AI Agents",
	Long: `Agent OS is a centralized operating system layer for AI agents.
It provides scheduling, resource management, memory, and decision support.`,
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		// Initialize logger
		var err error
		log, err = logger.New(config.Get().Log)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to initialize logger: %v\n", err)
			os.Exit(1)
		}

		// Initialize auth manager (skip for version/help commands)
		if cmd.Use != "version" && cmd.Use != "help" {
			permissionsPath := filepath.Join("config", "permissions.yaml")
			if err := middleware.InitAuth(permissionsPath); err != nil {
				fmt.Fprintf(os.Stderr, "Warning: Failed to initialize auth: %v\n", err)
				// Continue without auth (for backward compatibility)
			}
		}
	},
}

// Execute adds all child commands to the root command and sets flags appropriately.
func Execute() error {
	return rootCmd.Execute()
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is ./config.yaml)")
}

// initConfig reads in config file and ENV variables if set.
func initConfig() {
	if err := config.Load(cfgFile); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load config: %v\n", err)
		os.Exit(1)
	}
}
