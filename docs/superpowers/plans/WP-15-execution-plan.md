# WP-15 Execution Plan: quantsys-v2 Scheduler Integration

**Status**: 🚧 IN PROGRESS  
**Started**: 2026-08-16  
**Executor**: Claude (Haiku execution model)  
**Estimated Duration**: 3 days

---

## Day 1: Agent OS Client + Webhook Receiver

### Phase 1.1: Create Agent OS Client ✅
- [ ] Create `quantsys-v2/application/services/agent_os_client.py`
- [ ] Implement full Scheduler API methods
- [ ] Add global singleton accessor

### Phase 1.2: Create Webhook Receiver ✅
- [ ] Create `quantsys-v2/api/internal/scheduler_webhook.py`
- [ ] Implement webhook endpoint
- [ ] Add job handler registry decorator
- [ ] Implement background task execution

### Phase 1.3: Register Router ✅
- [ ] Add import in `api/app.py`
- [ ] Register `/internal/scheduler` router
- [ ] Manual test webhook endpoint

---

## Day 2: Job Handlers + Registration

### Phase 2.1: Migrate Existing Job Handlers ✅
- [ ] Create `quantsys-v2/application/services/scheduler_handlers.py`
- [ ] Extract 30+ handlers from `SchedulerService`
- [ ] Use `@register_job_handler` decorator
- [ ] Delegate to existing service methods

### Phase 2.2: Create Job Registration Script ✅
- [ ] Create `quantsys-v2/scripts/register_jobs_to_agent_os.py`
- [ ] Define all 30+ job definitions with cron expressions
- [ ] Implement idempotent registration logic
- [ ] Add CLI entry point

### Phase 2.3: Add Startup Hook ✅
- [ ] Add lifespan context manager to `api/app.py`
- [ ] Call `register_all_jobs()` on startup
- [ ] Handle registration failures gracefully

---

## Day 3: Legacy Cleanup + Gray Release

### Phase 3.1: Add Feature Flag ✅
- [ ] Add `USE_AGENT_OS_SCHEDULER` to config
- [ ] Default to `True`

### Phase 3.2: Conditional Legacy Scheduler ✅
- [ ] Update lifespan with conditional logic
- [ ] Fallback to legacy on Agent OS failure
- [ ] Proper cleanup on shutdown

### Phase 3.3: Mark Legacy Code as Deprecated ✅
- [ ] Add deprecation warning to `SchedulerService`
- [ ] Update docstrings

### Phase 3.4: Update Documentation ✅
- [ ] Add migration section to `CLAUDE.md`
- [ ] Document gray release process
- [ ] Document rollback procedure

### Phase 3.5: Create Monitoring Script ✅
- [ ] Create `scripts/monitor_scheduler.py`
- [ ] Display job status with Rich tables

---

## Acceptance Criteria

- [ ] All 30+ jobs registered in Agent OS via HTTP API
- [ ] Webhook endpoint receives and dispatches jobs
- [ ] Job handlers execute and return structured results
- [ ] Run history written to PostgreSQL
- [ ] Results reported back to Agent OS
- [ ] Feature flag controls scheduler selection
- [ ] Legacy scheduler works as fallback
- [ ] Documentation updated
- [ ] Monitoring script functional
- [ ] Zero downtime migration
- [ ] Unit tests pass
- [ ] Integration tests pass

---

## Notes

- Agent OS HTTP API is at `http://127.0.0.1:8080`
- quantsys-v2 webhook at `http://127.0.0.1:5001/internal/scheduler/webhook`
- Keep existing database tables for run history
- Preserve job execution logic in Python
