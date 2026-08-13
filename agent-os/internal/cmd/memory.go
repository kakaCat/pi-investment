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

var memoryCmd = &cobra.Command{
	Use:   "memory",
	Short: "Memory management commands",
	Long:  `Manage agent memories: write, read, search, and organize memories.`,
}

var memoryWriteCmd = &cobra.Command{
	Use:   "write",
	Short: "Write a new memory",
	Long:  `Create a new memory entry with content, category, importance, and tags.`,
	RunE:  runMemoryWrite,
}

var memoryReadCmd = &cobra.Command{
	Use:   "read <id>",
	Short: "Read a memory by ID",
	Args:  cobra.ExactArgs(1),
	RunE:  runMemoryRead,
}

var memorySearchCmd = &cobra.Command{
	Use:   "search",
	Short: "Search memories",
	Long:  `Search memories using text query with optional filters.`,
	RunE:  runMemorySearch,
}

var memoryListCmd = &cobra.Command{
	Use:   "list",
	Short: "List memories",
	RunE:  runMemoryList,
}

var memoryDeleteCmd = &cobra.Command{
	Use:   "delete <id>",
	Short: "Delete a memory by ID",
	Args:  cobra.ExactArgs(1),
	RunE:  runMemoryDelete,
}

var memoryTagCmd = &cobra.Command{
	Use:   "tag",
	Short: "Manage memory tags",
}

var memoryTagAddCmd = &cobra.Command{
	Use:   "add <memory-id> <tag1> [tag2...]",
	Short: "Add tags to a memory",
	Args:  cobra.MinimumNArgs(2),
	RunE:  runMemoryTagAdd,
}

var memoryTagRemoveCmd = &cobra.Command{
	Use:   "remove <memory-id> <tag1> [tag2...]",
	Short: "Remove tags from a memory",
	Args:  cobra.MinimumNArgs(2),
	RunE:  runMemoryTagRemove,
}

// Flags
var (
	memoryNamespace  string
	memoryContent    string
	memoryCategory   string
	memoryImportance float64
	memoryTags       []string
	memoryMetadata   string
	memoryQuery      string
	memoryCategories []string
	memoryMinImport  float64
	memoryLimit      int
	memoryOffset     int
	memoryHybrid     bool
	memoryOutputJSON bool
)

func init() {
	rootCmd.AddCommand(memoryCmd)

	// Subcommands
	memoryCmd.AddCommand(memoryWriteCmd)
	memoryCmd.AddCommand(memoryReadCmd)
	memoryCmd.AddCommand(memorySearchCmd)
	memoryCmd.AddCommand(memoryListCmd)
	memoryCmd.AddCommand(memoryDeleteCmd)
	memoryCmd.AddCommand(memoryTagCmd)

	memoryTagCmd.AddCommand(memoryTagAddCmd)
	memoryTagCmd.AddCommand(memoryTagRemoveCmd)

	// Write flags
	memoryWriteCmd.Flags().StringVar(&memoryNamespace, "namespace", "system", "Namespace ID or name")
	memoryWriteCmd.Flags().StringVar(&memoryContent, "content", "", "Memory content (required)")
	memoryWriteCmd.Flags().StringVar(&memoryCategory, "category", "project", "Memory category (user, feedback, project, reference)")
	memoryWriteCmd.Flags().Float64Var(&memoryImportance, "importance", 0.5, "Importance (0.0-1.0)")
	memoryWriteCmd.Flags().StringSliceVar(&memoryTags, "tags", []string{}, "Comma-separated tags")
	memoryWriteCmd.Flags().StringVar(&memoryMetadata, "metadata", "{}", "Metadata as JSON")
	memoryWriteCmd.MarkFlagRequired("content")

	// Search flags
	memorySearchCmd.Flags().StringVar(&memoryNamespace, "namespace", "system", "Namespace ID or name")
	memorySearchCmd.Flags().StringVar(&memoryQuery, "query", "", "Search query (required)")
	memorySearchCmd.Flags().StringSliceVar(&memoryCategories, "categories", []string{}, "Filter by categories")
	memorySearchCmd.Flags().StringSliceVar(&memoryTags, "tags", []string{}, "Filter by tags")
	memorySearchCmd.Flags().Float64Var(&memoryMinImport, "min-importance", 0.0, "Minimum importance")
	memorySearchCmd.Flags().IntVar(&memoryLimit, "limit", 10, "Maximum results")
	memorySearchCmd.Flags().IntVar(&memoryOffset, "offset", 0, "Result offset")
	memorySearchCmd.Flags().BoolVar(&memoryHybrid, "hybrid", false, "Use hybrid search (BM25 + Vector)")
	memorySearchCmd.Flags().BoolVar(&memoryOutputJSON, "json", false, "Output as JSON")
	memorySearchCmd.MarkFlagRequired("query")

	// List flags
	memoryListCmd.Flags().StringVar(&memoryNamespace, "namespace", "system", "Namespace ID or name")
	memoryListCmd.Flags().StringVar(&memoryCategory, "category", "", "Filter by category")
	memoryListCmd.Flags().StringSliceVar(&memoryTags, "tags", []string{}, "Filter by tags")
	memoryListCmd.Flags().IntVar(&memoryLimit, "limit", 20, "Maximum results")
	memoryListCmd.Flags().IntVar(&memoryOffset, "offset", 0, "Result offset")
	memoryListCmd.Flags().BoolVar(&memoryOutputJSON, "json", false, "Output as JSON")

	// Read flags
	memoryReadCmd.Flags().BoolVar(&memoryOutputJSON, "json", false, "Output as JSON")

	// Global namespace flag for tag commands
	memoryTagAddCmd.Flags().StringVar(&memoryNamespace, "namespace", "system", "Namespace ID or name")
	memoryTagRemoveCmd.Flags().StringVar(&memoryNamespace, "namespace", "system", "Namespace ID or name")
}

func getMemoryService() (domain.MemoryService, error) {
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

	repo := repository.NewMemoryRepository(db)
	embeddingService := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embeddingService)

	return svc, nil
}

func getNamespaceID(nameOrID string) (uuid.UUID, error) {
	// Try parsing as UUID first
	id, err := uuid.Parse(nameOrID)
	if err == nil {
		return id, nil
	}

	// Otherwise, look up by name
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
		return uuid.Nil, fmt.Errorf("failed to connect to database: %w", err)
	}
	defer db.Close()

	var namespaceID uuid.UUID
	err = db.QueryRow("SELECT id FROM namespaces WHERE name = $1", nameOrID).Scan(&namespaceID)
	if err != nil {
		return uuid.Nil, fmt.Errorf("namespace not found: %s", nameOrID)
	}

	return namespaceID, nil
}

func runMemoryWrite(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	namespaceID, err := getNamespaceID(memoryNamespace)
	if err != nil {
		return err
	}

	// Parse metadata
	var metadata map[string]any
	if memoryMetadata != "" && memoryMetadata != "{}" {
		if err := json.Unmarshal([]byte(memoryMetadata), &metadata); err != nil {
			return fmt.Errorf("invalid metadata JSON: %w", err)
		}
	}

	// Create memory
	memory, err := svc.Write(namespaceID, memoryContent, memoryCategory, memoryImportance, memoryTags, metadata)
	if err != nil {
		return err
	}

	fmt.Printf("✓ Memory created: %s\n", memory.ID)
	fmt.Printf("  Category: %s\n", memory.Category)
	fmt.Printf("  Importance: %.2f\n", memory.Importance)
	if len(memory.Tags) > 0 {
		fmt.Printf("  Tags: %s\n", strings.Join(memory.Tags, ", "))
	}

	return nil
}

func runMemoryRead(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid memory ID: %w", err)
	}

	memory, err := svc.Read(id)
	if err != nil {
		return err
	}

	if memoryOutputJSON {
		data, _ := json.MarshalIndent(memory, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	fmt.Printf("Memory ID: %s\n", memory.ID)
	fmt.Printf("Namespace: %s\n", memory.NamespaceID)
	fmt.Printf("Category: %s\n", memory.Category)
	fmt.Printf("Importance: %.2f\n", memory.Importance)
	fmt.Printf("Created: %s\n", memory.CreatedAt.Format(time.RFC3339))
	fmt.Printf("Updated: %s\n", memory.UpdatedAt.Format(time.RFC3339))
	fmt.Printf("Accessed: %d times\n", memory.AccessedCount)
	if len(memory.Tags) > 0 {
		fmt.Printf("Tags: %s\n", strings.Join(memory.Tags, ", "))
	}
	fmt.Printf("\nContent:\n%s\n", memory.Content)

	return nil
}

func runMemorySearch(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	namespaceID, err := getNamespaceID(memoryNamespace)
	if err != nil {
		return err
	}

	query := &domain.SearchQuery{
		Query:         memoryQuery,
		NamespaceID:   namespaceID,
		Categories:    memoryCategories,
		MinImportance: memoryMinImport,
		Limit:         memoryLimit,
		Offset:        memoryOffset,
	}

	var results []*domain.SearchResult
	if memoryHybrid {
		results, err = svc.SearchHybrid(query)
	} else {
		results, err = svc.Search(query)
	}

	if err != nil {
		return err
	}

	if memoryOutputJSON {
		data, _ := json.MarshalIndent(results, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	if len(results) == 0 {
		fmt.Println("No memories found.")
		return nil
	}

	fmt.Printf("Found %d memories:\n\n", len(results))

	for i, result := range results {
		memory := result.Memory
		fmt.Printf("[%d] %s (score: %.4f)\n", i+1, memory.ID, result.Score)
		fmt.Printf("    Category: %s | Importance: %.2f | Created: %s\n",
			memory.Category,
			memory.Importance,
			memory.CreatedAt.Format("2006-01-02"),
		)
		if len(memory.Tags) > 0 {
			fmt.Printf("    Tags: %s\n", strings.Join(memory.Tags, ", "))
		}

		// Truncate content for display
		content := memory.Content
		if len(content) > 200 {
			content = content[:197] + "..."
		}
		fmt.Printf("    %s\n\n", content)
	}

	return nil
}

func runMemoryList(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	namespaceID, err := getNamespaceID(memoryNamespace)
	if err != nil {
		return err
	}

	var memories []*domain.Memory

	// Filter by category or tags
	if memoryCategory != "" {
		memories, err = svc.ListByCategory(namespaceID, memoryCategory, memoryLimit)
	} else if len(memoryTags) > 0 {
		memories, err = svc.ListByTags(namespaceID, memoryTags, memoryLimit)
	} else {
		memories, err = svc.List(namespaceID, memoryLimit, memoryOffset)
	}

	if err != nil {
		return err
	}

	if memoryOutputJSON {
		data, _ := json.MarshalIndent(memories, "", "  ")
		fmt.Println(string(data))
		return nil
	}

	if len(memories) == 0 {
		fmt.Println("No memories found.")
		return nil
	}

	// Display as table
	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "ID\tCATEGORY\tIMPORTANCE\tCREATED\tCONTENT")
	fmt.Fprintln(w, strings.Repeat("-", 80))

	for _, memory := range memories {
		content := memory.Content
		if len(content) > 50 {
			content = content[:47] + "..."
		}
		content = strings.ReplaceAll(content, "\n", " ")

		fmt.Fprintf(w, "%s\t%s\t%.2f\t%s\t%s\n",
			memory.ID.String()[:8],
			memory.Category,
			memory.Importance,
			memory.CreatedAt.Format("2006-01-02"),
			content,
		)
	}

	w.Flush()
	fmt.Printf("\nTotal: %d memories\n", len(memories))

	return nil
}

func runMemoryDelete(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid memory ID: %w", err)
	}

	if err := svc.Delete(id); err != nil {
		return err
	}

	fmt.Printf("✓ Memory deleted: %s\n", id)
	return nil
}

func runMemoryTagAdd(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid memory ID: %w", err)
	}

	tags := args[1:]
	if err := svc.AddTags(id, tags); err != nil {
		return err
	}

	fmt.Printf("✓ Tags added to memory %s: %s\n", id, strings.Join(tags, ", "))
	return nil
}

func runMemoryTagRemove(cmd *cobra.Command, args []string) error {
	svc, err := getMemoryService()
	if err != nil {
		return err
	}

	id, err := uuid.Parse(args[0])
	if err != nil {
		return fmt.Errorf("invalid memory ID: %w", err)
	}

	tags := args[1:]
	if err := svc.RemoveTags(id, tags); err != nil {
		return err
	}

	fmt.Printf("✓ Tags removed from memory %s: %s\n", id, strings.Join(tags, ", "))
	return nil
}
