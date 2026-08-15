.PHONY: help build test clean run docker-build docker-up docker-down docker-logs deploy

# Default target
help:
	@echo "Agent OS - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  build          Build the application binary"
	@echo "  test           Run all tests"
	@echo "  test-coverage  Run tests with coverage"
	@echo "  bench          Run benchmarks"
	@echo "  clean          Clean build artifacts"
	@echo "  run            Run the application locally"
	@echo "  docker-build   Build Docker images"
	@echo "  docker-up      Start Docker services"
	@echo "  docker-down    Stop Docker services"
	@echo "  docker-logs    View Docker logs"
	@echo "  deploy         Deploy with Docker Compose"
	@echo "  lint           Run linters"
	@echo "  fmt            Format code"

# Build the application
build:
	@echo "🔨 Building agent-os..."
	@go build -o bin/agent-os ./cmd/agent-os
	@echo "✅ Build complete: bin/agent-os"

# Run tests
test:
	@echo "🧪 Running tests..."
	@go test -v -race ./...

# Run tests with coverage
test-coverage:
	@echo "🧪 Running tests with coverage..."
	@go test -v -race -coverprofile=coverage.txt -covermode=atomic ./...
	@go tool cover -html=coverage.txt -o coverage.html
	@echo "✅ Coverage report: coverage.html"

# Run benchmarks
bench:
	@echo "⚡ Running benchmarks..."
	@go test -bench=. -benchmem ./...

# Clean build artifacts
clean:
	@echo "🧹 Cleaning..."
	@rm -rf bin/
	@rm -f coverage.txt coverage.html
	@rm -f *.log
	@echo "✅ Clean complete"

# Run the application locally
run: build
	@echo "▶️  Starting agent-os..."
	@./bin/agent-os serve

# Build Docker images
docker-build:
	@echo "🐳 Building Docker images..."
	@docker-compose build

# Start Docker services
docker-up:
	@echo "🐳 Starting Docker services..."
	@docker-compose up -d
	@echo "✅ Services started"
	@echo "   HTTP API:    http://localhost:8080"
	@echo "   WebSocket:   ws://localhost:8081"
	@echo "   Metrics:     http://localhost:9090/metrics"
	@echo "   Prometheus:  http://localhost:9091"
	@echo "   Grafana:     http://localhost:3000"

# Stop Docker services
docker-down:
	@echo "🐳 Stopping Docker services..."
	@docker-compose down

# View Docker logs
docker-logs:
	@docker-compose logs -f

# Deploy with script
deploy:
	@./scripts/deploy.sh

# Run linters
lint:
	@echo "🔍 Running linters..."
	@golangci-lint run ./...

# Format code
fmt:
	@echo "✨ Formatting code..."
	@go fmt ./...
	@gofmt -s -w .
	@echo "✅ Formatting complete"

# Run all checks before commit
pre-commit: fmt lint test
	@echo "✅ All checks passed!"
