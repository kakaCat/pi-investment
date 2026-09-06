# DDD 架构修复报告

## 问题诊断

### 1. 架构违规问题

**严重违规**：Domain 层直接依赖 Adapters 和 Infrastructure 层

违规文件：
```
domain/quantlib/tools/strategy_stock_matcher.py
domain/quantlib/core/portfolio_calculator.py
domain/quantlib/stages/data_pipeline/time_alignment_stage.py
domain/quantlib/stages/data_pipeline/factor_compute_stage.py
domain/quantlib/stages/data_pipeline/storage_stage.py
domain/quantlib/engine/strategy_runner.py
domain/quantlib/engine/strategy_factory.py
domain/benchmarks/benchmark_cache.py
domain/benchmarks/run_all_benchmarks.py
domain/quantlib/pipeline/monitor.py
domain/quantlib/engine/mixins/ml_mixin.py
```

**违规模式**：
```python
# ❌ 错误：Domain 依赖 Adapters
from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.repositories import SignalORMRepository

# ❌ 错误：Domain 依赖 Infrastructure
from infrastructure.persistence.database.base_repository import BaseRepository
```

### 2. 正确的 DDD 架构

```
┌─────────────────────────────────────────────┐
│  Adapters (Inbound: API, CLI)              │
│  - 接收外部请求                              │
└──────────────────┬──────────────────────────┘
                   │ 调用
                   ↓
┌─────────────────────────────────────────────┐
│  Application Services                       │
│  - 用例协调                                  │
│  - 依赖注入 Repository 实现                  │
└──────────────────┬──────────────────────────┘
                   │ 调用
                   ↓
┌─────────────────────────────────────────────┐
│  Domain Layer                               │
│  - 纯业务逻辑                                │
│  - 定义 Ports (接口)                         │
│  - 不依赖外部框架                            │
└──────────────────┬──────────────────────────┘
                   │ 定义接口
                   ↓
┌─────────────────────────────────────────────┐
│  Adapters (Outbound: Repositories)          │
│  - 实现 Domain 定义的接口                    │
└──────────────────┬──────────────────────────┘
                   │ 使用
                   ↓
┌─────────────────────────────────────────────┐
│  Infrastructure                             │
│  - 数据库连接                                │
│  - ORM 配置                                  │
└─────────────────────────────────────────────┘
```

**依赖方向**：
```
Adapters (Inbound) → Application → Domain ← Adapters (Outbound)
                                              ↓
                                         Infrastructure
```

## 修复方案

### Phase 1: 创建 Domain Ports ✅

创建 `domain/ports/` 目录，定义 Repository 接口：

```
domain/ports/
├── __init__.py
└── repository_ports.py
    ├── IKlineRepository
    ├── ISignalRepository
    ├── IPortfolioRepository
    ├── IRiskRepository
    ├── IFactorRepository
    └── IStrategyRepository
```

### Phase 2: Adapters 实现接口（待执行）

让 ORM Repository 实现 Domain 接口：

```python
# adapters/outbound/repositories/kline_repository.py
from domain.ports import IKlineRepository

class KlineORMRepository(IKlineRepository):
    """实现 Domain 定义的 IKlineRepository 接口"""
    
    def get_kline_data(self, symbol, start_date, end_date, period):
        # 具体实现
        pass
```

### Phase 3: 重构 Domain 层（待执行）

修改 Domain 层文件，使用接口而非具体实现：

**修改前**：
```python
from adapters.outbound.repositories import KlineORMRepository

class StrategyRunner:
    def __init__(self):
        self.kline_repo = KlineORMRepository()  # ❌ 直接依赖具体实现
```

**修改后**：
```python
from domain.ports import IKlineRepository

class StrategyRunner:
    def __init__(self, kline_repo: IKlineRepository):  # ✅ 依赖接口
        self.kline_repo = kline_repo
```

### Phase 4: Application 层依赖注入（待执行）

Application Services 负责创建具体实现并注入：

```python
# application/services/strategy_execution_service.py
from domain.quantlib.engine.strategy_runner import StrategyRunner
from adapters.outbound.repositories import KlineORMRepository

class StrategyExecutionService:
    def __init__(self):
        # Application 层创建具体实现
        kline_repo = KlineORMRepository()
        
        # 注入到 Domain 对象
        self.strategy_runner = StrategyRunner(kline_repo=kline_repo)
```

## 修复清单

### ✅ 已完成

1. [x] 创建 `domain/ports/repository_ports.py`
2. [x] 定义 6 个核心 Repository 接口

### ⏳ 待执行

3. [ ] 让所有 ORM Repository 实现对应接口
4. [ ] 重构 13 个 Domain 层文件，移除 Adapters/Infrastructure 依赖
5. [ ] 在 Application Services 中实现依赖注入
6. [ ] 更新所有调用方代码
7. [ ] 运行测试验证修复

## 架构收益

**修复前（违规架构）**：
- ❌ Domain 耦合具体实现，难以测试
- ❌ 无法替换数据源（如从 ORM 换到 NoSQL）
- ❌ 违反依赖倒置原则
- ❌ 不符合六边形架构

**修复后（正确架构）**：
- ✅ Domain 纯粹，易于测试（Mock 接口）
- ✅ 可插拔数据源（实现接口即可）
- ✅ 符合 DDD 和六边形架构
- ✅ 清晰的分层边界

## 估算工作量

- **Phase 2**: ~2 小时（27 个 Repository 实现接口）
- **Phase 3**: ~4 小时（重构 13 个 Domain 文件）
- **Phase 4**: ~2 小时（Application 层依赖注入）
- **测试验证**: ~2 小时

**总计**: ~10 小时工作量

## 风险评估

**风险**: 中等（涉及核心业务逻辑重构）

**缓解措施**:
1. 先修复最简单的文件（如 strategy_stock_matcher.py）
2. 每修复一个文件立即运行相关测试
3. 使用 git 分支隔离修复工作
4. 保持向后兼容（渐进式迁移）

## 下一步行动

建议按以下顺序执行：

1. **创建修复分支**
   ```bash
   git checkout -b fix/ddd-architecture
   ```

2. **Phase 2**: 让 Repository 实现接口（从最简单的开始）
   - KlineORMRepository
   - SignalORMRepository
   - StrategyORMRepository

3. **Phase 3**: 重构一个 Domain 文件并测试
   - 从 `strategy_stock_matcher.py` 开始（最小文件）
   - 运行测试确保无回归

4. **重复 2-3** 直到所有文件修复完成

5. **Phase 4**: 更新 Application Services

6. **全量测试并合并**
