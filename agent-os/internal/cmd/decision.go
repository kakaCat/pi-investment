package cmd

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/google/uuid"
	"github.com/spf13/cobra"

	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
)

var decisionCmd = &cobra.Command{
	Use:   "decision",
	Short: "Decision management commands",
	Long:  `Manage agent decisions: record, list, get, and update investment decisions.`,
}

var decisionRecordCmd = &cobra.Command{
	Use:   "record",
	Short: "Record a new decision",
	Long:  `Create a new decision entry with agent, action, targets, reason, and confidence.`,
	RunE:  runDecisionRecord,
}

var decisionGetCmd = &cobra.Command{
	Use:   "get <id>",
	Short: "Get a decision by ID",
	Args:  cobra.ExactArgs(1),
	RunE:  runDecisionGet,
}

var decisionListCmd = &cobra.Command{
	Use:   "list",
	Short: "List decisions",
	Long:  `List decisions with optional filters.`,
	RunE:  runDecisionList,
}

var decisionUpdateCmd = &cobra.Command{
	Use:   "update <id>",
	Short: "Update a decision outcome",
	Args:  cobra.ExactArgs(1),
	RunE:  runDecisionUpdate,
}

var decisionDeleteCmd = &cobra.Command{
	Use:   "delete <id>",
	Short: "Delete a decision by ID",
	Args:  cobra.ExactArgs(1),
	RunE:  runDecisionDelete,
}

var decisionStatsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Get decision statistics",
	Long:  `Get statistics about decisions for an agent.`,
	RunE:  runDecisionStats,
}

// Flags
var (
	decisionAgent       string
	decisionAction      string
	decisionTargets     []string
	decisionTargetsJSON string
	decisionReason      string
	decisionConfidence  float64
	decisionContext     string
	decisionOutcome     string
	decisionLimit       int
	decisionOffset      int
	decisionOutputJSON  bool
	decisionExecuted    string // "all", "true", "false"
)

func init() {
	rootCmd.AddCommand(decisionCmd)

	// Subcommands
	decisionCmd.AddCommand(decisionRecordCmd)
	decisionCmd.AddCommand(decisionGetCmd)
	decisionCmd.AddCommand(decisionListCmd)
	decisionCmd.AddCommand(decisionUpdateCmd)
	decisionCmd.AddCommand(decisionDeleteCmd)
	decisionCmd.AddCommand(decisionStatsCmd)

	// Record flags
	decisionRecordCmd.Flags().StringVar(&decisionAgent, "agent", "", "Agent ID (required)")
	decisionRecordCmd.Flags().StringVar(&decisionAction, "action", "", "Action: watch, buy, sell, hold (required)")
	decisionRecordCmd.Flags().StringSliceVar(&decisionTargets, "targets", []string{}, "Target stock symbols (comma-separated)")
	decisionRecordCmd.Flags().StringVar(&decisionTargetsJSON, "targets-json", "", "Target stock symbols as JSON array")
	decisionRecordCmd.Flags().StringVar(&decisionReason, "reason", "", "Decision reason")
	decisionRecordCmd.Flags().Float64Var(&decisionConfidence, "confidence", 0.5, "Confidence (0.0-1.0)")
	decisionRecordCmd.Flags().StringVar(&decisionContext, "context", "{}", "Context as JSON")
	decisionRecordCmd.MarkFlagRequired("agent")
	decisionRecordCmd.MarkFlagRequired("action")

	// List flags
	decisionListCmd.Flags().StringVar(&decisionAgent, "agent", "", "Filter by agent ID")
	decisionListCmd.Flags().StringVar(&decisionAction, "action", "", "Filter by action (watch, buy, sell, hold)")
	decisionListCmd.Flags().StringVar(&decisionExecuted, "executed", "all", "Filter by execution status: all, true, false")
	decisionListCmd.Flags().IntVar(&decisionLimit, "limit", 20, "Maximum results")
	decisionListCmd.Flags().IntVar(&decisionOffset, "offset", 0, "Result offset")
	decisionListCmd.Flags().BoolVar(&decisionOutputJSON, "json", false, "Output as JSON")

	// Get flags
	decisionGetCmd.Flags().BoolVar(&decisionOutputJSON, "json", false, "Output as JSON")

	// Update flags
	decisionUpdateCmd.Flags().StringVar(&decisionOutcome, "outcome", "", "Outcome as JSON (required)")
	decisionUpdateCmd.MarkFlagRequired("outcome")

	// Stats flags
	decisionStatsCmd.Flags().StringVar(&decisionAgent, "agent", "", "Agent ID (required)")
	decisionStatsCmd.Flags().BoolVar(&decisionOutputJSON, "json", false, "Output as JSON")
	decisionStatsCmd.MarkFlagRequired("agent")
}

func getDecisionService() (domain.DecisionService, error) {
	cfg := config.Get()
	connStr := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.DBName,
		cfg.Database.SSLMode,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	repo := repository.NewDecisionRepository(db)
	svc := service.NewDecisionService(repo)

	return svc, nil
}

func runDecisionRecord(cmd *cobra.Command, args []string) error {
	svc, err := getDecisionService()
	if err != nil {
		return err
	}

	// Parse action
	action := domain.DecisionAction(decisionAction)
	if action != domain.ActionWatch && action != domain.ActionBuy &&
		action != domain.ActionSell && action != domain.ActionHold {
		return fmt.Errorf("invalid action: %s (must be watch, buy, sell, or hold)", decisionAction)
	}

	// Parse targets
	var targets []string
	if decisionTargetsJSON != "" {
		if err := json.Unmarshal([]byte(decisionTargetsJSON), &targets); err != nil {
			return fmt.Errorf("invalid targets JSON: %w", err)
		}
	} else if len(decisionTargets) > 0 {
		targets = decisionTargets
	} else {
		return fmt.Errorf("targets are required (use --targets or --targets-json)")
	}

	// Parse context
	var context map[string]interface{}
	if decisionContext != "" && decisionContext != "{}" {
		if err := json.Unmarshal([]byte(decisionContext), &context); err != nil {
			return fmt.Errorf("invalid context JSON: %w", err)
		}
	}

	// Record decision
	decision, err := svc.Record(decisionAgent, action, targets, decisionReason, decisionConfidence, context)
	if err != nil {
		return err
	}

	fmt.Printf("Decision recorded: %s\n", decision.ID)
	return nil
}

func runDecisionGet(cmd *cobra.Command, args []string) error {
	svc, err := getDecisionService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid decision ID: %w", err)
	}

	decision, err := svc.Get(id)
	if err != nil {
		return err
	}

	if decisionOutputJSON {
		data, _ := json.MarshalIndent(decision, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	fmt.Printf("Decision ID: %s\n", decision.ID)
	fmt.Printf("Agent: %s\n", decision.AgentID)
	fmt.Printf("Action: %s\n", decision.Action)
	fmt.Printf("Targets: %s\n", strings.Join(decision.Targets, ", "))
	fmt.Printf("Reason: %s\n", decision.Reason)
	fmt.Printf("Confidence: %.2f\n", decision.Confidence)
	fmt.Printf("Created: %s\n", decision.CreatedAt.Format(time.RFC3339))

	if decision.ExecutedAt != nil {
		fmt.Printf("Executed: %s\n", decision.ExecutedAt.Format(time.RFC3339))
	} else {
		fmt.Printf("Executed: (pending)\n")
	}

	if len(decision.Context) > 0 {
		contextJSON, _ := json.MarshalIndent(decision.Context, "", "  ")
		fmt.Printf("\nContext:\n%s\n", string(contextJSON))
	}

	if len(decision.Outcome) > 0 {
		outcomeJSON, _ := json.MarshalIndent(decision.Outcome, "", "  ")
		fmt.Printf("\nOutcome:\n%s\n", string(outcomeJSON))
	}

	return nil
}

func runDecisionList(cmd *cobra.Command, args []string) error {
	svc, err := getDecisionService()
	if err != nil {
		return err
	}

	// Build filter
	filter := &domain.DecisionFilter{
		AgentID: decisionAgent,
		Limit:   decisionLimit,
		Offset:  decisionOffset,
	}

	if decisionAction != "" {
		filter.Action = domain.DecisionAction(decisionAction)
	}

	if decisionExecuted != "all" {
		executed := decisionExecuted == "true"
		filter.Executed = &executed
	}

	decisions, err := svc.List(filter)
	if err != nil {
		return err
	}

	if decisionOutputJSON {
		data, _ := json.MarshalIndent(decisions, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	if len(decisions) == 0 {
		fmt.Println("No decisions found.")
		return nil
	}

	// Display as table
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tAGENT\tACTION\tTARGETS\tCONFIDENCE\tEXECUTED\tCREATED")
	fmt.Fprintln(w, strings.Repeat("-", 100))

	for _, decision := range decisions {
		targetsStr := strings.Join(decision.Targets, ",")
		if len(targetsStr) > 30 {
			targetsStr = targetsStr[:27] + "..."
		}

		executedStr := "No"
		if decision.ExecutedAt != nil {
			executedStr = "Yes"
		}

		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%.2f\t%s\t%s\n",
			decision.ID.String()[:8],
			decision.AgentID,
			decision.Action,
			targetsStr,
			decision.Confidence,
			executedStr,
			decision.CreatedAt.Format("2006-01-02"),
		)
	}

	w.Flush()
	fmt.Printf("\nTotal: %d decisions\n", len(decisions))

	return nil
}

func runDecisionUpdate(cmd *cobra.Command, args []string) error {
	svc, err := getDecisionService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid decision ID: %w", err)
	}

	// Parse outcome
	var outcome map[string]interface{}
	if err := json.Unmarshal([]byte(decisionOutcome), &outcome); err != nil {
		return fmt.Errorf("invalid outcome JSON: %w", err)
	}

	// Update decision
	if err := svc.Update(id, outcome); err != nil {
		return err
	}

	fmt.Printf("Decision updated: %s\n", id)
	return nil
}

func runDecisionDelete(cmd *cobra.Command, args []string) error {
	svc, err := getDecisionService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid decision ID: %w", err)
	}

	if err := svc.Delete(id); err != nil {
		return err
	}

	fmt.Printf("✓ Decision deleted: %s\n", id)
	return nil
}

func runDecisionStats(cmd *cobra.Command, args []string) error {
	svc, err := getDecisionService()
	if err != nil {
		return err
	}

	stats, err := svc.GetStats(decisionAgent)
	if err != nil {
		return err
	}

	if decisionOutputJSON {
		data, _ := json.MarshalIndent(stats, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	fmt.Printf("Decision Statistics for Agent: %s\n\n", decisionAgent)
	fmt.Printf("Total Decisions: %v\n", stats["total_decisions"])

	if byAction, ok := stats["by_action"].(map[string]int64); ok {
		fmt.Printf("\nBy Action:\n")
		fmt.Printf("  Watch: %d\n", byAction["watch"])
		fmt.Printf("  Buy:   %d\n", byAction["buy"])
		fmt.Printf("  Sell:  %d\n", byAction["sell"])
		fmt.Printf("  Hold:  %d\n", byAction["hold"])
	}

	fmt.Printf("\nRecent (Last 10):\n")
	fmt.Printf("  Executed: %v\n", stats["recent_executed"])
	fmt.Printf("  Pending:  %v\n", stats["recent_pending"])

	return nil
}
