# quantsys-v2 架构审计报告

**审计日期**: 2026-08-19
**审计范围**: quantsys-v2 项目架构质量（框架一致性、DDD 分离、基础设施健壮性）
**代码统计**: 707 个 Python 文件，约 15 万行代码

---

## 执行摘要

| 维度 | 评分 | 状态 |
|------|------|------|
| 框架一致性 | 4/10 | ⚠️ 需要改进 |
| DDD 分离清晰度 | 5/10 | ⚠️ 需要改进 |
| 基础设施健壮性 | 6/10 | ✅ 基本合格 |
| **综合** | **5/10** | **⚠️ 需要系统性改进** |

---

## 一、框架一致性审计（评分：4/10）

### 1.1 服务基类不统一 ❌ 严重

**问题**: 76 个服务类中仅 **2 个（2.6%）** 继承 `ServiceBase`，其余 74 个（97.4%）无统一基类。

**影响**:
- 错误处理模式各异：有的吞异常、有的抛 RuntimeError、有的返回 None
- 日志记录不统一：有的用 structlog、有的用 logging、有的无日志
- 参数校验重复：每个服务各自实现 symbol 校验、日期校验等

**具体数据**:
```
继承 ServiceBase: 2 (2.6%)
  - LhbService(ServiceBase)
  - DividendService(ServiceBase)
未继承基类: 74 (97.4%)
  - DataService, StockPoolService, StrategyService, OrderService, ...
```

**建议**: 
- P1: 所有服务类统一继承 `ServiceBase`
- P1: 在基类中统一实现 `_validate_symbol`、`_validate_date`、`_handle_error`、`_log_operation`

### 1.2 Repository 基类基本统一 ✅ 良好

**现状**: 62 个 Repository 类中 59 个（95.2%）继承 `BaseORMRepository`/`AsyncBaseORMRepository`。

**例外**（3 个不继承基类）:
| Repository | 原因 | 风险 |
|-----------|------|------|
| `StockPoolRepository` | ORM 重构后恢复旧实现（psycopg2 原始 SQL） | 2026-08-04 事故后恢复，与 ORM 模型共存 |
| `StrategyPerformanceRepository` | 同上，指向 quant.strategy_performance 表 | 同上 |
| `SchedulerRepository` | 直接操作 SchedulerTaskConfig ORM 模型 | 实际上在用 ORM，只是没继承基类 |

**建议**: P2: 将 3 个 Repository 统一为继承 ORM 基类

### 1.3 双框架并存（Flask + FastAPI）⚠️ 中等

**现状**:
- Flask 路由: 62 个文件（`adapters/inbound/api/routes/`）
- FastAPI 路由: 62 个文件（`adapters/inbound/fastapi_app/routes/`）
- 生产环境 2026-08-02 起运行 FastAPI

**问题**:
- 维护负担：任何 API 变更需要改两个地方
- 代码混淆：新开发者不知道哪个是"真相源"
- 历史包袱：Flask 目录中仍有 `scheduler_enterprise.py` 等已废弃代码

**建议**: P1: 制定 Flask 删除计划，保留 1-2 个版本后彻底移除

### 1.4 数据访问模式不统一 ❌ 严重

**问题**: 存在三套并行的数据 provider 体系：

| 体系 | 位置 | 用途 | 状态 |
|------|------|------|------|
| **DataProviderManager** | `adapters/outbound/datasources/` | 统一外部数据访问（推荐） | ✅ 活跃 |
| **financial_providers** | `application/services/financial_providers/` | 财务数据 provider | ❌ 与 DPM 重复 |
| **quote_providers** | `application/services/quote_providers/` | 实时报价 provider | ❌ 与 DPM 重复 |

**直接 akshare 导入统计**:
- Application 层: **15 个文件** 直接 `import akshare`
- Domain 层: **2 个文件** 直接 `import akshare`（`akshare_broker.py`, `akshare_adapter.py`）
- Adapters 层: **5 个文件** 直接 `import akshare`（排除 datasource providers）

**建议**: 
- P0: 将 `financial_providers/` 和 `quote_providers/` 迁移到 `DataProviderManager` 体系
- P1: 逐步消除 application 层的直接 akshare 导入

### 1.5 路由层导入模式混乱 ❌ 严重

**FastAPI 路由存在两种服务获取模式**：

模式 A（推荐）: 通过 `adapters/shared/services.py` 获取预组装服务
```python
from adapters.inbound.fastapi_app.shared import ds, strategy_service
```

模式 B（绕过）: 直接从 application 层导入
```python
from application.services.strategy_service import StrategyService
from application.services.market_data_service import market_data_service
```

**统计**: 37 个路由文件使用模式 A，35 个路由文件使用模式 B（80 处直接导入）。

**建议**: P1: 统一为模式 A，所有服务通过 `ServiceFactory` 或 `shared.services` 获取

---

## 二、DDD 分离清晰度审计（评分：5/10）

### 2.1 依赖方向违规 ❌ 严重

**理论规则**: `domain/` → `application/` → `adapters/` → `infrastructure/`

**发现的违规**:

| 方向 | 文件数 | 示例 |
|------|--------|------|
| domain → application | 3 | `backtest_report.py` 导入 `RiskMetricsService` |
| domain → adapters | 2 | `memory/distiller.py` 导入 `MemoryRepository` |
| domain → infrastructure | 2 | `benchmark_cache.py` 导入 `CacheService` |
| application → inbound adapters | 1 | `scheduler_tasks.py` 导入 `stock_pool_service` |

**根因分析**:
1. `domain/quantlib/adapters/` — 这些 akshare adapter 本质上是**基础设施适配器**，不应在 domain 层
2. `domain/brokers/adapters/` — 同上，broker adapter 应属于 adapters 层
3. `domain/memory/distiller.py` — 直接操作 repository 和 session，应移至 application 层

**建议**:
- P0: 将 `domain/quantlib/adapters/` 移至 `adapters/outbound/`
- P0: 将 `domain/brokers/adapters/` 移至 `adapters/outbound/`
- P1: 将 `domain/memory/distiller.py` 重构为 application service

### 2.2 Application 层直接依赖 Infrastructure ⚠️ 中等

**统计**:
- 65 处直接导入 `adapters.outbound.repositories`（涉及 65 个文件）
- 65 处直接导入 `infrastructure.*`（涉及 30 个文件）
- 6 处直接导入 ORM Models

**问题**: Application 层应通过 **Domain Ports** 依赖 Repository，而非直接依赖具体实现。

**现状**: Domain Ports 完全未被 Application 层使用。

```
Domain Ports 定义: 6 个接口
  IKlineRepository: 1 实现, 0 处 Application 使用
  ISignalRepository: 1 实现, 0 处 Application 使用
  IPortfolioRepository: 1 实现, 0 处 Application 使用
  IRiskRepository: 1 实现, 0 处 Application 使用
  IFactorRepository: 1 实现, 0 处 Application 使用
  IStrategyRepository: 1 实现, 0 处 Application 使用
```

**建议**:
- P1: 评估是否需要真正实施依赖倒置（当前直接依赖模式在小型团队中有其便利性）
- P2: 如实施 DIP，需为所有 Service 添加构造函数注入接口的能力

### 2.3 ServiceFactory 使用不足 ⚠️ 中等

**现状**: `ServiceFactory` 仅被 3 个文件使用（`adapters/shared/services.py` 等）。

**问题**: 大多数服务直接在路由中实例化，或通过模块级全局变量获取。

**建议**: P1: 推广 `ServiceFactory` 作为统一的服务获取入口

### 2.4 异常层次结构部分使用 ⚠️ 中等

**统计**:
```
Domain Exceptions 使用情况:
  DomainError: 2 处
  NotFoundError: 15 处
  ValidationError: 66 处 ← 相对较多
  ConflictError: 3 处
  ExternalServiceError: 3 处
  DatabaseError: 4 处
  AuthenticationError: 2 处
  AuthorizationError: 2 处
```

**问题**: 
- 大量代码仍使用裸 `raise Exception()`、`raise ValueError()`
- `domain/exceptions.py` 中包含 FastAPI `HTTPException` 示例（框架泄漏到 domain）

**建议**: P2: 清理 `domain/exceptions.py` 中的框架引用；推广使用 domain exceptions

---

## 三、基础设施健壮性审计（评分：6/10）

### 3.1 数据库连接管理 ✅ 良好

**优点**:
- 三层 pytest 安全防护（conftest.py → base_repository → async_base_repository）
- scoped_session 线程隔离
- 2026-08-18 事故后修复：session 不再实例缓存，每次 `get_session()` 现取
- `_get_cursor()` 兼容层为遗留代码提供平滑过渡

**风险**:
- `_get_cursor()` 的 `_raw_conn` 连接在实例上缓存，存在泄漏风险
- 异步连接池配置需要验证（pool_recycle、pool_pre_ping）

### 3.2 数据源故障转移 ✅ 良好

**优点**:
- `DataProviderManager` 实现多 provider 自动故障转移
- 超时护栏（60s）防止单 provider 挂死拖垮线程池
- 健康统计追踪（success/failure 计数）
- 2026-08-18 修复：超时线程 finally 中释放 ORM session

**待改进**:
- 无动态优先级调整（基于健康统计自动降级/恢复 provider）
- 无熔断器模式（circuit breaker）
- 无 provider 级别的缓存

### 3.3 缓存层 ⚠️ 基础

**现状**:
- 内存缓存: `infrastructure/cache/cache_service.py`
- 异步缓存: `infrastructure/cache/async_cache_service.py`
- 简单缓存: `infrastructure/utils/simple_cache.py`

**问题**: 无分布式缓存（Redis），重启后缓存丢失

### 3.4 调度系统 ✅ 良好

**现状**:
- 2026-08-13 迁移到 FastAPI lifespan 三线程
- 僵尸任务检测（running > 6h → failed）
- per-task misfire 宽限

**风险**:
- lifespan 线程异常可能导致整个 FastAPI 进程崩溃
- 任务并发安全性需要验证

---

## 四、问题清单（按优先级排序）

### P0 — 必须立即修复

| # | 问题 | 影响 | 建议修复 |
|---|------|------|---------|
| 1 | Application 层 15 个文件直接 `import akshare`，绕过 `DataProviderManager` | 无故障转移，重复代码 | 迁移到 `DataProviderManager` |
| 2 | Domain 层 7 个文件反向依赖上层（adapters/application/infrastructure） | 违反分层原则，循环依赖风险 | 将 adapter 移至 adapters/ 层 |
| 3 | `financial_providers/` 和 `quote_providers/` 与 `DataProviderManager` 重复 | 代码重复，维护困难 | 合并到统一体系 |

### P1 — 需要改进

| # | 问题 | 影响 | 建议修复 |
|---|------|------|---------|
| 4 | 74/76 个服务类不继承 `ServiceBase` | 错误处理不统一 | 统一基类，逐步迁移 |
| 5 | FastAPI 路由 35 个文件直接导入 application services | 绕过服务工厂，难以测试 | 统一通过 shared/services 获取 |
| 6 | Flask + FastAPI 双框架并存（124 个路由文件） | 维护负担 | 制定 Flask 删除计划 |
| 7 | Application 层 65 个文件直接依赖 Repository 实现 | 违反 DIP | 评估是否需要接口抽象 |
| 8 | Domain Ports 定义的接口完全未被 Application 层使用 | 设计未落地 | 决定保留/删除/实施 |

### P2 — 长期优化

| # | 问题 | 影响 | 建议修复 |
|---|------|------|---------|
| 9 | 3 个 Repository 不继承 ORM 基类 | 模式不一致 | 统一为 ORM 模式 |
| 10 | Domain exceptions 使用率不高 | 异常处理不统一 | 推广使用 |
| 11 | 无分布式缓存 | 重启丢缓存 | 引入 Redis |
| 12 | 无 provider 动态优先级/熔断器 | 故障恢复不智能 | 增强 DataProviderManager |

---

## 五、关键文件清单

### 需要重点审查的文件

| 文件 | 问题 | 优先级 |
|------|------|--------|
| `application/services/base_service.py` | 仅 2/76 服务使用 | P1 |
| `domain/ports/repository_ports.py` | 完全未被 Application 使用 | P1 |
| `adapters/outbound/datasources/manager.py` | 应统一所有数据访问 | P0 |
| `application/services/financial_providers/` | 与 DPM 重复 | P0 |
| `application/services/quote_providers/` | 与 DPM 重复 | P0 |
| `domain/quantlib/adapters/akshare_adapter.py` | Domain 层直接 import akshare | P0 |
| `domain/brokers/adapters/akshare_broker.py` | Domain 层直接 import akshare | P0 |
| `infrastructure/persistence/orm/base_repository.py` | 连接管理核心 | P1 |
| `adapters/shared/services.py` | 服务组装层 | P1 |
| `infrastructure/services/service_factory.py` | 仅 3 处使用 | P1 |

---

## 六、建议行动路线

### 短期（1-2 周）
1. **统一数据访问**: 将 `financial_providers/` 和 `quote_providers/` 合并到 `DataProviderManager`
2. **修复分层违规**: 将 `domain/quantlib/adapters/` 和 `domain/brokers/adapters/` 移至 adapters 层
3. **消除直接 akshare 导入**: 优先处理 application 层 15 个文件

### 中期（1 个月）
4. **统一服务基类**: 所有服务继承 `ServiceBase`，统一错误处理
5. **统一路由导入**: 所有路由通过 `shared.services` 获取服务
6. **删除 Flask**: 确认无客户端使用后删除 Flask 路由栈

### 长期（3 个月）
7. **实施 DIP**: 评估是否需要 Application 层通过 Domain Ports 依赖 Repository
8. **增强 DataProviderManager**: 添加动态优先级、熔断器、缓存
9. **引入分布式缓存**: Redis 缓存层

---

*报告生成时间: 2026-08-19*
*审计方法: 自动化扫描 + 人工代码审查*
