# WP-15: quantsys-v2 Scheduler Integration with Agent OS

**Priority**: P1  
**Duration**: 3 days  
**Dependencies**: WP-12 (Agent OS Scheduler HTTP API must be completed first)  
**Execution Model**: Haiku  
**Parallel**: Can run in parallel with WP-13/WP-14

## 1. Overview

### Objective
Migrate quantsys-v2's custom scheduler to Agent OS Scheduler, eliminating the third parallel scheduler and unifying all scheduling through Agent OS.

### Current State
- quantsys-v2 has custom scheduler in `services/scheduler_service.py` with 30+ jobs
- Uses `apscheduler` library with custom `SchedulerOrchestrator`
- Jobs stored in PostgreSQL `scheduler_jobs` and `scheduler_job_runs` tables
- Runs in FastAPI lifespan (3 threads: scheduler + executor + reaper)
- No integration with Agent OS

### Target State
- All quantsys-v2 scheduled jobs registered in Agent OS Scheduler via HTTP API
- quantsys-v2 provides webhook endpoints to receive job execution callbacks
- Legacy scheduler code removed or marked deprecated
- Jobs continue to run on same schedule without disruption
- Zero downtime migration with gray release support

## 2. Architecture Design

### 2.1 Integration Pattern

```
Agent OS Scheduler (cron engine)
         ↓ HTTP POST (webhook)
quantsys-v2 Webhook Receiver
         ↓ dispatch by job_type
Job Handler (existing business logic)
         ↓ write results
PostgreSQL (scheduler_job_runs)
```

### 2.2 Job Registration Flow

```python
# On FastAPI startup (lifespan)
async def register_jobs_to_agent_os():
    jobs = [
        {
            "name": "kline_update",
            "schedule": "40 17 * * 1-5",  # 工作日 17:40
            "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
            "enabled": True,
            "metadata": {"job_type": "kline_update", "timeout": 600}
        },
        # ... 30+ more jobs
    ]
    
    for job in jobs:
        response = await agent_os_client.register_job(job)
        logger.info(f"Registered {job['name']}: {response['id']}")
```

### 2.3 Webhook Execution Flow

```python
@app.post("/internal/scheduler/webhook")
async def scheduler_webhook(payload: WebhookPayload):
    """
    Receive job execution trigger from Agent OS Scheduler.
    
    Payload format:
    {
        "job_id": "uuid",
        "job_name": "kline_update",
        "trigger_time": "2026-08-15T17:40:00Z",
        "metadata": {"job_type": "kline_update", "timeout": 600}
    }
    """
    job_type = payload.metadata.get("job_type")
    
    # Dispatch to handler
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        return {"status": "error", "message": f"Unknown job_type: {job_type}"}
    
    # Execute in background
    background_tasks.add_task(execute_job, handler, payload)
    
    return {"status": "accepted", "job_id": payload.job_id}


async def execute_job(handler, payload):
    """Execute job and report results back to Agent OS."""
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    try:
        result = await handler(payload.metadata)
        status = "success"
        error_msg = None
    except Exception as e:
        logger.exception(f"Job {payload.job_name} failed")
        status = "failed"
        error_msg = str(e)
        result = None
    
    end_time = datetime.now(timezone.utc)
    
    # Write to local database
    await scheduler_repo.create_job_run({
        "id": run_id,
        "job_id": payload.job_id,
        "status": status,
        "started_at": start_time,
        "completed_at": end_time,
        "error_message": error_msg,
        "result": result
    })
    
    # Report back to Agent OS
    await agent_os_client.report_job_result(payload.job_id, run_id, {
        "status": status,
        "started_at": start_time.isoformat(),
        "completed_at": end_time.isoformat(),
        "error_message": error_msg
    })
```

## 3. Implementation Plan

### Day 1: Agent OS Client + Webhook Receiver

#### 3.1 Create Agent OS Client
**File**: `quantsys-v2/services/agent_os_client.py`

```python
"""Agent OS HTTP client for Scheduler and Skill Hub."""
import httpx
from typing import Dict, Any, Optional
from datetime import datetime


class AgentOSClient:
    """Client for Agent OS HTTP API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self.client.aclose()
    
    # ==================== Scheduler API ====================
    
    async def register_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a scheduled job.
        
        Args:
            job: {
                "name": str,
                "schedule": str,  # cron expression
                "webhook_url": str,
                "enabled": bool,
                "metadata": dict
            }
        
        Returns:
            {"id": "uuid", "name": str, ...}
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/jobs",
            json=job
        )
        response.raise_for_status()
        return response.json()
    
    async def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job details."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/scheduler/jobs/{job_id}"
        )
        response.raise_for_status()
        return response.json()
    
    async def list_jobs(self) -> list[Dict[str, Any]]:
        """List all registered jobs."""
        response = await self.client.get(
            f"{self.base_url}/api/v1/scheduler/jobs"
        )
        response.raise_for_status()
        return response.json()
    
    async def update_job(self, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update job configuration."""
        response = await self.client.put(
            f"{self.base_url}/api/v1/scheduler/jobs/{job_id}",
            json=updates
        )
        response.raise_for_status()
        return response.json()
    
    async def delete_job(self, job_id: str) -> None:
        """Delete a job."""
        response = await self.client.delete(
            f"{self.base_url}/api/v1/scheduler/jobs/{job_id}"
        )
        response.raise_for_status()
    
    async def report_job_result(
        self, 
        job_id: str, 
        run_id: str, 
        result: Dict[str, Any]
    ) -> None:
        """
        Report job execution result back to Agent OS.
        
        Args:
            job_id: Job UUID
            run_id: Run UUID
            result: {
                "status": "success" | "failed",
                "started_at": ISO timestamp,
                "completed_at": ISO timestamp,
                "error_message": str | null
            }
        """
        response = await self.client.post(
            f"{self.base_url}/api/v1/scheduler/jobs/{job_id}/runs/{run_id}",
            json=result
        )
        response.raise_for_status()


# Global singleton
_agent_os_client: Optional[AgentOSClient] = None


def get_agent_os_client() -> AgentOSClient:
    """Get global Agent OS client instance."""
    global _agent_os_client
    if _agent_os_client is None:
        _agent_os_client = AgentOSClient()
    return _agent_os_client
```

#### 3.2 Create Webhook Receiver
**File**: `quantsys-v2/api/internal/scheduler_webhook.py`

```python
"""Internal webhook endpoint for Agent OS Scheduler callbacks."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Callable
from datetime import datetime, timezone
import uuid
import logging

from services.agent_os_client import get_agent_os_client
from repositories.scheduler_repository import SchedulerRepository

logger = logging.getLogger(__name__)
router = APIRouter()


class WebhookPayload(BaseModel):
    """Webhook payload from Agent OS Scheduler."""
    job_id: str
    job_name: str
    trigger_time: str
    metadata: Dict[str, Any]


# Job handler registry
JOB_HANDLERS: Dict[str, Callable] = {}


def register_job_handler(job_type: str):
    """Decorator to register job handlers."""
    def decorator(func: Callable):
        JOB_HANDLERS[job_type] = func
        return func
    return decorator


@router.post("/webhook")
async def scheduler_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks
):
    """
    Receive job execution trigger from Agent OS Scheduler.
    
    This endpoint is called by Agent OS when a scheduled job should run.
    It dispatches to the appropriate handler and returns immediately.
    """
    job_type = payload.metadata.get("job_type")
    
    if not job_type:
        raise HTTPException(status_code=400, detail="Missing job_type in metadata")
    
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Unknown job_type: {job_type}")
    
    logger.info(f"Received webhook for job {payload.job_name} ({job_type})")
    
    # Execute in background
    background_tasks.add_task(
        execute_job,
        handler,
        payload
    )
    
    return {
        "status": "accepted",
        "job_id": payload.job_id,
        "job_name": payload.job_name
    }


async def execute_job(handler: Callable, payload: WebhookPayload):
    """
    Execute job handler and report results.
    
    This runs in a FastAPI background task to avoid blocking the webhook response.
    """
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    logger.info(f"Executing job {payload.job_name} (run_id={run_id})")
    
    try:
        # Call handler with metadata
        result = await handler(payload.metadata)
        status = "success"
        error_msg = None
        logger.info(f"Job {payload.job_name} succeeded: {result}")
    except Exception as e:
        logger.exception(f"Job {payload.job_name} failed")
        status = "failed"
        error_msg = str(e)
        result = None
    
    end_time = datetime.now(timezone.utc)
    
    # Write to local database
    scheduler_repo = SchedulerRepository()
    await scheduler_repo.create_job_run({
        "id": run_id,
        "job_id": payload.job_id,
        "status": status,
        "started_at": start_time,
        "completed_at": end_time,
        "error_message": error_msg,
        "result": result
    })
    
    # Report back to Agent OS
    agent_os_client = get_agent_os_client()
    try:
        await agent_os_client.report_job_result(payload.job_id, run_id, {
            "status": status,
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "error_message": error_msg
        })
    except Exception as e:
        logger.error(f"Failed to report job result to Agent OS: {e}")
```

#### 3.3 Register Router
**File**: `quantsys-v2/api/app.py`

```python
# Add import
from api.internal.scheduler_webhook import router as scheduler_webhook_router

# Register internal router
app.include_router(
    scheduler_webhook_router,
    prefix="/internal/scheduler",
    tags=["internal"]
)
```

**Deliverables**:
- [ ] `services/agent_os_client.py` created with full Scheduler API client
- [ ] `api/internal/scheduler_webhook.py` created with webhook receiver
- [ ] Router registered in `api/app.py`
- [ ] Manual test: `curl -X POST http://127.0.0.1:5001/internal/scheduler/webhook -H "Content-Type: application/json" -d '{"job_id":"test","job_name":"test","trigger_time":"2026-08-15T00:00:00Z","metadata":{"job_type":"unknown"}}'` returns 404

---

### Day 2: Job Handlers + Registration

#### 3.4 Migrate Existing Job Handlers
**File**: `quantsys-v2/services/scheduler_handlers.py`

Extract existing job logic from `SchedulerService` into standalone async functions:

```python
"""Job handlers for Agent OS Scheduler webhooks."""
from typing import Dict, Any
import logging

from services.kline_service import KlineService
from services.pool_service import PoolService
from services.financial_statement_service import FinancialStatementService
from services.chip_distribution_service import ChipDistributionService
from services.signal_service import SignalService
from api.internal.scheduler_webhook import register_job_handler

logger = logging.getLogger(__name__)


@register_job_handler("kline_update")
async def handle_kline_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update daily K-line data for all stocks.
    
    Original: SchedulerService.kline_update_job
    Schedule: 工作日 17:40
    """
    logger.info("Starting kline_update job")
    kline_service = KlineService()
    
    result = await kline_service.update_all_stocks()
    
    return {
        "updated_count": result["updated"],
        "failed_count": result["failed"],
        "skipped_count": result["skipped"]
    }


@register_job_handler("pool_refresh")
async def handle_pool_refresh(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Refresh dynamic stock pools.
    
    Original: SchedulerService.pool_refresh_job
    Schedule: 每日 02:00
    """
    logger.info("Starting pool_refresh job")
    pool_service = PoolService()
    
    # Refresh all dynamic pools
    pools = await pool_service.list_pools(pool_type="dynamic")
    results = []
    
    for pool in pools:
        try:
            result = await pool_service.refresh_pool(pool["id"])
            results.append({
                "pool_id": pool["id"],
                "pool_name": pool["name"],
                "status": "success",
                "added": result["added"],
                "removed": result["removed"]
            })
        except Exception as e:
            logger.error(f"Failed to refresh pool {pool['name']}: {e}")
            results.append({
                "pool_id": pool["id"],
                "pool_name": pool["name"],
                "status": "failed",
                "error": str(e)
            })
    
    return {"pools": results}


@register_job_handler("financial_statement_update")
async def handle_financial_statement_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update quarterly financial statements.
    
    Original: SchedulerService.financial_statement_job
    Schedule: 每周六 20:00
    """
    logger.info("Starting financial_statement_update job")
    fs_service = FinancialStatementService()
    
    result = await fs_service.update_all_stocks()
    
    return {
        "updated_count": result["updated"],
        "failed_count": result["failed"]
    }


@register_job_handler("chip_distribution_update")
async def handle_chip_distribution_update(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate chip distribution for all stocks.
    
    Original: SchedulerService.chip_distribution_job
    Schedule: 每日 18:00
    """
    logger.info("Starting chip_distribution_update job")
    chip_service = ChipDistributionService()
    
    result = await chip_service.calculate_all_stocks()
    
    return {
        "calculated_count": result["calculated"],
        "failed_count": result["failed"]
    }


@register_job_handler("signal_scan")
async def handle_signal_scan(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan for trading signals.
    
    Original: SchedulerService.signal_scan_job
    Schedule: 工作日 09:00 (买入信号扫描)
    """
    logger.info("Starting signal_scan job")
    signal_service = SignalService()
    
    scan_type = metadata.get("scan_type", "buy")  # "buy" or "sell"
    strategy_ids = metadata.get("strategy_ids")  # Optional filter
    
    result = await signal_service.scan_signals(
        scan_type=scan_type,
        strategy_ids=strategy_ids
    )
    
    return {
        "signal_count": result["signal_count"],
        "strategy_count": result["strategy_count"]
    }


# Add more handlers for remaining 25+ jobs...
# Each handler follows the same pattern:
# 1. Extract parameters from metadata
# 2. Call existing service method
# 3. Return structured result dict
```

#### 3.5 Create Job Registration Script
**File**: `quantsys-v2/scripts/register_jobs_to_agent_os.py`

```python
"""
Register all quantsys-v2 scheduled jobs to Agent OS Scheduler.

Run this script on deployment or when job definitions change.
"""
import asyncio
import logging
from services.agent_os_client import get_agent_os_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Job definitions (migrated from SchedulerService)
JOBS = [
    {
        "name": "kline_update",
        "schedule": "40 17 * * 1-5",  # 工作日 17:40
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {
            "job_type": "kline_update",
            "timeout": 600,
            "description": "Update daily K-line data"
        }
    },
    {
        "name": "pool_refresh",
        "schedule": "0 2 * * *",  # 每日 02:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {
            "job_type": "pool_refresh",
            "timeout": 300,
            "description": "Refresh dynamic stock pools"
        }
    },
    {
        "name": "financial_statement_update",
        "schedule": "0 20 * * 6",  # 每周六 20:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {
            "job_type": "financial_statement_update",
            "timeout": 1800,
            "description": "Update quarterly financial statements"
        }
    },
    {
        "name": "chip_distribution_update",
        "schedule": "0 18 * * 1-5",  # 工作日 18:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {
            "job_type": "chip_distribution_update",
            "timeout": 900,
            "description": "Calculate chip distribution"
        }
    },
    {
        "name": "signal_scan_buy",
        "schedule": "0 9 * * 1-5",  # 工作日 09:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {
            "job_type": "signal_scan",
            "scan_type": "buy",
            "strategy_ids": [179, 178, 163, 193],
            "timeout": 300,
            "description": "Scan buy signals before market opens"
        }
    },
    {
        "name": "signal_scan_sell",
        "schedule": "30 15 * * 1-5",  # 工作日 15:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "enabled": True,
        "metadata": {
            "job_type": "signal_scan",
            "scan_type": "sell",
            "timeout": 300,
            "description": "Scan sell signals after market closes"
        }
    },
    # Add remaining 24+ jobs...
]


async def register_all_jobs():
    """Register all jobs to Agent OS Scheduler."""
    client = get_agent_os_client()
    
    # Get existing jobs
    existing_jobs = await client.list_jobs()
    existing_names = {job["name"] for job in existing_jobs}
    
    success_count = 0
    error_count = 0
    
    for job in JOBS:
        try:
            if job["name"] in existing_names:
                logger.info(f"Job {job['name']} already exists, skipping")
                continue
            
            result = await client.register_job(job)
            logger.info(f"Registered {job['name']}: {result['id']}")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to register {job['name']}: {e}")
            error_count += 1
    
    logger.info(f"Registration complete: {success_count} success, {error_count} errors")
    await client.close()


if __name__ == "__main__":
    asyncio.run(register_all_jobs())
```

#### 3.6 Add Startup Hook
**File**: `quantsys-v2/api/app.py`

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown hooks."""
    # Startup
    logger.info("Starting quantsys-v2 API server")
    
    # Register jobs to Agent OS (idempotent)
    from scripts.register_jobs_to_agent_os import register_all_jobs
    try:
        await register_all_jobs()
        logger.info("Job registration complete")
    except Exception as e:
        logger.error(f"Job registration failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down quantsys-v2 API server")
    agent_os_client = get_agent_os_client()
    await agent_os_client.close()


app = FastAPI(lifespan=lifespan)
```

**Deliverables**:
- [ ] `services/scheduler_handlers.py` created with all 30+ job handlers
- [ ] `scripts/register_jobs_to_agent_os.py` created with job definitions
- [ ] Startup hook added to `api/app.py`
- [ ] Manual test: restart quantsys-v2, check logs for "Job registration complete"
- [ ] Verify: `curl http://127.0.0.1:8080/api/v1/scheduler/jobs | jq` shows all 30+ jobs

---

### Day 3: Legacy Cleanup + Gray Release

#### 3.7 Add Feature Flag
**File**: `quantsys-v2/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Scheduler migration feature flag
    USE_AGENT_OS_SCHEDULER: bool = True  # Set to False to use legacy scheduler
    
    class Config:
        env_file = ".env"
```

#### 3.8 Conditional Legacy Scheduler
**File**: `quantsys-v2/api/app.py`

```python
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown hooks."""
    # Startup
    logger.info("Starting quantsys-v2 API server")
    
    if settings.USE_AGENT_OS_SCHEDULER:
        # New: Agent OS Scheduler
        logger.info("Using Agent OS Scheduler")
        from scripts.register_jobs_to_agent_os import register_all_jobs
        try:
            await register_all_jobs()
            logger.info("Job registration complete")
        except Exception as e:
            logger.error(f"Job registration failed: {e}")
            logger.warning("Falling back to legacy scheduler")
            settings.USE_AGENT_OS_SCHEDULER = False
    
    if not settings.USE_AGENT_OS_SCHEDULER:
        # Legacy: Local scheduler (fallback)
        logger.info("Using legacy local scheduler")
        from services.scheduler_service import SchedulerService
        scheduler_service = SchedulerService()
        await scheduler_service.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down quantsys-v2 API server")
    if settings.USE_AGENT_OS_SCHEDULER:
        agent_os_client = get_agent_os_client()
        await agent_os_client.close()
```

#### 3.9 Mark Legacy Code as Deprecated
**File**: `quantsys-v2/services/scheduler_service.py`

```python
"""
DEPRECATED: Legacy scheduler service.

This module is deprecated and will be removed in a future version.
All scheduled jobs have been migrated to Agent OS Scheduler.

To use legacy scheduler (not recommended):
    Set USE_AGENT_OS_SCHEDULER=False in .env

Migration date: 2026-08-15
Removal target: 2026-09-01
"""
import warnings

warnings.warn(
    "SchedulerService is deprecated. Use Agent OS Scheduler instead.",
    DeprecationWarning,
    stacklevel=2
)

class SchedulerService:
    """DEPRECATED: Use Agent OS Scheduler."""
    # ... existing code unchanged ...
```

#### 3.10 Update Documentation
**File**: `quantsys-v2/CLAUDE.md`

Add section:

```markdown
## Scheduler Migration (2026-08-15)

All scheduled jobs have been migrated from local `apscheduler` to **Agent OS Scheduler**.

### Architecture
- **Agent OS Scheduler**: Centralized cron engine running in Agent OS (port 8080)
- **quantsys-v2 Webhook**: Receives job execution callbacks at `/internal/scheduler/webhook`
- **Job Handlers**: Business logic in `services/scheduler_handlers.py`

### Job Registration
Jobs are auto-registered on startup via `scripts/register_jobs_to_agent_os.py`.

To manually register:
```bash
python scripts/register_jobs_to_agent_os.py
```

### Gray Release
Set `USE_AGENT_OS_SCHEDULER=False` in `.env` to fall back to legacy scheduler.

### Legacy Code
- `services/scheduler_service.py`: Marked deprecated, will be removed 2026-09-01
- Database tables `scheduler_jobs` and `scheduler_job_runs`: Still used for run history
```

#### 3.11 Create Monitoring Dashboard
**File**: `quantsys-v2/scripts/monitor_scheduler.py`

```python
"""Monitor Agent OS Scheduler job status."""
import asyncio
from services.agent_os_client import get_agent_os_client
from rich.console import Console
from rich.table import Table

console = Console()


async def monitor_jobs():
    """Display all jobs and their next run times."""
    client = get_agent_os_client()
    jobs = await client.list_jobs()
    
    table = Table(title="Agent OS Scheduler Jobs")
    table.add_column("Name", style="cyan")
    table.add_column("Schedule", style="yellow")
    table.add_column("Enabled", style="green")
    table.add_column("Last Run", style="blue")
    table.add_column("Next Run", style="magenta")
    
    for job in jobs:
        table.add_row(
            job["name"],
            job["schedule"],
            "✓" if job["enabled"] else "✗",
            job.get("last_run_at", "Never"),
            job.get("next_run_at", "N/A")
        )
    
    console.print(table)
    await client.close()


if __name__ == "__main__":
    asyncio.run(monitor_jobs())
```

**Deliverables**:
- [ ] Feature flag `USE_AGENT_OS_SCHEDULER` added to `config.py`
- [ ] Conditional startup logic in `api/app.py`
- [ ] Deprecation warning in `services/scheduler_service.py`
- [ ] Documentation updated in `CLAUDE.md`
- [ ] Monitoring script `scripts/monitor_scheduler.py` created
- [ ] End-to-end test: Set `USE_AGENT_OS_SCHEDULER=True`, restart, verify jobs run correctly
- [ ] Fallback test: Set `USE_AGENT_OS_SCHEDULER=False`, restart, verify legacy scheduler works

## 4. Testing Plan

### 4.1 Unit Tests
```python
# tests/test_scheduler_webhook.py
import pytest
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_webhook_accepts_valid_payload():
    response = client.post("/internal/scheduler/webhook", json={
        "job_id": "test-job-id",
        "job_name": "test_job",
        "trigger_time": "2026-08-15T00:00:00Z",
        "metadata": {"job_type": "kline_update"}
    })
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_webhook_rejects_unknown_job_type():
    response = client.post("/internal/scheduler/webhook", json={
        "job_id": "test-job-id",
        "job_name": "test_job",
        "trigger_time": "2026-08-15T00:00:00Z",
        "metadata": {"job_type": "unknown_type"}
    })
    assert response.status_code == 404


def test_webhook_requires_job_type():
    response = client.post("/internal/scheduler/webhook", json={
        "job_id": "test-job-id",
        "job_name": "test_job",
        "trigger_time": "2026-08-15T00:00:00Z",
        "metadata": {}
    })
    assert response.status_code == 400
```

### 4.2 Integration Tests
```bash
# 1. Start Agent OS
cd agent-os
go run cmd/agent-os/main.go serve

# 2. Start quantsys-v2
cd quantsys-v2
source activate-py313.sh
python api/app.py

# 3. Verify job registration
curl http://127.0.0.1:8080/api/v1/scheduler/jobs | jq

# 4. Trigger a test job manually
curl -X POST http://127.0.0.1:8080/api/v1/scheduler/jobs/{job_id}/trigger

# 5. Check quantsys-v2 logs for webhook execution
tail -f ~/v2-api.log | grep "Received webhook"

# 6. Query job run history
psql quant_investment -c "SELECT * FROM scheduler_job_runs ORDER BY started_at DESC LIMIT 10;"
```

### 4.3 Gray Release Test
```bash
# Phase 1: Agent OS Scheduler (1 week)
echo "USE_AGENT_OS_SCHEDULER=True" >> quantsys-v2/.env
sudo launchctl kickstart -k system/com.pi-investment.v2-api

# Monitor for issues
python quantsys-v2/scripts/monitor_scheduler.py

# Phase 2: If issues found, rollback
echo "USE_AGENT_OS_SCHEDULER=False" >> quantsys-v2/.env
sudo launchctl kickstart -k system/com.pi-investment.v2-api

# Phase 3: After 1 week of stable operation, remove legacy code
git rm quantsys-v2/services/scheduler_service.py
```

## 5. Acceptance Criteria

- [ ] All 30+ jobs registered in Agent OS Scheduler via HTTP API
- [ ] Webhook endpoint `/internal/scheduler/webhook` receives and dispatches jobs correctly
- [ ] Job handlers execute business logic and return structured results
- [ ] Job run history written to PostgreSQL `scheduler_job_runs` table
- [ ] Results reported back to Agent OS via `report_job_result` API
- [ ] Feature flag `USE_AGENT_OS_SCHEDULER` controls which scheduler is used
- [ ] Legacy scheduler still works when flag is `False` (fallback)
- [ ] Documentation updated in `CLAUDE.md`
- [ ] Monitoring script shows all jobs and their status
- [ ] Zero downtime: jobs continue to run on schedule during migration
- [ ] Unit tests pass for webhook endpoint
- [ ] Integration tests pass end-to-end
- [ ] Gray release successful for 1 week without issues

## 6. Rollback Plan

If Agent OS Scheduler fails:

1. **Immediate**: Set `USE_AGENT_OS_SCHEDULER=False` in `.env`
2. **Restart**: `sudo launchctl kickstart -k system/com.pi-investment.v2-api`
3. **Verify**: Check logs show "Using legacy local scheduler"
4. **Monitor**: Confirm jobs run correctly with legacy scheduler
5. **Debug**: Investigate Agent OS Scheduler issue offline
6. **Retry**: Fix issue and set flag back to `True`

## 7. Migration Checklist

### Pre-Migration
- [ ] WP-12 (Agent OS Scheduler HTTP API) completed and tested
- [ ] Agent OS Scheduler running on port 8080
- [ ] quantsys-v2 can reach Agent OS at `http://127.0.0.1:8080`
- [ ] PostgreSQL `scheduler_job_runs` table exists

### Migration
- [ ] Day 1 deliverables completed
- [ ] Day 2 deliverables completed
- [ ] Day 3 deliverables completed
- [ ] All tests passing
- [ ] Documentation updated

### Post-Migration
- [ ] Monitor for 1 week with `USE_AGENT_OS_SCHEDULER=True`
- [ ] No job execution failures
- [ ] No webhook errors in logs
- [ ] Job run history correctly written to database
- [ ] Set legacy removal date (target: 2026-09-01)

## 8. Related Documents

- [WP-11: quantsys-v2 Scheduler Migration (Original)](./2026-08-15-wp11-v2-scheduler-migration.md) - 30+ task breakdown
- [WP-12: Agent OS Scheduler HTTP API](./WP-12-scheduler-http-api.md) - Dependency (must complete first)
- [Agent OS Implementation Audit](../audits/2026-08-15-agent-os-code-review.md) - Current status
- [Agent OS Unification Plan](../plans/2026-08-15-agent-os-unification-plan.md) - Master plan

## 9. Notes

### Differences from WP-13 (agent-ts Integration)

agent-ts integration (WP-13) is **simpler** because:
- agent-ts has only ~5 scheduled tasks (vs quantsys-v2's 30+)
- agent-ts uses simple `node-cron` (vs quantsys-v2's complex `apscheduler`)
- agent-ts is TypeScript (same language as Agent OS SDK)

quantsys-v2 integration (WP-15) is **more complex** because:
- 30+ jobs to migrate (see WP-11 for full list)
- Jobs have complex dependencies (e.g., K-line must run before signal scan)
- Existing job run history must be preserved
- Production system requires zero downtime migration

### Key Design Decisions

1. **Why webhook pattern?**
   - Agent OS Scheduler is cron engine only, not job executor
   - quantsys-v2 business logic stays in Python services
   - Webhook allows quantsys-v2 to execute jobs in its own process

2. **Why keep local database tables?**
   - `scheduler_job_runs` provides detailed execution logs
   - Useful for debugging and performance analysis
   - Agent OS only stores job metadata, not run history

3. **Why gray release with feature flag?**
   - Production system cannot tolerate extended downtime
   - Feature flag allows instant rollback without code deployment
   - Enables gradual migration with monitoring

### Estimated Effort

- **Day 1**: 6 hours (client + webhook receiver)
- **Day 2**: 8 hours (30+ job handlers + registration)
- **Day 3**: 4 hours (feature flag + documentation + testing)
- **Total**: 18 hours over 3 days

### Success Metrics

After migration:
- All 30+ jobs run on schedule without manual intervention
- Zero job execution failures due to scheduler issues
- Webhook latency < 100ms (fast accept, background execute)
- Job run history complete in PostgreSQL
- Legacy scheduler removed after 1 week of stable operation
