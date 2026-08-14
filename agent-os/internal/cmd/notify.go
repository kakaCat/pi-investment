package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"
)

var notifyCmd = &cobra.Command{
	Use:   "notify",
	Short: "Send notifications via Feishu",
	Long:  `Send notifications to users or channels using Feishu webhook API.`,
}

var notifySendCmd = &cobra.Command{
	Use:   "send",
	Short: "Send a notification",
	Long:  `Send a notification to a user or channel via Feishu.`,
	RunE:  runNotifySend,
}

var notifyTestCmd = &cobra.Command{
	Use:   "test",
	Short: "Send a test notification",
	RunE:  runNotifyTest,
}

// Flags
var (
	notifyUser    string
	notifyChannel string
	notifyTitle   string
	notifyMessage string
	notifyColor   string
	notifyWebhook string
)

func init() {
	rootCmd.AddCommand(notifyCmd)

	// Subcommands
	notifyCmd.AddCommand(notifySendCmd)
	notifyCmd.AddCommand(notifyTestCmd)

	// Send flags
	notifySendCmd.Flags().StringVar(&notifyUser, "user", "", "User to send notification to")
	notifySendCmd.Flags().StringVar(&notifyChannel, "channel", "", "Channel to send notification to")
	notifySendCmd.Flags().StringVar(&notifyTitle, "title", "", "Notification title (required)")
	notifySendCmd.Flags().StringVar(&notifyMessage, "message", "", "Notification message (required)")
	notifySendCmd.Flags().StringVar(&notifyColor, "color", "blue", "Card header color (blue/green/red/orange/purple/grey)")
	notifySendCmd.Flags().StringVar(&notifyWebhook, "webhook", "", "Override webhook URL")
	notifySendCmd.MarkFlagRequired("title")
	notifySendCmd.MarkFlagRequired("message")

	// Test flags
	notifyTestCmd.Flags().StringVar(&notifyTitle, "title", "Test Notification", "Test notification title")
	notifyTestCmd.Flags().StringVar(&notifyWebhook, "webhook", "", "Webhook URL to test")
}

func getFeishuDriverPath() (string, error) {
	// Get agent-os root directory
	executable, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("failed to get executable path: %w", err)
	}

	// Navigate to agent-os root (assuming binary is in cmd/agent-os/)
	agentOSRoot := filepath.Dir(filepath.Dir(executable))

	// Path to feishu-driver
	driverPath := filepath.Join(agentOSRoot, "drivers", "feishu-driver", "main.py")

	// Check if driver exists
	if _, err := os.Stat(driverPath); os.IsNotExist(err) {
		// Try current working directory
		cwd, _ := os.Getwd()
		driverPath = filepath.Join(cwd, "drivers", "feishu-driver", "main.py")
		if _, err := os.Stat(driverPath); os.IsNotExist(err) {
			return "", fmt.Errorf("feishu-driver not found at %s", driverPath)
		}
	}

	return driverPath, nil
}

func runFeishuDriver(args []string) (string, error) {
	driverPath, err := getFeishuDriverPath()
	if err != nil {
		return "", err
	}

	// Find python3 executable
	pythonCmd, err := exec.LookPath("python3")
	if err != nil {
		pythonCmd, err = exec.LookPath("python")
		if err != nil {
			return "", fmt.Errorf("python3 not found in PATH")
		}
	}

	// Build command
	cmdArgs := append([]string{driverPath}, args...)
	cmd := exec.Command(pythonCmd, cmdArgs...)

	// Set environment
	cmd.Env = os.Environ()

	// Capture output
	output, err := cmd.CombinedOutput()
	outputStr := strings.TrimSpace(string(output))

	if err != nil {
		// Check exit code
		if exitError, ok := err.(*exec.ExitError); ok {
			exitCode := exitError.ExitCode()
			switch exitCode {
			case 1:
				return "", fmt.Errorf("invalid arguments: %s", outputStr)
			case 2:
				return "", fmt.Errorf("notification failed: %s", outputStr)
			case 3:
				return "", fmt.Errorf("system error: %s", outputStr)
			default:
				return "", fmt.Errorf("driver error (exit code %d): %s", exitCode, outputStr)
			}
		}
		return "", fmt.Errorf("failed to run driver: %w\n%s", err, outputStr)
	}

	return outputStr, nil
}

func runNotifySend(cmd *cobra.Command, args []string) error {
	// Validate flags
	if notifyUser == "" && notifyChannel == "" {
		return fmt.Errorf("either --user or --channel must be specified")
	}

	if notifyUser != "" && notifyChannel != "" {
		return fmt.Errorf("cannot specify both --user and --channel")
	}

	// Build driver arguments
	driverArgs := []string{"send", "--title", notifyTitle, "--message", notifyMessage, "--color", notifyColor}

	if notifyUser != "" {
		driverArgs = append(driverArgs, "--user", notifyUser)
	} else {
		driverArgs = append(driverArgs, "--channel", notifyChannel)
	}

	if notifyWebhook != "" {
		driverArgs = append(driverArgs, "--webhook", notifyWebhook)
	}

	// Run driver
	output, err := runFeishuDriver(driverArgs)
	if err != nil {
		return err
	}

	// Success
	fmt.Println("✓ Notification sent")
	if output != "" {
		fmt.Println(output)
	}

	return nil
}

func runNotifyTest(cmd *cobra.Command, args []string) error {
	// Build driver arguments
	driverArgs := []string{"test", "--title", notifyTitle}

	if notifyWebhook != "" {
		driverArgs = append(driverArgs, "--webhook", notifyWebhook)
	}

	// Run driver
	output, err := runFeishuDriver(driverArgs)
	if err != nil {
		return err
	}

	// Parse output for JSON response
	if strings.Contains(output, "Response:") {
		lines := strings.Split(output, "\n")
		for _, line := range lines {
			if strings.Contains(line, "Response:") {
				// Extract JSON
				jsonStart := strings.Index(line, "{")
				if jsonStart != -1 {
					jsonStr := line[jsonStart:]
					var response map[string]interface{}
					if err := json.Unmarshal([]byte(jsonStr), &response); err == nil {
						prettyJSON, _ := json.MarshalIndent(response, "", "  ")
						fmt.Println(string(prettyJSON))
						return nil
					}
				}
			}
		}
	}

	// Fallback: print raw output
	fmt.Println(output)
	return nil
}
