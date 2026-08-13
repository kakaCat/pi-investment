package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"text/tabwriter"

	"github.com/spf13/cobra"
)

var dataCmd = &cobra.Command{
	Use:   "data",
	Short: "Market data commands",
	Long:  `Query market data: quotes, K-lines, and market status.`,
}

var dataQuoteCmd = &cobra.Command{
	Use:   "quote",
	Short: "Get real-time quote",
	Long:  `Get real-time quote for a stock symbol.`,
	RunE:  runDataQuote,
}

var dataKlineCmd = &cobra.Command{
	Use:   "kline",
	Short: "Get K-line data",
	Long:  `Get historical K-line (OHLCV) data for a stock symbol.`,
	RunE:  runDataKline,
}

var dataMarketStatusCmd = &cobra.Command{
	Use:   "market-status",
	Short: "Get market status",
	Long:  `Check if the market is currently open or closed.`,
	RunE:  runDataMarketStatus,
}

// Flags
var (
	dataSymbol    string
	dataPeriod    string
	dataStartDate string
	dataEndDate   string
	dataOutputJSON bool
)

func init() {
	rootCmd.AddCommand(dataCmd)

	// Subcommands
	dataCmd.AddCommand(dataQuoteCmd)
	dataCmd.AddCommand(dataKlineCmd)
	dataCmd.AddCommand(dataMarketStatusCmd)

	// Quote flags
	dataQuoteCmd.Flags().StringVar(&dataSymbol, "symbol", "", "Stock symbol (e.g., 600519.SH)")
	dataQuoteCmd.Flags().BoolVar(&dataOutputJSON, "json", false, "Output as JSON")
	dataQuoteCmd.MarkFlagRequired("symbol")

	// Kline flags
	dataKlineCmd.Flags().StringVar(&dataSymbol, "symbol", "", "Stock symbol (e.g., 600519.SH)")
	dataKlineCmd.Flags().StringVar(&dataPeriod, "period", "daily", "Period: daily, weekly, monthly")
	dataKlineCmd.Flags().StringVar(&dataStartDate, "start", "20240101", "Start date (YYYYMMDD)")
	dataKlineCmd.Flags().StringVar(&dataEndDate, "end", "20240131", "End date (YYYYMMDD)")
	dataKlineCmd.Flags().BoolVar(&dataOutputJSON, "json", false, "Output as JSON")
	dataKlineCmd.MarkFlagRequired("symbol")

	// Market status flags
	dataMarketStatusCmd.Flags().BoolVar(&dataOutputJSON, "json", false, "Output as JSON")
}

// Market Driver Response Types
type QuoteResponse struct {
	Symbol    string  `json:"symbol"`
	Name      string  `json:"name"`
	Price     float64 `json:"price"`
	Change    float64 `json:"change"`
	ChangePct float64 `json:"change_pct"`
	Volume    float64 `json:"volume"`
	Amount    float64 `json:"amount"`
	High      float64 `json:"high"`
	Low       float64 `json:"low"`
	Open      float64 `json:"open"`
	PreClose  float64 `json:"pre_close"`
}

type KlineData struct {
	Symbol string  `json:"symbol"`
	Date   string  `json:"date"`
	Open   float64 `json:"open"`
	High   float64 `json:"high"`
	Low    float64 `json:"low"`
	Close  float64 `json:"close"`
	Volume float64 `json:"volume"`
	Amount float64 `json:"amount"`
}

type KlineResponse struct {
	Symbol string      `json:"symbol"`
	Period string      `json:"period"`
	Count  int         `json:"count"`
	Data   []KlineData `json:"data"`
}

type MarketStatusResponse struct {
	IsOpen    bool   `json:"is_open"`
	Status    string `json:"status"`
	Reason    string `json:"reason,omitempty"`
	Session   string `json:"session,omitempty"`
	Timestamp int64  `json:"timestamp"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// callMarketDriver calls the Python market-driver CLI
func callMarketDriver(args ...string) ([]byte, error) {
	// Try multiple paths to find market-driver
	var driverPath string

	// Option 1: Relative to current working directory
	cwd, _ := os.Getwd()
	candidates := []string{
		filepath.Join(cwd, "drivers", "market-driver", "main.py"),
		filepath.Join(cwd, "agent-os", "drivers", "market-driver", "main.py"),
	}

	// Option 2: Relative to executable
	if execPath, err := os.Executable(); err == nil {
		execDir := filepath.Dir(execPath)
		candidates = append(candidates,
			filepath.Join(execDir, "drivers", "market-driver", "main.py"),
			filepath.Join(filepath.Dir(execDir), "drivers", "market-driver", "main.py"),
		)
	}

	// Find the first existing path
	for _, path := range candidates {
		if _, err := os.Stat(path); err == nil {
			driverPath = path
			break
		}
	}

	if driverPath == "" {
		return nil, fmt.Errorf("market-driver not found. Searched paths:\n%s", strings.Join(candidates, "\n"))
	}

	// Call Python driver with warnings suppressed
	cmd := exec.Command("python3", append([]string{"-W", "ignore", driverPath}, args...)...)

	// Only capture stdout (JSON output), let stderr go to terminal
	output, err := cmd.Output()

	return output, err
}

func runDataQuote(cmd *cobra.Command, args []string) error {
	// Call market-driver quote
	output, err := callMarketDriver("quote", "--symbol", dataSymbol)
	if err != nil {
		// Try to parse error response
		var errResp ErrorResponse
		if jsonErr := json.Unmarshal(output, &errResp); jsonErr == nil {
			return fmt.Errorf("%s: %s", errResp.Error, errResp.Message)
		}
		return fmt.Errorf("failed to get quote: %w\n%s", err, string(output))
	}

	// Parse response
	var quote QuoteResponse
	if err := json.Unmarshal(output, &quote); err != nil {
		return fmt.Errorf("failed to parse quote response: %w", err)
	}

	// Output
	if dataOutputJSON {
		fmt.Println(string(output))
	} else {
		printQuote(quote)
	}

	return nil
}

func runDataKline(cmd *cobra.Command, args []string) error {
	// Call market-driver kline
	output, err := callMarketDriver(
		"kline",
		"--symbol", dataSymbol,
		"--period", dataPeriod,
		"--start", dataStartDate,
		"--end", dataEndDate,
	)
	if err != nil {
		// Try to parse error response
		var errResp ErrorResponse
		if jsonErr := json.Unmarshal(output, &errResp); jsonErr == nil {
			return fmt.Errorf("%s: %s", errResp.Error, errResp.Message)
		}
		return fmt.Errorf("failed to get kline: %w\n%s", err, string(output))
	}

	// Parse response
	var klineResp KlineResponse
	if err := json.Unmarshal(output, &klineResp); err != nil {
		return fmt.Errorf("failed to parse kline response: %w", err)
	}

	// Output
	if dataOutputJSON {
		fmt.Println(string(output))
	} else {
		printKline(klineResp)
	}

	return nil
}

func runDataMarketStatus(cmd *cobra.Command, args []string) error {
	// Call market-driver market-status
	output, err := callMarketDriver("market-status")
	if err != nil {
		return fmt.Errorf("failed to get market status: %w\n%s", err, string(output))
	}

	// Parse response
	var status MarketStatusResponse
	if err := json.Unmarshal(output, &status); err != nil {
		return fmt.Errorf("failed to parse market status response: %w", err)
	}

	// Output
	if dataOutputJSON {
		fmt.Println(string(output))
	} else {
		printMarketStatus(status)
	}

	return nil
}

// Print functions

func printQuote(quote QuoteResponse) {
	fmt.Printf("=== Quote: %s (%s) ===\n\n", quote.Symbol, quote.Name)

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintf(w, "Price:\t%.2f\n", quote.Price)
	fmt.Fprintf(w, "Change:\t%.2f (%.2f%%)\n", quote.Change, quote.ChangePct)
	fmt.Fprintf(w, "Open:\t%.2f\n", quote.Open)
	fmt.Fprintf(w, "High:\t%.2f\n", quote.High)
	fmt.Fprintf(w, "Low:\t%.2f\n", quote.Low)
	fmt.Fprintf(w, "Pre Close:\t%.2f\n", quote.PreClose)
	fmt.Fprintf(w, "Volume:\t%.0f\n", quote.Volume)
	fmt.Fprintf(w, "Amount:\t%.2f\n", quote.Amount)
	w.Flush()
}

func printKline(klineResp KlineResponse) {
	fmt.Printf("=== K-line: %s (%s) ===\n", klineResp.Symbol, klineResp.Period)
	fmt.Printf("Total: %d records\n\n", klineResp.Count)

	if len(klineResp.Data) == 0 {
		fmt.Println("No data")
		return
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintf(w, "Date\tOpen\tHigh\tLow\tClose\tVolume\tAmount\n")
	fmt.Fprintf(w, "----\t----\t----\t---\t-----\t------\t------\n")

	// Show first 10 and last 5 records
	showCount := 10
	if len(klineResp.Data) <= 15 {
		showCount = len(klineResp.Data)
	}

	for i := 0; i < showCount && i < len(klineResp.Data); i++ {
		k := klineResp.Data[i]
		fmt.Fprintf(w, "%s\t%.2f\t%.2f\t%.2f\t%.2f\t%.0f\t%.2f\n",
			k.Date, k.Open, k.High, k.Low, k.Close, k.Volume, k.Amount)
	}

	if len(klineResp.Data) > 15 {
		fmt.Fprintf(w, "...\t...\t...\t...\t...\t...\t...\n")
		for i := len(klineResp.Data) - 5; i < len(klineResp.Data); i++ {
			k := klineResp.Data[i]
			fmt.Fprintf(w, "%s\t%.2f\t%.2f\t%.2f\t%.2f\t%.0f\t%.2f\n",
				k.Date, k.Open, k.High, k.Low, k.Close, k.Volume, k.Amount)
		}
	}

	w.Flush()
}

func printMarketStatus(status MarketStatusResponse) {
	fmt.Printf("=== Market Status ===\n\n")

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)

	statusStr := "OPEN"
	if !status.IsOpen {
		statusStr = "CLOSED"
	}
	fmt.Fprintf(w, "Status:\t%s\n", statusStr)

	if status.Session != "" {
		fmt.Fprintf(w, "Session:\t%s\n", status.Session)
	}

	if status.Reason != "" {
		fmt.Fprintf(w, "Reason:\t%s\n", status.Reason)
	}

	w.Flush()
}
