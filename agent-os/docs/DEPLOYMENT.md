# Agent OS Deployment Guide

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Go 1.21+ (for local development)
- Make (optional, for shortcuts)

### Deploy with Docker Compose

```bash
# Clone the repository
git clone <repository-url>
cd agent-os

# Deploy all services
./scripts/deploy.sh

# Or using make
make deploy
```

The deploy script will:
1. Create `.env` from `.env.example` if it doesn't exist
2. Build Docker images
3. Start all services (PostgreSQL, Agent OS, Prometheus, Grafana)
4. Perform health checks

### Service URLs

After deployment, access the following endpoints:

- **HTTP API**: http://localhost:8080
- **WebSocket**: ws://localhost:8081/ws/events
- **Metrics**: http://localhost:9090/metrics
- **Prometheus**: http://localhost:9091
- **Grafana**: http://localhost:3000 (default: admin/admin)

## Architecture

```
┌─────────────┐     ┌─────────────┐
│   Grafana   │────▶│ Prometheus  │
│   :3000     │     │   :9091     │
└─────────────┘     └──────┬──────┘
                           │ scrape
                           ▼
                    ┌─────────────┐
                    │  Agent OS   │
                    │  :8080      │◀── HTTP API
                    │  :8081      │◀── WebSocket
                    │  :9090      │◀── Metrics
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ PostgreSQL  │
                    │   :5432     │
                    └─────────────┘
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Database
POSTGRES_DB=agent_os
POSTGRES_USER=agent
POSTGRES_PASSWORD=your_secure_password

# Server
HTTP_PORT=8080
WS_PORT=8081
METRICS_PORT=9090

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=your_grafana_password
```

### Custom Configuration

Edit `config/config.yaml` for application-specific settings:

```yaml
server:
  host: 0.0.0.0
  port: 8080
  ws_port: 8081
  metrics_port: 9090

database:
  host: postgres
  port: 5432
  name: agent_os
  user: agent
  max_connections: 100

logging:
  level: info
  format: json
```

## Management Commands

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# Restart services
docker-compose restart

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f agent-os

# Destroy everything (including volumes)
docker-compose down -v

# Rebuild and restart
docker-compose up -d --build
```

### Using Makefile

```bash
# Build locally
make build

# Run tests
make test

# Run with coverage
make test-coverage

# Run benchmarks
make bench

# Deploy with Docker
make deploy

# Start Docker services
make docker-up

# Stop Docker services
make docker-down

# View logs
make docker-logs
```

## Local Development

### Build and Run Locally

```bash
# Install dependencies
go mod download

# Build
make build

# Run locally (requires PostgreSQL)
./bin/agent-os serve
```

### Run Tests

```bash
# All tests
make test

# With coverage
make test-coverage

# Benchmarks
make bench

# Specific package
go test -v ./internal/metrics
```

## Database Management

### Initialize Database

The database is automatically initialized on first startup using `scripts/init-db.sql`.

### Manual Migration

```bash
# Connect to database
docker exec -it agent-os-db psql -U agent -d agent_os

# Run migration
\i /docker-entrypoint-initdb.d/init.sql
```

### Backup Database

```bash
# Backup
docker exec agent-os-db pg_dump -U agent agent_os > backup.sql

# Restore
docker exec -i agent-os-db psql -U agent agent_os < backup.sql
```

## Monitoring

### Prometheus

Access Prometheus at http://localhost:9091

**Useful Queries:**

```promql
# Request rate
rate(agent_os_api_requests_total[5m])

# Command latency (95th percentile)
histogram_quantile(0.95, rate(agent_os_command_execution_duration_seconds_bucket[5m]))

# Error rate
rate(agent_os_api_requests_total{status=~"5.."}[5m])

# Active agents
agent_os_scheduler_tasks_active
```

### Grafana

Access Grafana at http://localhost:3000 (default: admin/admin)

Datasource is pre-configured to connect to Prometheus.

**Create Dashboard:**
1. Click "+" → "Dashboard"
2. Add panel
3. Use metrics like `agent_os_command_execution_total`

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs

# Check specific service
docker-compose logs agent-os
```

### Database Connection Issues

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Verify database is ready
docker exec agent-os-db pg_isready -U agent

# Connect manually
docker exec -it agent-os-db psql -U agent -d agent_os
```

### Metrics Not Appearing

```bash
# Check metrics endpoint
curl http://localhost:9090/metrics

# Verify Prometheus scraping
curl http://localhost:9091/api/v1/targets
```

## Production Deployment

### Security Checklist

- [ ] Change default passwords in `.env`
- [ ] Use secrets management (e.g., Docker secrets, HashiCorp Vault)
- [ ] Enable HTTPS/TLS for external endpoints
- [ ] Configure firewall rules
- [ ] Set up log rotation
- [ ] Enable database backups
- [ ] Configure resource limits

### Resource Limits

Add to `docker-compose.yml`:

```yaml
services:
  agent-os:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### High Availability

For production, consider:

- Multiple agent-os replicas behind a load balancer
- PostgreSQL replication (primary + replicas)
- Persistent volumes for data
- External monitoring and alerting
- Automated backups

## Health Checks

### Application Health

```bash
# Health endpoint
curl http://localhost:9090/health

# Metrics endpoint
curl http://localhost:9090/metrics
```

### Service Health via Docker

```bash
# Check health status
docker inspect agent-os-app | grep -A 10 Health
```

## Upgrade Procedure

```bash
# 1. Backup database
docker exec agent-os-db pg_dump -U agent agent_os > backup-$(date +%Y%m%d).sql

# 2. Pull latest code
git pull

# 3. Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# 4. Verify health
docker-compose ps
curl http://localhost:9090/health
```

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Review metrics: http://localhost:9090/metrics
- Inspect Prometheus: http://localhost:9091
