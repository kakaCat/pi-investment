package cmd

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"text/tabwriter"

	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/middleware"
	"github.com/pi-investment/agent-os/internal/resource"
	"github.com/spf13/cobra"
	_ "github.com/lib/pq"
)

var resourceCmd = &cobra.Command{
	Use:   "resource",
	Short: "Resource management commands",
	Long:  `Manage resource quotas and usage for agent namespaces.`,
}

var quotaCmd = &cobra.Command{
	Use:   "quota",
	Short: "Query resource quotas",
	Long:  `Query resource quotas for agent namespaces.`,
}

var quotaListCmd = &cobra.Command{
	Use:     "list",
	Short:   "List all quotas",
	Long:    `List all resource quotas across all namespaces.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runQuotaList,
}

var quotaGetCmd = &cobra.Command{
	Use:     "get",
	Short:   "Get quotas for a namespace",
	Long:    `Get all resource quotas for a specific namespace.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runQuotaGet,
}

var quotaSetCmd = &cobra.Command{
	Use:     "set",
	Short:   "Set quota limit",
	Long:    `Set the limit value for a specific resource quota.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runQuotaSet,
}

var quotaResetCmd = &cobra.Command{
	Use:     "reset",
	Short:   "Reset quota usage",
	Long:    `Reset the usage counter for a specific resource quota to zero.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runQuotaReset,
}

var namespaceCmd = &cobra.Command{
	Use:   "namespace",
	Short: "Namespace management",
	Long:  `Manage agent namespaces.`,
}

var namespaceListCmd = &cobra.Command{
	Use:     "list",
	Short:   "List all namespaces",
	Long:    `List all registered agent namespaces.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runNamespaceList,
}

var usageCmd = &cobra.Command{
	Use:   "usage",
	Short: "View resource usage",
	Long:  `View resource usage history and statistics.`,
}

var usageHistoryCmd = &cobra.Command{
	Use:     "history",
	Short:   "View usage history",
	Long:    `View resource usage history for a namespace.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runUsageHistory,
}

var usageOverviewCmd = &cobra.Command{
	Use:     "overview",
	Short:   "View usage overview",
	Long:    `View quota usage overview for all namespaces.`,
	PreRunE: middleware.AuthMiddleware,
	RunE:    runUsageOverview,
}

var (
	flagAgent        string
	flagResourceType string
	flagLimit        int64
	flagHistoryLimit int
)

func init() {
	rootCmd.AddCommand(resourceCmd)

	// resource quota commands
	resourceCmd.AddCommand(quotaCmd)
	quotaCmd.AddCommand(quotaListCmd)
	quotaCmd.AddCommand(quotaGetCmd)
	quotaCmd.AddCommand(quotaSetCmd)
	quotaCmd.AddCommand(quotaResetCmd)

	quotaGetCmd.Flags().StringVar(&flagAgent, "agent", "", "Agent namespace name (required)")
	quotaGetCmd.MarkFlagRequired("agent")

	quotaSetCmd.Flags().StringVar(&flagAgent, "agent", "", "Agent namespace name (required)")
	quotaSetCmd.Flags().StringVar(&flagResourceType, "type", "", "Resource type (required)")
	quotaSetCmd.Flags().Int64Var(&flagLimit, "limit", 0, "New limit value (required)")
	quotaSetCmd.MarkFlagRequired("agent")
	quotaSetCmd.MarkFlagRequired("type")
	quotaSetCmd.MarkFlagRequired("limit")

	quotaResetCmd.Flags().StringVar(&flagAgent, "agent", "", "Agent namespace name (required)")
	quotaResetCmd.Flags().StringVar(&flagResourceType, "type", "", "Resource type (required)")
	quotaResetCmd.MarkFlagRequired("agent")
	quotaResetCmd.MarkFlagRequired("type")

	// resource namespace commands
	resourceCmd.AddCommand(namespaceCmd)
	namespaceCmd.AddCommand(namespaceListCmd)

	// resource usage commands
	resourceCmd.AddCommand(usageCmd)
	usageCmd.AddCommand(usageHistoryCmd)
	usageCmd.AddCommand(usageOverviewCmd)

	usageHistoryCmd.Flags().StringVar(&flagAgent, "agent", "", "Agent namespace name (required)")
	usageHistoryCmd.Flags().IntVar(&flagHistoryLimit, "limit", 20, "Number of history entries to show")
	usageHistoryCmd.MarkFlagRequired("agent")
}

// getResourceService creates a resource service with database connection
func getResourceService() (*resource.Service, *sql.DB, error) {
	cfg := config.Get()

	// Build DSN - omit password if empty to avoid libpq issues
	var dsn string
	if cfg.Database.Password != "" {
		dsn = fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
			cfg.Database.Host,
			cfg.Database.Port,
			cfg.Database.User,
			cfg.Database.Password,
			cfg.Database.DBName,
			cfg.Database.SSLMode,
		)
	} else {
		dsn = fmt.Sprintf("host=%s port=%d user=%s dbname=%s sslmode=%s",
			cfg.Database.Host,
			cfg.Database.Port,
			cfg.Database.User,
			cfg.Database.DBName,
			cfg.Database.SSLMode,
		)
	}

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	if err := db.Ping(); err != nil {
		db.Close()
		return nil, nil, fmt.Errorf("failed to ping database: %w", err)
	}

	repo := resource.NewRepository(db)
	svc := resource.NewService(repo)

	return svc, db, nil
}

func runQuotaList(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	views, err := svc.GetQuotaUsageOverview(ctx)
	if err != nil {
		return fmt.Errorf("failed to get quota overview: %w", err)
	}

	// Print table
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "NAMESPACE\tRESOURCE\tUSED\tLIMIT\tUSAGE%\tUNIT")
	fmt.Fprintln(w, "---------\t--------\t----\t-----\t------\t----")

	for _, v := range views {
		fmt.Fprintf(w, "%s\t%s\t%d\t%d\t%.2f%%\t%s\n",
			v.Namespace,
			v.ResourceType,
			v.UsedValue,
			v.LimitValue,
			v.UsagePercent,
			v.Unit,
		)
	}

	return w.Flush()
}

func runQuotaGet(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	quotas, err := svc.GetQuotas(ctx, flagAgent)
	if err != nil {
		return fmt.Errorf("failed to get quotas: %w", err)
	}

	if len(quotas) == 0 {
		fmt.Printf("No quotas found for namespace: %s\n", flagAgent)
		return nil
	}

	// Print table
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintf(w, "Quotas for namespace: %s\n\n", flagAgent)
	fmt.Fprintln(w, "RESOURCE\tUSED\tLIMIT\tUSAGE%\tUNIT\tSTATUS")
	fmt.Fprintln(w, "--------\t----\t-----\t------\t----\t------")

	for _, q := range quotas {
		status := "OK"
		if q.IsExceeded() {
			status = "EXCEEDED"
		} else if q.UsagePercent() >= 80 {
			status = "WARNING"
		}

		fmt.Fprintf(w, "%s\t%d\t%d\t%.2f%%\t%s\t%s\n",
			q.ResourceType,
			q.UsedValue,
			q.LimitValue,
			q.UsagePercent(),
			q.Unit,
			status,
		)
	}

	return w.Flush()
}

func runQuotaSet(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	if err := svc.SetQuotaLimit(ctx, flagAgent, flagResourceType, flagLimit); err != nil {
		return fmt.Errorf("failed to set quota limit: %w", err)
	}

	fmt.Printf("✓ Updated quota limit for %s/%s to %d\n", flagAgent, flagResourceType, flagLimit)
	return nil
}

func runQuotaReset(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	if err := svc.ResetQuotaUsage(ctx, flagAgent, flagResourceType); err != nil {
		return fmt.Errorf("failed to reset quota usage: %w", err)
	}

	fmt.Printf("✓ Reset usage counter for %s/%s to 0\n", flagAgent, flagResourceType)
	return nil
}

func runNamespaceList(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	namespaces, err := svc.ListNamespaces(ctx)
	if err != nil {
		return fmt.Errorf("failed to list namespaces: %w", err)
	}

	if len(namespaces) == 0 {
		fmt.Println("No namespaces found")
		return nil
	}

	// Print table
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "NAME\tDESCRIPTION\tCREATED")
	fmt.Fprintln(w, "----\t-----------\t-------")

	for _, ns := range namespaces {
		fmt.Fprintf(w, "%s\t%s\t%s\n",
			ns.Name,
			ns.Description,
			ns.CreatedAt.Format("2006-01-02 15:04"),
		)
	}

	return w.Flush()
}

func runUsageHistory(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	logs, err := svc.GetUsageHistory(ctx, flagAgent, flagHistoryLimit)
	if err != nil {
		return fmt.Errorf("failed to get usage history: %w", err)
	}

	if len(logs) == 0 {
		fmt.Printf("No usage history found for namespace: %s\n", flagAgent)
		return nil
	}

	// Print table
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintf(w, "Usage history for namespace: %s\n\n", flagAgent)
	fmt.Fprintln(w, "TIME\tRESOURCE\tOPERATION\tAMOUNT")
	fmt.Fprintln(w, "----\t--------\t---------\t------")

	for _, log := range logs {
		fmt.Fprintf(w, "%s\t%s\t%s\t%d\n",
			log.CreatedAt.Format("2006-01-02 15:04:05"),
			log.ResourceType,
			log.Operation,
			log.Amount,
		)
	}

	return w.Flush()
}

func runUsageOverview(cmd *cobra.Command, args []string) error {
	svc, db, err := getResourceService()
	if err != nil {
		return err
	}
	defer db.Close()

	ctx := context.Background()
	views, err := svc.GetQuotaUsageOverview(ctx)
	if err != nil {
		return fmt.Errorf("failed to get usage overview: %w", err)
	}

	// Print summary
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "Resource Usage Overview\n")
	fmt.Fprintln(w, "NAMESPACE\tRESOURCE\tUSED\tLIMIT\tUSAGE%\tUNIT\tSTATUS")
	fmt.Fprintln(w, "---------\t--------\t----\t-----\t------\t----\t------")

	for _, v := range views {
		status := "OK"
		if v.UsagePercent >= 100 {
			status = "CRITICAL"
		} else if v.UsagePercent >= 80 {
			status = "WARNING"
		}

		fmt.Fprintf(w, "%s\t%s\t%d\t%d\t%.2f%%\t%s\t%s\n",
			v.Namespace,
			v.ResourceType,
			v.UsedValue,
			v.LimitValue,
			v.UsagePercent,
			v.Unit,
			status,
		)
	}

	return w.Flush()
}
