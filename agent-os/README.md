# Agent OS

Agent OS is a centralized operating system layer for AI agents in the PI Investment system.

## Features

- **Scheduler**: Cron-like task scheduling with DAG dependencies
- **Resource Manager**: Quota management and resource tracking per agent namespace
- **Memory System**: Vector + BM25 hybrid search for agent memory
- - **Decision System**: Decision recording and audit trail
- **Permissions**: Role-based access control for agents
- **Event Bus**: System-wide event streaming

## Quick Start

### Installation

```bash
go build -o agent-os ./cmd/agent-os
```

### Configuration

Copy `config.yaml` and adjust settings:

```yaml
database:
  host: 127.0.0.1
  port: 5432
  dbname: agent_os
```

### Database Setup

```bash
# Create database
createdb agent_os

# Apply schema
psql -d agent_os -f schema.sql
```

### Run

```bash
# Show version
./agent-os version

# Show help
./agent-os help
```

## Architecture

```
┌─────────────────────────────────────────┐
│          agent-ts (AI Agent)            │
│  - Calls agent-os CLI commands          │
│  - Registers tasks via agent-os         │
└─────────────┬───────────────────────────┘
              │ CLI calls
              ↓
┌─────────────────────────────────────────┐
│         agent-os (This Project)         │
│  - Scheduler (task execution)           │
│  - Resource Manager (quotas)            │
│  - Memory System (hybrid search)        │
│  - Decision System (audit)              │
│  - Permissions (RBAC)                   │
└─────────────┬───────────────────────────┘
              │ SQL / Redis
              ↓
┌─────────────────────────────────────────┐
│     PostgreSQL + Redis (Storage)        │
└─────────────────────────────────────────┘
```

## Project Structure

```
agent-os/
├── cmd/
│   └── agent-os/          # Main CLI entry point
├── internal/
│   ├── cmd/               # Cobra commands
│   ├── config/            # Viper configuration
│   ├── scheduler/         # Task scheduling (TODO)
│   ├── resource/          # Resource management (TODO)
│   ├── memory/            # Memory system (TODO)
│   └── decision/          # Decision system (TODO)
├── pkg/
│   └── logger/            # Zap logger wrapper
├── schema.sql             # Database schema
├── config.yaml            # Configuration file
├── go.mod
└── README.md
```

## Development Roadmap

- [x] **WP-0**: Project scaffold (Day 1)
- [ ] **WP-1**: Scheduler module (Day 2-4)
- [ ] **WP-2**: Resource Manager (Day 2-4)
- [ ] **WP-3**: Memory System (Day 2-4)
- [ ] **WP-4**: agent-ts integration (Day 5-6)
- [ ] **WP-5**: Market Driver (Day 7-8)
- [ ] **WP-6**: Feishu Driver (Day 7-8)
- [ ] **WP-7**: Decision System (Day 7-8)
- [ ] **WP-8**: Permissions + Event Bus (Day 9-10)
- [ ] **WP-9**: Production optimization (Day 11)

## License

Proprietary - PI Investment System
