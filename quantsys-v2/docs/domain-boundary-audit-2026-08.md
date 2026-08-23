# Domain Boundary Audit Report - quantsys-v2

**Audit Date**: 2026-08-23  
**Auditor**: Claude (Kiro)  
**Scope**: quantsys-v2 architectural layer boundaries

## Executive Summary

This audit examines the adherence to clean architecture principles in quantsys-v2, focusing on dependency direction between layers. The system uses a five-layer architecture where dependency should flow inward:

```
api → adapters/infrastructure → application → domain
(outermost)                              (innermost)
```

### Key Findings

- **🚨 CRITICAL**: 24 violations in domain layer (12 files)
- **⚠️ ERROR**: 97 violations in application layer (42 files)  
- **⚠️ WARNING**: 0 violations in infrastructure layer
- **Overall Status**: ❌ **FAIL** - Core domain layer compromised

### Impact Assessment

The domain layer violations are **architecturally critical** because:
1. Domain is meant to be the stable core with zero external dependencies
2. Violations create circular dependencies and tight coupling
3. Makes unit testing difficult (requires mocking infrastructure)
4. Prevents domain logic reuse in different contexts
5. Violates Dependency Inversion Principle

## Layer Architecture Reference

### Intended Architecture (Clean Architecture)

```
┌─────────────────────────────────────────────────────────┐
│ api/ (3)                                                │
│ HTTP/WebSocket endpoints                                │
│ Dependencies: adapters, application, domain             │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ adapters/ (2) & infrastructure/ (2)                     │
│ Technical implementations: DB, external APIs, cache     │
│ Dependencies: application, domain                       │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ application/ (1)                                        │
│ Use cases, orchestration, services                      │
│ Dependencies: domain ONLY                               │
└────────────────────┬────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────┐
│ domain/ (0)                                             │
│ Core business logic, entities, value objects            │
│ Dependencies: NONE (pure domain logic)                  │
└─────────────────────────────────────────────────────────┘
```

### Layer Statistics

| Layer | Files | Directories | Top Module |
|-------|-------|-------------|------------|
| domain | 267 | 43 | quantlib/engine (37 files) |
| application | 174 | 10 | services (124 files) |
| infrastructure | 89 | 20 | persistence/orm/models (15 files) |
| adapters | 221 | 29 | inbound/fastapi_app/routes (63 files) |
| api | 1 | 1 | internal (1 file) |

## 🚨 CRITICAL: Domain Layer Violations

**Rule**: Domain layer must have ZERO dependencies on outer layers.

**Violations Found**: 24 import statements across 12 files

### Category A: Infrastructure Dependencies (7 files)

These files directly import from `infrastructure/`, violating domain purity.

#### 1. domain/benchmarks/benchmark_cache.py
```python
Line 28: from infrastructure.config import create_cache_service
Line 29: from infrastructure.cache import CacheService
```
**Issue**: Benchmark caching logic depends on infrastructure implementation.  
**Fix**: Use dependency injection or port/adapter pattern.

#### 2. domain/memory/distiller.py
```python
Line 10: from infrastructure.persistence.orm import get_session
```
**Issue**: Memory distillation logic coupled to ORM session management.  
**Fix**: Accept session as injected dependency or use repository pattern.

#### 3. domain/memory/embedding.py
```python
Line 14: from infrastructure.config import get_config
```
**Issue**: Embedding logic reads config directly from infrastructure.  
**Fix**: Pass config values as parameters or inject config port.

#### 4. domain/memory/service.py
```python
Line 12: from infrastructure.config import get_config
```
**Issue**: Memory service coupled to config infrastructure.  
**Fix**: Inject configuration through constructor.

#### 5. domain/quantlib/adapters/factory.py
```python
Line 21: from infrastructure.config import get_config
```
**Issue**: Factory pattern in domain depends on infrastructure config.  
**Fix**: Pass config values to factory methods.

#### 6. domain/quantlib/core/portfolio_calculator.py
```python
Line 15: from infrastructure.config import get_config
```
**Issue**: Core portfolio calculation coupled to config system.  
**Fix**: Accept configuration values as parameters.

### Category B: Adapters Dependencies (4 files)

These files import from `adapters/`, which should be injected.

#### 7. domain/brokers/adapters/__init__.py
```python
Line 24: from adapters.outbound.brokers.akshare_broker import AkshareBroker
Line 25: from adapters.outbound.brokers.ibkr_broker import IBKRBroker
Line 26: from adapters.outbound.brokers.alpaca_broker import AlpacaBroker
```
**Issue**: Domain imports concrete adapter implementations.  
**Fix**: Move concrete imports to infrastructure, use registry pattern.

#### 8. domain/brokers/broker_registry.py
```python
Line 67: from adapters.outbound.brokers.akshare_broker import AkshareBroker
Line 75: from adapters.outbound.brokers.ibkr_broker import IBKRBroker
Line 85: from adapters.outbound.brokers.alpaca_broker import AlpacaBroker
```
**Issue**: Registry in domain directly imports adapters.  
**Fix**: Registry should be in infrastructure, domain defines interface only.

#### 9. domain/memory/distiller.py
```python
Line 9: from adapters.outbound.repositories.memory_repository import MemoryRepository
Line 63: from adapters.outbound.repositories.agent_intelligence_repository import AgentDecision
```
**Issue**: Domain business logic depends on repository implementations.  
**Fix**: Define repository interfaces in domain, inject implementations.

#### 10. domain/quantlib/adapters/__init__.py
```python
Line 24: from adapters.outbound.datasources.providers.quantlib.factor_calculator_adapter import ...
Line 28: from adapters.outbound.datasources.providers.quantlib.base_adapter import BaseMarketAdapter
Line 29: from adapters.outbound.datasources.providers.quantlib.akshare_adapter import AkShareAdapter
Line 30: from adapters.outbound.datasources.providers.quantlib.factory import ...
Line 35: from adapters.outbound.datasources.providers.quantlib.eastmoney_adapter import EastMoneyAdapter
Line 36: from adapters.outbound.datasources.providers.quantlib.sina_adapter import SinaAdapter
```
**Issue**: Domain's adapter module re-exports concrete implementations.  
**Fix**: This is a misplaced module - should be in infrastructure layer.

### Category C: Application Dependencies (2 files)

These files import from `application/`, creating circular dependencies.

#### 11. domain/benchmarks/run_all_benchmarks.py
```python
Line 14: from application.services.benchmark_service import BenchmarkService
```
**Issue**: Domain benchmark runner depends on application service.  
**Fix**: This script should be in application/ or infrastructure/.

#### 12. domain/quantlib/engine/backtest_report.py
```python
Line 93: from application.services.risk_metrics_service import RiskMetricsService
```
**Issue**: Backtest report generation depends on application service.  
**Fix**: Inject service or move report generation to application layer.

#### 13. domain/quantlib/engine/mixins/ml_mixin.py
```python
Line 54: from application.services.ml_pipeline.predictor import MLPredictor
```
**Issue**: ML mixin in domain depends on application-layer predictor.  
**Fix**: Define predictor interface in domain, inject implementation.

## ⚠️ ERROR: Application Layer Violations

**Rule**: Application layer should only depend on domain layer.

**Violations Found**: 97 import statements across 42 files

### Breakdown by Target Layer

#### Application → Infrastructure: 79 violations in 37 files

**Sample violations**:
- `application/services/account_trading_service.py` - imports ORM models directly
- `application/services/backtest_async_engine.py` - imports database session
- `application/services/configurable_scoring_service.py` - imports config infrastructure
- `application/services/daily_orchestrator.py` - imports scheduler infrastructure
- `application/services/data_service.py` - imports persistence layer

**Pattern**: Services directly importing ORM models, database sessions, cache implementations, and config infrastructure.

**Impact**: Medium - Application services are coupled to infrastructure implementation details.

**Fix Strategy**: 
- Use repository interfaces defined in domain
- Inject infrastructure dependencies via constructors
- Use ports and adapters pattern

#### Application → Adapters: 17 violations in 11 files

**Sample violations**:
- `application/services/data_backfiller.py` - imports data source adapters
- `application/services/dividend_service.py` - imports repository implementations
- `application/services/financial_analysis_service.py` - imports adapters
- `application/services/hk_market_data_service.py` - imports data providers
- `application/services/market_data_service.py` - imports adapters

**Pattern**: Services directly importing concrete repository and data source implementations.

**Impact**: Medium - Services are tightly coupled to specific adapter implementations.

**Fix Strategy**:
- Define interfaces in domain
- Inject implementations at runtime
- Use factory pattern in infrastructure

#### Application → API: 1 violation

**File**: `application/services/scheduler_handlers.py`

**Impact**: Low - Single violation, likely a misplaced module.

**Fix Strategy**: Move scheduler handlers to adapters/inbound layer.

## ⚠️ WARNING: Infrastructure Layer Issues

**Violations Found**: 0 direct layer violations

However, infrastructure shows **borderline pattern** with 10 files importing from application layer. This creates potential circular dependencies.

**Files importing application**:
- Infrastructure jobs importing application services
- Config modules importing application-layer factories

**Recommendation**: Review these cases - some may be legitimate (e.g., job configurations), others should be refactored.

## Architectural Debt Summary

### Severity Classification

| Severity | Count | Impact | Priority |
|----------|-------|--------|----------|
| 🔴 Critical | 24 | Domain layer compromised | P0 - Immediate |
| 🟡 High | 97 | Application-infrastructure coupling | P1 - This quarter |
| 🟢 Medium | 10 | Infrastructure-application coupling | P2 - Review needed |

### Root Causes

1. **Historical Growth**: Code evolved without strict architectural enforcement
2. **Convenience Over Structure**: Direct imports faster than proper DI
3. **Missing Abstractions**: No clear port/interface definitions in domain
4. **Registry Pattern Misplacement**: Registries in domain instead of infrastructure
5. **Script Misplacement**: Utility scripts in domain instead of tools/scripts

## Recommended Remediation Plan

### Phase 1: Domain Layer Purity (P0) - 2-3 days

**Goal**: Eliminate all 24 domain layer violations

#### Step 1: Move Misplaced Modules (1 day)
- Move `domain/benchmarks/run_all_benchmarks.py` → `scripts/`
- Move `domain/brokers/broker_registry.py` → `infrastructure/brokers/`
- Move `domain/quantlib/adapters/` → `infrastructure/quantlib/adapters/`

#### Step 2: Introduce Port Interfaces (1 day)
Create domain interfaces:
```python
# domain/ports/config_port.py
class ConfigPort(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...

# domain/ports/cache_port.py
class CachePort(Protocol):
    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any, ttl: int = None) -> None: ...

# domain/ports/memory_port.py
class MemoryRepository(Protocol):
    def save(self, memory: Memory) -> None: ...
    def find_similar(self, embedding: List[float], limit: int) -> List[Memory]: ...
```

#### Step 3: Inject Dependencies (1 day)
Refactor domain services to accept dependencies:
```python
# Before
class MemoryService:
    def __init__(self):
        self.config = get_config()  # ❌ Direct import

# After
class MemoryService:
    def __init__(self, config: ConfigPort):
        self.config = config  # ✅ Injected
```

### Phase 2: Application Layer Cleanup (P1) - 1 week

**Goal**: Reduce application-infrastructure coupling from 97 to <10

#### Step 1: Define Repository Interfaces (2 days)
Move repository interfaces to domain:
```python
# domain/repositories/stock_repository.py
class StockRepository(Protocol):
    def find_by_symbol(self, symbol: str) -> Optional[Stock]: ...
    def save(self, stock: Stock) -> None: ...
```

#### Step 2: Refactor Services to Use Interfaces (3 days)
Update application services:
```python
# Before
from infrastructure.persistence.orm.models import Stock  # ❌

class StockService:
    def get_stock(self, symbol: str):
        return Stock.query.filter_by(symbol=symbol).first()

# After
from domain.repositories import StockRepository  # ✅

class StockService:
    def __init__(self, stock_repo: StockRepository):
        self.stock_repo = stock_repo
    
    def get_stock(self, symbol: str):
        return self.stock_repo.find_by_symbol(symbol)
```

#### Step 3: Update Dependency Injection (2 days)
Configure DI in infrastructure:
```python
# infrastructure/di/container.py
def configure_services():
    return {
        'config': ConfigAdapter(),
        'stock_repo': StockRepositoryImpl(),
        'stock_service': StockService(stock_repo=stock_repo),
    }
```

### Phase 3: Infrastructure Review (P2) - 2 days

**Goal**: Resolve infrastructure→application dependencies

Review each of 10 cases:
- If legitimate (job configuration), document rationale
- If circular, refactor to use events or interfaces

## Testing Strategy

### Pre-Refactor Baseline
1. Run full test suite: `pytest tests/` (establish baseline)
2. Document current pass/fail status
3. Identify tests dependent on current architecture

### During Refactor
1. **Test per module**: After moving each module, run affected tests
2. **Integration checkpoints**: After each step, run full suite
3. **Rollback threshold**: If >10% tests break, pause and review

### Post-Refactor Validation
1. All baseline tests must pass
2. New unit tests for domain layer (now testable in isolation)
3. Architecture tests to prevent regression:
   ```python
   def test_domain_has_no_external_dependencies():
       """Domain layer must not import from outer layers"""
       domain_files = glob.glob('domain/**/*.py', recursive=True)
       for file_path in domain_files:
           content = Path(file_path).read_text()
           assert 'from application' not in content
           assert 'from infrastructure' not in content
           assert 'from adapters' not in content
   ```

## Architectural Governance

### Prevention Mechanisms

1. **Pre-commit Hook**: Check for layer violations
2. **CI/CD Gate**: Architecture tests must pass
3. **Code Review Checklist**: Verify layer boundaries
4. **Documentation**: Update CLAUDE.md with layer rules

### Allowed Exceptions

Document any necessary exceptions with rationale:

```python
# domain/special_case.py
# ARCHITECTURAL_EXCEPTION: Imports from infrastructure
# Rationale: [Detailed justification]
# Approved by: [Name/Date]
# Review by: [Date]
from infrastructure.special_module import special_function  # noqa: ARCH001
```

## Conclusion

The quantsys-v2 codebase has **significant architectural debt** in domain boundaries:

- ✅ **Strengths**: Clear directory structure, separation of concerns attempted
- ❌ **Weaknesses**: Domain layer compromised by 24 violations
- ⚠️ **Risk**: Application layer has 97 coupling issues

**Recommendation**: Execute Phase 1 (Domain Purity) immediately. Domain layer integrity is foundational - all other patterns depend on it.

**Estimated Effort**:
- Phase 1 (P0): 2-3 days
- Phase 2 (P1): 1 week  
- Phase 3 (P2): 2 days
- **Total**: ~2 weeks of focused refactoring

**Benefits Post-Remediation**:
1. Domain logic testable in isolation (faster tests)
2. Clear boundaries enable parallel development
3. Domain logic reusable in different contexts
4. Easier to understand and maintain
5. Supports future microservices extraction

---

**Next Steps**:
1. Review this audit with team
2. Prioritize Phase 1 for immediate execution
3. Create tracking issues for each violation
4. Schedule refactoring sprint

**Related Documents**:
- [quantsys-v2/CLAUDE.md](../CLAUDE.md) - Architecture overview
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) - Reference
