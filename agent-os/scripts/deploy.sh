#!/bin/bash
# Deploy Agent OS using Docker Compose

set -e

echo "🚀 Deploying Agent OS"
echo "===================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please review and update passwords!"
    echo ""
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "📦 Building images..."
docker-compose build

echo ""
echo "🔄 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check service health
SERVICES=("agent-os-db" "agent-os-app" "agent-os-prometheus")
ALL_HEALTHY=true

for service in "${SERVICES[@]}"; do
    if docker ps --filter "name=$service" --filter "health=healthy" | grep -q "$service"; then
        echo "  ✓ $service is healthy"
    else
        echo "  ⚠️  $service is not healthy yet"
        ALL_HEALTHY=false
    fi
done

echo ""
if [ "$ALL_HEALTHY" = true ]; then
    echo "✅ All services are healthy!"
else
    echo "⚠️  Some services are not healthy yet. Check with: docker-compose ps"
fi

echo ""
echo "🌐 Service URLs:"
echo "  HTTP API:    http://localhost:8080"
echo "  WebSocket:   ws://localhost:8081"
echo "  Metrics:     http://localhost:9090/metrics"
echo "  Prometheus:  http://localhost:9091"
echo "  Grafana:     http://localhost:3000 (admin/admin)"
echo ""
echo "📋 Useful commands:"
echo "  View logs:   docker-compose logs -f"
echo "  Stop:        docker-compose stop"
echo "  Restart:     docker-compose restart"
echo "  Destroy:     docker-compose down -v"
echo ""
