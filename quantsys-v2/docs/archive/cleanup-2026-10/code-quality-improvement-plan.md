# 代码质量提升计划

**目标**: 代码质量从 7/10 提升到 9/10  
**日期**: 2026-09-06  
**状态**: 进行中

---

## 当前状态分析

### 代码质量评分：7/10

**优势** ✅:
- 线程池 bug 已修复
- 六边形架构清晰
- 5,338 个测试用例

**问题** ⚠️:
1. 测试覆盖率未测量
2. 87 处 TODO/FIXME 未解决
3. 类型提示不完整
4. 错误处理不一致
5. Application 层 142 个 service 文件无分类
6. 数据访问层三套并存

---

## 提升路线图

### Phase 1: 测试与类型（1 周）- 7/10 → 8/10

#### 任务 1.1: 清理测试环境 ✅

**问题**: 75 个测试收集错误

**行动**:
```bash
# 清理 __pycache__
find . -type d -name __pycache__ -exec rm -rf {} +

# 修复重复测试文件名
# tests/api/test_exception_handlers.py 与 
# tests/adapters/inbound/test_exception_handlers.py 冲突
```

**优先级**: P0

---

#### 任务 1.2: 核心模块类型提示

**目标**: 核心模块达到 90% 类型覆盖

**关键文件**:
- `domain/trading/*.py` - 交易领域模型
- `domain/accounts/*.py` - 账户领域模型
- `domain/portfolio/*.py` - 持仓领域模型
- `application/services/trading_service.py`
- `application/services/portfolio_service.py`

**示例改进**:
```python
# ❌ Before
def get_positions(account_name):
    return self.repo.find_all(account_name)

# ✅ After
def get_positions(self, account_name: str) -> List[Position]:
    return self.repo.find_all(account_name)
```

**验证**:
```bash
# 使用 mypy 检查类型
mypy domain/trading --strict
mypy domain/accounts --strict
mypy domain/portfolio --strict
```

**预期提升**: +0.5 分

---

#### 任务 1.3: 统一错误处理

**问题**: 混用 Exception 和自定义异常

**方案**: 统一异常层次

```python
# domain/exceptions.py
class QuantSysError(Exception):
    """基础异常类"""
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(message)

class BusinessError(QuantSysError):
    """业务逻辑错误"""
    pass

class InsufficientFundsError(BusinessError):
    """资金不足"""
    def __init__(self, required: float, available: float):
        super().__init__(
            f"资金不足: 需要 {required}, 可用 {available}",
            code="INSUFFICIENT_FUNDS"
        )
        self.required = required
        self.available = available

class InsufficientSharesError(BusinessError):
    """持仓不足"""
    def __init__(self, symbol: str, required: int, available: int):
        super().__init__(
            f"{symbol} 持仓不足: 需要 {required}, 可用 {available}",
            code="INSUFFICIENT_SHARES"
        )
```

**FastAPI 错误处理器**:
```python
@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )
```

**预期提升**: +0.5 分

---

### Phase 2: 架构优化（2-3 周）- 8/10 → 8.5/10

#### 任务 2.1: Application 层重构

**问题**: 142 个 service 文件无分类

**方案**: 按领域分组

```
application/services/
├── trading/              # 交易相关（15 个）
│   ├── order_service.py
│   ├── execution_service.py
│   └── ...
├── portfolio/            # 持仓相关（12 个）
│   ├── position_service.py
│   ├── balance_service.py
│   └── ...
├── data/                 # 数据服务（20 个）
│   ├── kline_service.py
│   ├── factor_service.py
│   └── ...
├── strategy/             # 策略相关（18 个）
│   ├── backtest_service.py
│   ├── signal_service.py
│   └── ...
└── analytics/            # 分析服务（15 个)
    ├── performance_service.py
    ├── risk_service.py
    └── ...
```

**预期提升**: +0.3 分

---

#### 任务 2.2: 数据访问层统一

**问题**: DataProviderManager / DataService / Repository 职责重叠

**方案**: 统一入口

```python
# 统一规则：业务代码只调用 DataService
# DataService 内部决策：缓存 → 数据库 → 外部源

# ✅ 正确用法
from application.services.data_service import DataService

service = DataService()
klines = service.get_klines("600519.SH", "2026-01-01", "2026-09-06")

# ❌ 错误用法（禁止）
from adapters.outbound.repositories.kline_repository import KlineRepository
repo = KlineRepository()
klines = repo.get_daily_klines(...)  # 跨层调用
```

**强制检查**:
```bash
# 检测工具：detect_data_access_violations.py
python tools/detect_data_access_violations.py

# 输出违规：
# ❌ adapters/inbound/fastapi_app/routes/pools.py:45
#    直接调用 KlineRepository，应使用 DataService
```

**预期提升**: +0.2 分

---

### Phase 3: 清理与优化（1 周）- 8.5/10 → 9/10

#### 任务 3.1: TODO/FIXME 清理

**当前**: 87 处 TODO/FIXME

**目标**: 减少到 < 20 处

**分类处理**:
1. **可快速修复**（30 处）→ 立即修复
2. **需要设计**（25 处）→ 创建 Issue，添加到 backlog
3. **已过时**（20 处）→ 删除注释
4. **长期优化**（12 处）→ 标记为 P2，保留

**示例**:
```python
# ❌ Before
# TODO: 优化性能
def calculate_factors(self, df):
    ...

# ✅ After - 已修复
def calculate_factors(self, df: pd.DataFrame) -> pd.DataFrame:
    """计算因子（使用向量化提升 3x 性能）"""
    ...

# ✅ After - 转为 Issue
# GitHub Issue #234: 因子计算性能优化（P2）
def calculate_factors(self, df):
    ...
```

**预期提升**: +0.3 分

---

#### 任务 3.2: 性能隐患修复

**问题**: Polars 多线程竞争临时修复

**当前方案**: `POLARS_MAX_THREADS=4` 限流

**根本解决**:
1. 审计所有 Polars 使用位置
2. 确保线程安全（避免共享状态）
3. 使用 Polars 推荐的并行模式

**预期提升**: +0.2 分

---

## 验收标准

### 代码质量 9/10 的标准

| 维度 | 当前 | 目标 | 验收 |
|------|------|------|------|
| 测试覆盖率 | 未知 | 75%+ | pytest --cov |
| 类型覆盖率 | 30% | 80%+ | mypy --strict |
| TODO/FIXME | 87 | < 20 | grep 统计 |
| 架构合规 | 良好 | 优秀 | 无跨层调用 |
| 错误处理 | 不统一 | 统一 | 统一异常体系 |
| 性能 | 有隐患 | 稳定 | 无临时修复 |

---

## 执行时间表

| 阶段 | 时间 | 目标评分 |
|------|------|----------|
| Phase 1 | 第 1 周 | 8.0/10 |
| Phase 2 | 第 2-3 周 | 8.5/10 |
| Phase 3 | 第 4 周 | 9.0/10 |

**总计**: 4 周达到 9/10

---

## 快速行动（本周可完成）

如果只有 1 周时间，优先完成：

1. ✅ **核心模块类型提示**（2 天）
2. ✅ **统一错误处理**（1 天）
3. ✅ **TODO/FIXME 清理**（2 天）
4. ✅ **测试环境清理**（半天）

**预期**: 7/10 → 8.3/10

---

## 工具脚本

### 1. 类型覆盖率检查

```bash
# scripts/check_type_coverage.sh
#!/bin/bash
echo "检查核心模块类型覆盖率..."
mypy domain/trading --strict --no-error-summary 2>&1 | grep "error" | wc -l
mypy domain/accounts --strict --no-error-summary 2>&1 | grep "error" | wc -l
mypy domain/portfolio --strict --no-error-summary 2>&1 | grep "error" | wc -l
```

### 2. TODO 统计

```bash
# scripts/count_todos.sh
#!/bin/bash
echo "TODO/FIXME 统计:"
grep -r "TODO\|FIXME\|XXX\|HACK" --include="*.py" . | wc -l
```

### 3. 跨层调用检测

```bash
# scripts/detect_layer_violations.sh
#!/bin/bash
echo "检测跨层调用..."
python tools/detect_layer_violations.py
```

---

**文档版本**: 1.0  
**最后更新**: 2026-09-06
