# Runtime Infrastructure Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize QuantSys V2 so runtime infrastructure, application services, external integrations, and quant calculation code have clear ownership while preserving import compatibility during migration.

**Architecture:** Introduce `runtime/` for jobs, scheduler, messaging, events, websocket runtime, and cache runtime; introduce `infrastructure/` for cross-cutting HTTP/config/DB/observability utilities; move application ML pipeline under `services/ml_pipeline/`; keep `quantlib/` as pure quant calculation and `brokers/` as trading broker integration. Existing public import paths remain as thin shims until callers are updated.

**Tech Stack:** Python 3, Flask, pytest, psycopg2, Redis/aioredis, confluent-kafka, existing QuantSys V2 packages.

---

## File Structure

Create:
- `runtime/__init__.py`
- `runtime/events/__init__.py`
- `runtime/events/event_bus.py`
- `runtime/events/handlers.py`
- `runtime/messaging/__init__.py`
- `runtime/messaging/kafka_producer.py`
- `runtime/messaging/kafka_consumer.py`
- `runtime/jobs/__init__.py`
- `runtime/jobs/daily_snapshot_job.py`
- `runtime/scheduler/__init__.py`
- `runtime/scheduler/service.py`
- `runtime/cache/__init__.py`
- `runtime/cache/cache_service.py`
- `runtime/cache/async_cache_service.py`
- `runtime/websocket/__init__.py`
- `runtime/websocket/connection_manager.py`
- `infrastructure/__init__.py`
- `infrastructure/http/__init__.py`
- `infrastructure/http/async_http_client.py`
- `infrastructure/config/__init__.py`
- `infrastructure/config/cache_factory.py`
- `infrastructure/config/redis_config.py`
- `infrastructure/db/__init__.py`
- `services/ml_pipeline/__init__.py`
- `services/ml_pipeline/feature_engineering.py`
- `services/ml_pipeline/trainer.py`
- `services/ml_pipeline/predictor.py`

Modify:
- `events/*.py`, `messaging/*.py`, `jobs/*.py`, `services/scheduler.py`, `services/cache_service.py`, `services/async_cache_service.py`, `api/websocket.py`, `adapters/async_http_client.py`, `config/*.py`, `ml/*.py`: convert to compatibility shims.
- `api/server_websocket.py`, `api/routes/scheduler.py`, `api/routes/benchmarks.py`, `api/ml_routes.py`, `api/routes/training.py`, `api/routes/health.py`, `api/routes/analysis.py`, `quantlib/engine/mixins/ml_mixin.py`, scripts and tests: update imports to canonical paths.
- `README.md`, `docs/README.md`, `AGENTS.md`: update structure and ownership docs.
- `tests/test_event_bus.py`, `tests/test_websocket.py`, `tests/test_scheduler.py`, `tests/test_cache_service.py`, `tests/test_redis_cache.py`, ML route/pipeline tests: update assertions/imports as needed.

Delete later, after all canonical imports pass and shims have a deprecation window:
- Top-level `events/`, `messaging/`, `jobs/`, `ml/`, `adapters/`, and old cache/scheduler service modules.

Do not move in this phase:
- `brokers/`: keep top-level broker integration.
- `quantlib/`: keep pure quant calculation modules.
- `repositories/`: keep DB repository layer.
- `data_sources/`: keep data source connectors.

---

### Task 1: Add Runtime Package And Move Events

**Files:**
- Create: `runtime/__init__.py`
- Create: `runtime/events/__init__.py`
- Move content to: `runtime/events/event_bus.py`
- Move content to: `runtime/events/handlers.py`
- Modify shim: `events/__init__.py`
- Modify shim: `events/event_bus.py`
- Modify shim: `events/handlers.py`
- Modify: `api/server_websocket.py`
- Test: `tests/test_event_bus.py`
- Test: `tests/test_websocket.py`

- [ ] **Step 1: Write import compatibility tests**

Add or update tests to assert both paths resolve the same global event bus:

```python
from events.event_bus import event_bus as legacy_event_bus
from runtime.events.event_bus import event_bus as runtime_event_bus

def test_event_bus_legacy_import_matches_runtime_import():
    assert legacy_event_bus is runtime_event_bus
```

- [ ] **Step 2: Run event tests and verify baseline**

Run: `pytest tests/test_event_bus.py tests/test_websocket.py -q`

Expected before implementation: import from `runtime.events` fails if new tests are added.

- [ ] **Step 3: Move event implementation**

Move current implementation from `events/event_bus.py` to `runtime/events/event_bus.py`.
Move current implementation from `events/handlers.py` to `runtime/events/handlers.py`.
Inside `runtime/events/handlers.py`, change:

```python
from events.event_bus import event_bus
```

to:

```python
from runtime.events.event_bus import event_bus
```

- [ ] **Step 4: Add legacy shims**

`events/event_bus.py`:

```python
from runtime.events.event_bus import EventBus, event_bus

__all__ = ["EventBus", "event_bus"]
```

`events/handlers.py`:

```python
from runtime.events.handlers import *  # noqa: F401,F403
```

`events/__init__.py`:

```python
from runtime.events import EventBus, event_bus

__all__ = ["EventBus", "event_bus"]
```

- [ ] **Step 5: Update canonical imports**

Update `api/server_websocket.py` and tests to import from `runtime.events.*`.
Leave legacy imports only in shim tests.

- [ ] **Step 6: Run verification**

Run: `pytest tests/test_event_bus.py tests/test_websocket.py -q`

Expected: all selected tests pass.

---

### Task 2: Move Messaging Into Runtime

**Files:**
- Create: `runtime/messaging/__init__.py`
- Move content to: `runtime/messaging/kafka_producer.py`
- Move content to: `runtime/messaging/kafka_consumer.py`
- Modify shim: `messaging/__init__.py`
- Modify shim: `messaging/kafka_producer.py`
- Modify shim: `messaging/kafka_consumer.py`

- [ ] **Step 1: Add import tests**

Create or update a focused test to import:

```python
from runtime.messaging.kafka_producer import KafkaProducerClient, get_producer
from runtime.messaging.kafka_consumer import KafkaMessageConsumer
from messaging.kafka_producer import KafkaProducerClient as LegacyProducer

def test_messaging_legacy_import_matches_runtime_class():
    assert LegacyProducer is KafkaProducerClient
```

- [ ] **Step 2: Fix broken messaging package export**

Current `messaging/__init__.py` imports missing names (`KafkaConsumerClient`, `MessageHandler`, `EventStore`). Replace with exports that exist in current code:

```python
from runtime.messaging.kafka_producer import KafkaProducerClient, get_producer
from runtime.messaging.kafka_consumer import KafkaMessageConsumer

__all__ = ["KafkaProducerClient", "get_producer", "KafkaMessageConsumer"]
```

- [ ] **Step 3: Move producer and consumer implementations**

Move code to `runtime/messaging/`.
Keep old files as shims:

```python
from runtime.messaging.kafka_producer import *  # noqa: F401,F403
```

and:

```python
from runtime.messaging.kafka_consumer import *  # noqa: F401,F403
```

- [ ] **Step 4: Run verification**

Run: `python3 -m py_compile runtime/messaging/*.py messaging/*.py`

Expected: command exits 0.

---

### Task 3: Move Jobs And Scheduler Into Runtime

**Files:**
- Create: `runtime/jobs/__init__.py`
- Move content to: `runtime/jobs/daily_snapshot_job.py`
- Create: `runtime/scheduler/__init__.py`
- Move content to: `runtime/scheduler/service.py`
- Modify shim: `jobs/__init__.py`
- Modify shim: `jobs/daily_snapshot_job.py`
- Modify shim: `services/scheduler.py`
- Modify: `api/routes/scheduler.py`
- Modify: `api/routes/benchmarks.py`
- Modify: `start_all.py`
- Test: `tests/test_scheduler.py`
- Test: `tests/test_benchmark_service.py`

- [ ] **Step 1: Add scheduler compatibility test**

In `tests/test_scheduler.py`, add:

```python
from runtime.scheduler.service import SchedulerService as RuntimeSchedulerService
from services.scheduler import SchedulerService as LegacySchedulerService

def test_scheduler_legacy_import_matches_runtime_import():
    assert LegacySchedulerService is RuntimeSchedulerService
```

- [ ] **Step 2: Move scheduler implementation**

Move `services/scheduler.py` implementation to `runtime/scheduler/service.py`.
Change `services/scheduler.py` into:

```python
from runtime.scheduler.service import *  # noqa: F401,F403
```

- [ ] **Step 3: Move jobs implementation**

Move `jobs/daily_snapshot_job.py` to `runtime/jobs/daily_snapshot_job.py`.
Convert old job module to shim.

- [ ] **Step 4: Update canonical imports**

Update:
- `api/routes/scheduler.py`
- `api/routes/benchmarks.py`
- `start_all.py`
- tests

to import `SchedulerService` from `runtime.scheduler.service`.

- [ ] **Step 5: Run verification**

Run: `pytest tests/test_scheduler.py tests/test_benchmark_service.py -q`

Expected: selected tests pass.

---

### Task 4: Move Runtime Cache And Config

**Files:**
- Create: `runtime/cache/__init__.py`
- Move content to: `runtime/cache/cache_service.py`
- Move content to: `runtime/cache/async_cache_service.py`
- Create: `infrastructure/config/__init__.py`
- Move content to: `infrastructure/config/cache_factory.py`
- Move content to: `infrastructure/config/redis_config.py`
- Modify shim: `services/cache_service.py`
- Modify shim: `services/async_cache_service.py`
- Modify shim: `config/cache_factory.py`
- Modify shim: `config/redis_config.py`
- Test: `tests/test_cache_service.py`
- Test: `tests/test_redis_cache.py`

- [ ] **Step 1: Add cache import compatibility tests**

Add assertions that legacy service imports match runtime cache imports:

```python
from runtime.cache.cache_service import CacheService as RuntimeCacheService
from services.cache_service import CacheService as LegacyCacheService

def test_cache_legacy_import_matches_runtime_import():
    assert LegacyCacheService is RuntimeCacheService
```

- [ ] **Step 2: Move cache implementations**

Move `services/cache_service.py` to `runtime/cache/cache_service.py`.
Move `services/async_cache_service.py` to `runtime/cache/async_cache_service.py`.
Create shims at old paths.

- [ ] **Step 3: Move cache config**

Move `config/cache_factory.py` and `config/redis_config.py` into `infrastructure/config/`.
Create shims at old paths.

- [ ] **Step 4: Update canonical imports**

Update tests and scripts to canonical runtime/config imports.

- [ ] **Step 5: Run verification**

Run: `pytest tests/test_cache_service.py tests/test_redis_cache.py -q`

Expected: selected tests pass.

---

### Task 5: Extract WebSocket Runtime

**Files:**
- Create: `runtime/websocket/__init__.py`
- Create: `runtime/websocket/connection_manager.py`
- Modify: `api/websocket.py`
- Modify: `api/server_websocket.py`
- Modify: `runtime/events/handlers.py`
- Test: `tests/test_websocket.py`

- [ ] **Step 1: Add websocket runtime import test**

Assert connection manager APIs are available from both paths:

```python
from api.websocket import get_connection_manager as legacy_get_manager
from runtime.websocket.connection_manager import get_connection_manager as runtime_get_manager

def test_websocket_legacy_import_matches_runtime_import():
    assert legacy_get_manager is runtime_get_manager
```

- [ ] **Step 2: Move connection manager implementation**

Move connection manager classes/functions from `api/websocket.py` to `runtime/websocket/connection_manager.py`.
Keep `api/websocket.py` as API compatibility shim.

- [ ] **Step 3: Update runtime event handlers**

Change `runtime/events/handlers.py` to import connection manager from `runtime.websocket.connection_manager`.

- [ ] **Step 4: Run verification**

Run: `pytest tests/test_websocket.py -q`

Expected: selected tests pass.

---

### Task 6: Move Application ML Pipeline

**Files:**
- Create: `services/ml_pipeline/__init__.py`
- Move content to: `services/ml_pipeline/feature_engineering.py`
- Move content to: `services/ml_pipeline/trainer.py`
- Move content to: `services/ml_pipeline/predictor.py`
- Modify shim: `ml/__init__.py`
- Modify shim: `ml/feature_engineering.py`
- Modify shim: `ml/trainer.py`
- Modify shim: `ml/predictor.py`
- Modify: `api/ml_routes.py`
- Modify: `api/routes/training.py`
- Modify: `api/routes/analysis.py`
- Modify: `api/routes/health.py`
- Modify: `scripts/ml_demo.py`
- Modify: `quantlib/engine/mixins/ml_mixin.py`

- [ ] **Step 1: Add ML pipeline compatibility test**

Add a small test:

```python
from services.ml_pipeline.trainer import MLTrainer as RuntimeMLTrainer
from ml.trainer import MLTrainer as LegacyMLTrainer

def test_ml_legacy_import_matches_service_import():
    assert LegacyMLTrainer is RuntimeMLTrainer
```

- [ ] **Step 2: Move ML pipeline implementation**

Move top-level `ml/*.py` implementation to `services/ml_pipeline/`.
Convert old `ml` package into shims.

- [ ] **Step 3: Update canonical imports**

Update API routes, scripts, and `quantlib/engine/mixins/ml_mixin.py` to `services.ml_pipeline.*`.
Do not change `quantlib/ml/`; it remains quant calculation ML.

- [ ] **Step 4: Run verification**

Run: `python3 -m py_compile services/ml_pipeline/*.py ml/*.py api/ml_routes.py api/routes/training.py api/routes/analysis.py api/routes/health.py quantlib/engine/mixins/ml_mixin.py`

Expected: command exits 0.

---

### Task 7: Move Infrastructure HTTP Client

**Files:**
- Create: `infrastructure/http/__init__.py`
- Move content to: `infrastructure/http/async_http_client.py`
- Modify shim: `adapters/async_http_client.py`

- [ ] **Step 1: Add import compatibility test**

```python
from infrastructure.http.async_http_client import AsyncHttpClient as RuntimeAsyncHttpClient
from adapters.async_http_client import AsyncHttpClient as LegacyAsyncHttpClient

def test_http_client_legacy_import_matches_infrastructure_import():
    assert LegacyAsyncHttpClient is RuntimeAsyncHttpClient
```

- [ ] **Step 2: Move implementation**

Move top-level adapter implementation into `infrastructure/http/`.
Keep old file as shim.

- [ ] **Step 3: Run verification**

Run: `python3 -m py_compile infrastructure/http/async_http_client.py adapters/async_http_client.py`

Expected: command exits 0.

---

### Task 8: Resolve Database Directory State

**Files:**
- Restore or relocate tracked files:
  - `database/async_connection_pool.py`
  - `database/schema/signals_schema.sql`
- Preferred target:
  - `infrastructure/db/async_connection_pool.py`
  - `infrastructure/db/schema/signals_schema.sql`
- Modify imports/tests if any.

- [ ] **Step 1: Inspect tracked database files**

Run:

```bash
git show HEAD:database/async_connection_pool.py | sed -n '1,120p'
git show HEAD:database/schema/signals_schema.sql | sed -n '1,120p'
```

- [ ] **Step 2: Restore to infrastructure path**

Create `infrastructure/db/async_connection_pool.py` and `infrastructure/db/schema/signals_schema.sql` from HEAD content.
Create optional compatibility shims only if any imports still reference `database.*`.

- [ ] **Step 3: Update status**

Run: `git status --short database infrastructure/db`

Expected: old database files appear deleted, new infrastructure files appear added.

---

### Task 9: Reorganize Scripts And Examples

**Files:**
- Move scripts into:
  - `scripts/db/`
  - `scripts/data/`
  - `scripts/ops/`
  - `scripts/dev/`
  - `scripts/diagnostics/`
- Move Python example files from `docs/examples/` into `examples/advanced/` or `examples/quantlib/`.
- Update `docs/examples/README.md`.

- [ ] **Step 1: Classify scripts**

Suggested mapping:
- `scripts/db/`: `create_*.sql`, `migrate_tables.py`, `migrations/`, `verify_ningde_signal.sql`
- `scripts/data/`: `backfill_*`, `init_stocks.py`, `generate_*signals*`
- `scripts/ops/`: `init_redis.py`, `cleanup_test_data.py`, `delete_invalid_executions.py`, `benchmark_cache.py`, `retrain_pipeline.py`, `test_trade_flow.py`
- `scripts/dev/`: `fix_imports.py`, `split_server.py`, `analyze_queries.py`
- `scripts/diagnostics/`: keep current diagnostics scripts

- [ ] **Step 2: Move files and update references**

Use `git mv` for tracked files.
Run `rg` for old paths and update docs/scripts.

- [ ] **Step 3: Verify script syntax**

Run: `python3 -m py_compile $(find scripts -name '*.py' -print)`

Expected: command exits 0.

---

### Task 10: Update Documentation And Ownership Rules

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `AGENTS.md`
- Modify: relevant docs with old `quant.*`, `ml.*`, `events.*`, `services.scheduler`, `services.cache_service` examples.

- [ ] **Step 1: Update README structure**

Replace old `quant/` structure with:

```text
├── runtime/
├── infrastructure/
├── quantlib/
├── brokers/
├── services/
```

- [ ] **Step 2: Update canonical import examples**

Use:
- `quantlib.*` for quant calculation
- `services.ml_pipeline.*` for app ML pipeline
- `runtime.scheduler.service` for scheduler
- `runtime.events.event_bus` for events
- `runtime.messaging.*` for Kafka
- `runtime.cache.*` for cache

- [ ] **Step 3: Update AGENTS ownership**

Add directory ownership rules for `runtime/`, `infrastructure/`, and `brokers/`.

- [ ] **Step 4: Run doc reference check**

Run:

```bash
rg -n "from quant\\.|from ml\\.|from events\\.|from messaging\\.|from jobs\\.|from services\\.scheduler|from services\\.cache_service|from adapters\\.async_http_client" README.md docs AGENTS.md
```

Expected: only archived docs or intentional compatibility notes mention old paths.

---

### Task 11: Final Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest \
  tests/test_event_bus.py \
  tests/test_websocket.py \
  tests/test_scheduler.py \
  tests/test_cache_service.py \
  tests/test_redis_cache.py \
  tests/test_benchmark_service.py \
  tests/test_cli_commands.py \
  -q
```

Expected: selected tests pass.

- [ ] **Step 2: Run import compile check**

Run:

```bash
python3 -m py_compile \
  $(find runtime infrastructure services/ml_pipeline -name '*.py' -print) \
  events/*.py messaging/*.py jobs/*.py ml/*.py adapters/*.py \
  services/scheduler.py services/cache_service.py services/async_cache_service.py
```

Expected: command exits 0.

- [ ] **Step 3: Clean generated artifacts**

Run:

```bash
rm -rf htmlcov .coverage .pytest_cache
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
```

- [ ] **Step 4: Review git status**

Run: `git status --short`

Expected: only intended moves, docs updates, shims, and pre-existing unrelated user edits remain.

