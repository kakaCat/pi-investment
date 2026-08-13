package main

import (
	"os"

	"github.com/pi-investment/agent-os/internal/cmd"
)

func main() {
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
