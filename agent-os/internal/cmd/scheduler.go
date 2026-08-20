package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"text/tabwriter"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/kernel/scheduler"
	"github.com/pi-investment/agent-os/internal/middleware"
	"github.com/pi-investment/agent-os/internal/storage/postgres"
	"github.com/pi-investment/agent-os/pkg/types"
	"github.com/spf13/cobra"
)

var schedulerCmd = &cobra.Command{
	Use:   "scheduler",
	Short: "Manage task scheduling",
	Long:  "Manage task scheduling, execution, and dependencies",
}

var schedulerRegisterCmd = &cobra.Command{
	Use:   "register",
	Short: "Register a new task",
	Long:  "Register a new task with optional schedule and dependencies",
	PreRunE: middleware.AuthMiddleware,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := context.Background()

		// Initialize database
		if err := postgres.InitPool(ctx); err != nil {
			return fmt.Errorf("failed to initialize database: %w", err)
		}
		defer postgres.Close()

		// Get flags
		name, _ := cmd.Flags().GetString("name")
		description, _ := cmd.Flags().GetString("description")
		schedule, _ := cmd.Flags().GetString("schedule")
		command, _ := cmd.Flags().GetString("command")
		serviceName, _ := cmd.Flags().GetString("service")
		enabled, _ := cmd.Flags().GetBool("enabled")
		owner, _ := cmd.Flags().GetString("owner")

		// Create task
		task := &types.Task{
			Name:        name,
			Description: description,
			Schedule:    schedule,
			Command:     command,
			ServiceName: serviceName,
			Enabled:     enabled,
			CreatedBy:   owner,
			Metadata:    make(map[string]interface{}),
		}

		// Create scheduler
		s := scheduler.New(nil)
		if err := s.RegisterTask(ctx, task); err != nil {
			return fmt.Errorf("failed to register task: %w", err)
		}

		// Output as JSON
		output, _ := json.MarshalIndent(task, "", "  ")
		fmt.Println(string(output))

		return nil
	},
}

var schedulerListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all tasks",
	Long:  "List all registered tasks with their status",
	PreRunE: middleware.AuthMiddleware,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := context.Background()

		// Initialize database
		if err := postgres.InitPool(ctx); err != nil {
			return fmt.Errorf("failed to initialize database: %w", err)
		}
		defer postgres.Close()

		// Get flags
		enabledOnly, _ := cmd.Flags().GetBool("enabled-only")
		jsonOutput, _ := cmd.Flags().GetBool("json")
		stats, _ := cmd.Flags().GetBool("stats")

		taskRepo := postgres.NewTaskRepository()

		if stats {
			// Get tasks with stats
			tasks, err := taskRepo.GetTasksWithStats(ctx)
			if err != nil {
				return fmt.Errorf("failed to list tasks: %w", err)
			}

			if jsonOutput {
				output, _ := json.MarshalIndent(tasks, "", "  ")
				fmt.Println(string(output))
			} else {
				printTasksWithStats(tasks)
			}
		} else {
			// Get tasks without stats
			tasks, err := taskRepo.List(ctx, enabledOnly)
			if err != nil {
				return fmt.Errorf("failed to list tasks: %w", err)
			}

			if jsonOutput {
				output, _ := json.MarshalIndent(tasks, "", "  ")
				fmt.Println(string(output))
			} else {
				printTasks(tasks)
			}
		}

		return nil
	},
}

var schedulerTriggerCmd = &cobra.Command{
	Use:   "trigger",
	Short: "Manually trigger a task",
	Long:  "Manually trigger a task execution",
	PreRunE: middleware.AuthMiddleware,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := context.Background()

		// Initialize database
		if err := postgres.InitPool(ctx); err != nil {
			return fmt.Errorf("failed to initialize database: %w", err)
		}
		defer postgres.Close()

		// Get flags
		taskIDStr, _ := cmd.Flags().GetString("task-id")
		taskName, _ := cmd.Flags().GetString("name")

		// Parse task ID or get by name
		var taskID uuid.UUID
		var err error

		if taskIDStr != "" {
			taskID, err = uuid.Parse(taskIDStr)
			if err != nil {
				return fmt.Errorf("invalid task ID: %w", err)
			}
		} else if taskName != "" {
			taskRepo := postgres.NewTaskRepository()
			task, err := taskRepo.GetByName(ctx, taskName)
			if err != nil {
				return fmt.Errorf("failed to get task by name: %w", err)
			}
			taskID = task.ID
		} else {
			return fmt.Errorf("either --task-id or --name must be specified")
		}

		// Create scheduler
		s := scheduler.New(nil)

		// Trigger task
		run, err := s.TriggerTask(ctx, taskID)
		if err != nil {
			return fmt.Errorf("failed to trigger task: %w", err)
		}

		// Output as JSON
		output, _ := json.MarshalIndent(run, "", "  ")
		fmt.Println(string(output))

		return nil
	},
}

var schedulerExecutionsCmd = &cobra.Command{
	Use:   "executions",
	Short: "List task executions",
	Long:  "List execution history for a task",
	PreRunE: middleware.AuthMiddleware,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := context.Background()

		// Initialize database
		if err := postgres.InitPool(ctx); err != nil {
			return fmt.Errorf("failed to initialize database: %w", err)
		}
		defer postgres.Close()

		// Get flags
		taskIDStr, _ := cmd.Flags().GetString("task-id")
		taskName, _ := cmd.Flags().GetString("name")
		limit, _ := cmd.Flags().GetInt("limit")
		jsonOutput, _ := cmd.Flags().GetBool("json")

		// Parse task ID or get by name
		var taskID uuid.UUID
		var err error

		if taskIDStr != "" {
			taskID, err = uuid.Parse(taskIDStr)
			if err != nil {
				return fmt.Errorf("invalid task ID: %w", err)
			}
		} else if taskName != "" {
			taskRepo := postgres.NewTaskRepository()
			task, err := taskRepo.GetByName(ctx, taskName)
			if err != nil {
				return fmt.Errorf("failed to get task by name: %w", err)
			}
			taskID = task.ID
		} else {
			return fmt.Errorf("either --task-id or --name must be specified")
		}

		// Get task runs
		runRepo := postgres.NewTaskRunRepository()
		runs, err := runRepo.ListByTaskID(ctx, taskID, limit)
		if err != nil {
			return fmt.Errorf("failed to list task runs: %w", err)
		}

		if jsonOutput {
			output, _ := json.MarshalIndent(runs, "", "  ")
			fmt.Println(string(output))
		} else {
			printTaskRuns(runs)
		}

		return nil
	},
}

var schedulerDeleteCmd = &cobra.Command{
	Use:   "delete",
	Short: "Delete a task",
	Long:  "Delete a task and all its execution history",
	PreRunE: middleware.AuthMiddleware,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx := context.Background()

		// Initialize database
		if err := postgres.InitPool(ctx); err != nil {
			return fmt.Errorf("failed to initialize database: %w", err)
		}
		defer postgres.Close()

		// Get flags
		taskIDStr, _ := cmd.Flags().GetString("task-id")
		taskName, _ := cmd.Flags().GetString("name")

		// Parse task ID or get by name
		var taskID uuid.UUID
		var err error

		if taskIDStr != "" {
			taskID, err = uuid.Parse(taskIDStr)
			if err != nil {
				return fmt.Errorf("invalid task ID: %w", err)
			}
		} else if taskName != "" {
			taskRepo := postgres.NewTaskRepository()
			task, err := taskRepo.GetByName(ctx, taskName)
			if err != nil {
				return fmt.Errorf("failed to get task by name: %w", err)
			}
			taskID = task.ID
		} else {
			return fmt.Errorf("either --task-id or --name must be specified")
		}

		// Create scheduler
		s := scheduler.New(nil)

		// Delete task
		if err := s.DeleteTask(ctx, taskID); err != nil {
			return fmt.Errorf("failed to delete task: %w", err)
		}

		fmt.Printf("Task deleted: %s\n", taskID)

		return nil
	},
}

func init() {
	rootCmd.AddCommand(schedulerCmd)

	// Add subcommands
	schedulerCmd.AddCommand(schedulerRegisterCmd)
	schedulerCmd.AddCommand(schedulerListCmd)
	schedulerCmd.AddCommand(schedulerTriggerCmd)
	schedulerCmd.AddCommand(schedulerExecutionsCmd)
	schedulerCmd.AddCommand(schedulerDeleteCmd)

	// Register command flags
	schedulerRegisterCmd.Flags().String("name", "", "Task name (required)")
	schedulerRegisterCmd.Flags().String("description", "", "Task description")
	schedulerRegisterCmd.Flags().String("schedule", "", "Cron schedule expression")
	schedulerRegisterCmd.Flags().String("command", "", "Command to execute (required)")
	schedulerRegisterCmd.Flags().String("service", "", "Bound service name (ensured running before execution, e.g. quantsys-v2)")
	schedulerRegisterCmd.Flags().Bool("enabled", true, "Enable task")
	schedulerRegisterCmd.Flags().String("owner", "system", "Task owner (agent ID)")
	schedulerRegisterCmd.MarkFlagRequired("name")
	schedulerRegisterCmd.MarkFlagRequired("command")

	// List command flags
	schedulerListCmd.Flags().Bool("enabled-only", false, "Show only enabled tasks")
	schedulerListCmd.Flags().Bool("json", false, "Output as JSON")
	schedulerListCmd.Flags().Bool("stats", false, "Include execution statistics")

	// Trigger command flags
	schedulerTriggerCmd.Flags().String("task-id", "", "Task ID")
	schedulerTriggerCmd.Flags().String("name", "", "Task name")

	// Executions command flags
	schedulerExecutionsCmd.Flags().String("task-id", "", "Task ID")
	schedulerExecutionsCmd.Flags().String("name", "", "Task name")
	schedulerExecutionsCmd.Flags().Int("limit", 20, "Maximum number of executions to show")
	schedulerExecutionsCmd.Flags().Bool("json", false, "Output as JSON")

	// Delete command flags
	schedulerDeleteCmd.Flags().String("task-id", "", "Task ID")
	schedulerDeleteCmd.Flags().String("name", "", "Task name")
}

// Helper functions for printing

func printTasks(tasks []*types.Task) {
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tNAME\tSCHEDULE\tENABLED\tCREATED_AT")

	for _, task := range tasks {
		fmt.Fprintf(w, "%s\t%s\t%s\t%v\t%s\n",
			task.ID.String()[:8],
			task.Name,
			task.Schedule,
			task.Enabled,
			task.CreatedAt.Format("2006-01-02 15:04"))
	}

	w.Flush()
}

func printTasksWithStats(tasks []*types.TaskWithStats) {
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tNAME\tSCHEDULE\tENABLED\tRUNS\tSUCCESS_RATE\tLAST_RUN\tLAST_STATUS")

	for _, task := range tasks {
		lastRun := "never"
		if task.LastRunAt != nil {
			lastRun = task.LastRunAt.Format("2006-01-02 15:04")
		}

		lastStatus := "-"
		if task.LastRunStatus != nil {
			lastStatus = string(*task.LastRunStatus)
		}

		fmt.Fprintf(w, "%s\t%s\t%s\t%v\t%d\t%.1f%%\t%s\t%s\n",
			task.ID.String()[:8],
			task.Name,
			task.Schedule,
			task.Enabled,
			task.TotalRuns,
			task.SuccessRate,
			lastRun,
			lastStatus)
	}

	w.Flush()
}

func printTaskRuns(runs []*types.TaskRun) {
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tSTATUS\tSTARTED_AT\tDURATION\tTRIGGERED_BY")

	for _, run := range runs {
		duration := "-"
		if run.DurationMs != nil {
			d := time.Duration(*run.DurationMs) * time.Millisecond
			duration = d.String()
		}

		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n",
			run.ID.String()[:8],
			run.Status,
			run.StartedAt.Format("2006-01-02 15:04:05"),
			duration,
			run.TriggeredBy)
	}

	w.Flush()
}
