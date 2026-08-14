package main

import (
	"os"

	"github.com/pi-investment/agent-os/internal/cmd"
	_ "github.com/pi-investment/agent-os/internal/provider/feishu" // 自动注册 provider
)

func main() {
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
