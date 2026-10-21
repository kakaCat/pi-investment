# QuantSys V2 Architecture

## Overview

QuantSys V2 is a quantitative investment system built with a layered architecture that separates runtime infrastructure, external integrations, application services, and domain logic.

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Entry Points                             │
│  API Server │ WebSocket Server │ CLI │ Scheduler            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                          │
│  Services │ ML Pipeline │ Business Logic                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                              │
│  Repositories │ Pipeline │ Quant Library                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Infrastructure & Runtime                        │
│  Database │ Cache │ Events │ HTTP │ WebSocket               │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

### Runtime Layer (`runtime/`)

Core runtime infrastructure and cross-cutting concerns that support the entire application.

- **`runtime/events/`** - Event-driven architecture
  - `event_bus.py` - Pub-sub event bus for decoupled communication
  - `handlers.py` - Event handlers for system events
  
- **`runtime/messaging/`** - Message queue integration
  - `kafka_producer.py` - Kafka message producer
  - `kafka_consumer.py` - Kafka message consumer
  
- **`runtime/jobs/`** - Background job execution
  - `daily_snapshot_job.py` - Scheduled snapshot jobs
  
- **`runtime/scheduler/`** - Task scheduling
  - `scheduler.py` - Cron-based task scheduler
  
- **`runtime/cache/`** - Caching services
  - `cache_service.py` - Synchronous cache (Memory/Redis)
  - `async_cache_service.py` - Async cache with aioredis
  
- **`runtime/config/`** - Runtime configuration
  - `redis_config.py` - Redis connection configuration
  
- **`runtime/websocket/`** - WebSocket infrastructure
  - `connection_manager.py` - WebSocket connection lifecycle management

### Infrastructure Layer (`infrastructure/`)

External system integrations and low-level technical services.

- **`infrastructure/database/`** - Database infrastructure
  - `base_repository.py` - Synchronous database base class (psycopg2)
  - `async_base_repository.py` - Async database base class (asyncpg)
  
- **`infrastructure/http/`** - HTTP client infrastructure
  - `client.py` - Async HTTP client for external APIs (aiohttp)

### Application Layer

Business logic and application services that orchestrate domain operations.

- **`services/`** - Application services
  - `data_service.py` - Data aggregation and transformation
  - `cache_factory.py` - Cache instance factory
  - **`services/ml_pipeline/`** - Machine learning pipeline
    - `feature_engineering.py` - Feature extraction and engineering
    - `trainer.py` - Model training
    - `predictor.py` - Model prediction

- **`api/`** - HTTP API endpoints
  - `server.py` - Flask HTTP server
  - `server_websocket.py` - Flask-SocketIO WebSocket server
  - `routes/` - API route handlers
  
- **`cli/`** - Command-line interface
  - `main.py` - CLI entry point
  - Command modules for stock, order, position management

### Domain Layer

Core business domain logic and data access.

- **`core/`** - Core domain abstractions
  - `pipeline.py` - Pipeline pattern for data processing
  
- **`repositories/`** - Data access layer
  - Repository implementations for each domain entity
  - Extends base repositories from infrastructure layer
  
- **`quantlib/`** - Quantitative analysis library
  - Factor models, derivatives, risk management
  - Trading strategies and backtesting engine
  
- **`quant/stages/`** - Pipeline stages
  - Factor calculation, model prediction, backtesting stages

## Key Design Patterns

### 1. Dual Anti-Corruption Layer

```
Entry Points (API/CLI/Scheduler)
        ↓
Application Services
        ↓
Repositories
        ↓
Database
```

This pattern ensures:
- Entry points don't directly access repositories
- Services encapsulate business logic
- Repositories abstract data access
- Changes in one layer don't cascade to others

### 2. Pipeline Pattern

Composable stages for data processing:

```python
pipeline = Pipeline([
    FactorCalculationStage(),
    ModelPredictionStage(),
    BacktestStage()
])
result = pipeline.execute(data)
```

### 3. Event-Driven Architecture

Decoupled communication via event bus:

```python
# Publisher
event_bus.publish("trade.executed", {"symbol": "AAPL", "qty": 100})

# Subscriber
@event_bus.subscribe("trade.executed")
def handle_trade(event):
    # Handle trade execution
    pass
```

### 4. Repository Pattern

Abstraction over data access:

```python
class StockRepository(BaseRepository):
    def get_by_symbol(self, symbol: str) -> Stock:
        # Data access logic
        pass
```

## Technology Stack

### Core Technologies
- **Python 3.14+** - Primary language
- **PostgreSQL** - Primary database
- **Redis** - Caching and session storage
- **Kafka** - Message queue (optional)

### Web Framework
- **Flask** - HTTP API server
- **Flask-SocketIO** - WebSocket server

### Database Access
- **psycopg2** - Synchronous PostgreSQL driver
- **asyncpg** - Async PostgreSQL driver
- **aioredis** - Async Redis client

### Testing
- **pytest** - Test framework
- **pytest-cov** - Coverage reporting
- **pytest-asyncio** - Async test support

## Database Architecture

### Database Separation

- **Production Database**: `quant_investment`
- **Test Database**: `quant_test` (auto-switched during pytest)

### Safety Mechanisms

Three-layer safety checks prevent accidental production database access during tests:

1. **conftest.py** - Validates database configuration at pytest startup
2. **base_repository.py** - Runtime check for synchronous connections
3. **async_base_repository.py** - Runtime check for async connections

All layers verify database name ends with `_test` when pytest is detected.

## Scripts Organization

### `/scripts/migrations/`
Database schema migrations and management tools.

### `/scripts/maintenance/`
Data backfilling, cleanup, and maintenance operations.

### `/scripts/examples/`
Example scripts demonstrating system features.

### `/scripts/tools/`
Development tools for analysis, benchmarking, and code maintenance.

### `/scripts/diagnostics/`
Diagnostic and troubleshooting scripts.

## Backward Compatibility

During the infrastructure restructure, legacy import paths are maintained via shim files:

```python
# Old location: events/event_bus.py
from runtime.events.event_bus import *  # noqa: F401, F403
```

This allows gradual migration without breaking existing code.

## Development Workflow

### Running the System

```bash
# HTTP API
python api/server.py

# WebSocket API
python api/server_websocket.py

# CLI
python cli/main.py stock search --q 平安

# All services
python start_all.py
```

### Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_pipeline.py -v

# View coverage
pytest --cov=. --cov-report=html
```

### Code Quality Standards

- Test coverage target: > 80% for core modules
- All tests must pass before committing
- No `_backup`, `_v2`, `_old`, `_new` parallel files
- Delete obsolete code after references are removed
- Example code goes to `docs/examples/`

## Future Considerations

### Scalability
- Horizontal scaling via load balancers
- Database read replicas for query optimization
- Redis cluster for distributed caching

### Observability
- Structured logging with correlation IDs
- Metrics collection (Prometheus)
- Distributed tracing (OpenTelemetry)

### Resilience
- Circuit breakers for external API calls
- Retry mechanisms with exponential backoff
- Graceful degradation strategies

---

**Last Updated**: 2026-05-25  
**Version**: 2.0.0  
**Maintainers**: QuantSys V2 Team
