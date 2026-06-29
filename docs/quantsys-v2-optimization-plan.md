# quantsys-v2 优化执行方案

**生成时间**: 2026-06-29  
**基于**: 规范化诊断报告

---

## 📋 优化优先级矩阵

| 优化项 | 影响 | 紧急度 | 工作量 | 优先级 | 状态 |
|--------|------|--------|--------|--------|------|
| 统一日志启动配置 | 高 | 高 | 1h | **P0** | 🔲 待执行 |
| 模拟账户使用 Decimal | 高 | 高 | 2h | **P0** | 🔲 待执行 |
| Service 层结构化日志 | 高 | 中 | 1d | **P1** | 🔲 待执行 |
| Repository 层结构化日志 | 高 | 中 | 1d | **P1** | 🔲 待执行 |
| 替换 print() 为 logger | 中 | 中 | 1d | **P1** | 🔲 待执行 |
| 清理 logging.basicConfig | 低 | 低 | 4h | **P2** | 🔲 待执行 |
| 补充单元测试 | 中 | 低 | 2d | **P2** | 🔲 待执行 |

---

## 🎯 P0 优化 - 立即执行（3小时）

### 优化 1: 统一日志启动配置（1小时）

#### 目标
消除 3 个启动文件中的重复 `logging.basicConfig`，使用统一的结构化日志配置。

#### 影响文件
1. `start_all.py` - 主启动脚本
2. `adapters/inbound/fastapi_app/main.py` - FastAPI 主应用
3. `adapters/inbound/fastapi_app/websocket_server.py` - WebSocket 服务

#### 当前问题
```python
# start_all.py (第52-55行)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# main.py (第34-37行)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**问题**: 配置相互覆盖，无法使用结构化日志（JSON、Trace ID、敏感信息过滤）

#### 优化方案
```python
# 方案：在每个启动入口调用统一配置
from infrastructure.logging import configure_structured_logging
import os

# 开发环境：彩色控制台
configure_structured_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("LOG_FORMAT") == "json",  # 通过环境变量控制
    enable_trace_id=True
)
```

#### 改动清单
- `start_all.py`:
  - 删除第 51-55 行的 `logging.basicConfig`
  - 在 `run_websocket()` 开头添加统一配置
  - 在 `run_scheduler()` 开头添加统一配置
  
- `adapters/inbound/fastapi_app/main.py`:
  - 删除第 34-37 行的 `logging.basicConfig`
  - 在 `lifespan()` 启动时添加统一配置
  
- `adapters/inbound/fastapi_app/websocket_server.py`:
  - 检查并删除 `logging.basicConfig`（如果存在）
  - 添加统一配置

#### 验证步骤
```bash
# 1. 重启服务
pkill -f "start_all.py"
python start_all.py &

# 2. 观察日志输出（应该是结构化格式）
tail -f logs/api.log

# 3. 测试 API
curl http://127.0.0.1:5001/api/health
```

#### 预期收益
- ✅ 日志格式统一
- ✅ 支持 JSON 格式输出（生产环境）
- ✅ 自动 Trace ID 追踪
- ✅ 敏感信息自动脱敏

---

### 优化 2: 模拟账户使用 Decimal（2小时）

#### 目标
将模拟交易中的金额计算从 `float` 改为 `Decimal`，避免浮点数精度问题。

#### 影响文件
1. `live_trading/simulation_broker.py` - 模拟券商
2. `live_trading/simulation_trader.py` - 模拟交易器

#### 当前问题
```python
# simulation_broker.py
commission = max(amount * self.commission_rate, 5)  # float 计算
filled_price = price * (1 + self.slippage_rate)  # float 计算

# 问题：金融计算可能出现精度误差
# 例如: 0.1 + 0.2 = 0.30000000000000004
```

#### 优化方案
```python
from decimal import Decimal, ROUND_HALF_UP

class SimulationBroker:
    def __init__(self, commission_rate: float = 0.0003, slippage_rate: float = 0.001):
        # 转换为 Decimal
        self.commission_rate = Decimal(str(commission_rate))
        self.slippage_rate = Decimal(str(slippage_rate))
    
    def buy(self, symbol: str, shares: int, price: Decimal, ...) -> Dict:
        # 所有计算使用 Decimal
        amount = Decimal(shares) * price
        commission = max(amount * self.commission_rate, Decimal('5'))
        filled_price = price * (Decimal('1') + self.slippage_rate)
        
        # 返回时转换为 float（用于 JSON 序列化）
        return {
            'amount': float(amount),
            'commission': float(commission),
            ...
        }
```

#### 改动清单

**simulation_broker.py**:
- `__init__`: 将 `commission_rate`, `slippage_rate` 转换为 `Decimal`
- `buy()`: 参数 `price` 改为 `Decimal`，所有计算使用 `Decimal`
- `sell()`: 同上

**simulation_trader.py**:
- `_load_account_from_db()`: 使用 `Decimal` 加载账户余额
- `_calculate_position_size()`: 使用 `Decimal` 计算仓位
- 所有涉及金额计算的地方改为 `Decimal`

#### 风险与兼容性
- **数据库**: SQLAlchemy Numeric 字段已支持 Decimal ✅
- **JSON 序列化**: 返回前转换为 float ✅
- **向后兼容**: 通过类型转换保证兼容 ✅

#### 验证步骤
```python
# 单元测试
pytest tests/test_simulation_broker.py -v

# 集成测试
python live_trading/simulation_trader.py --dry-run

# 验证精度
from decimal import Decimal
commission = Decimal('1000.00') * Decimal('0.0003')
assert commission == Decimal('0.3000')  # 精确到分
```

#### 预期收益
- ✅ 金额计算精确到分（避免累积误差）
- ✅ 符合金融行业最佳实践
- ✅ 通过单元测试验证精度

---

## 🚀 P1 优化 - 本周执行（2-3天）

### 优化 3: Service 层迁移到结构化日志（1天）

#### 范围
`application/services/` 目录下约 50 个文件

#### 示例改动
```python
# 改前
import logging
logger = logging.getLogger(__name__)

def refresh_pool(pool_id: str):
    logger.info(f"刷新股票池: {pool_id}")
    stocks = fetch_stocks(pool_id)
    logger.info(f"刷新完成，共 {len(stocks)} 只股票")

# 改后
import structlog
logger = structlog.get_logger(__name__)

def refresh_pool(pool_id: str):
    logger.info("pool_refresh_started", pool_id=pool_id)
    stocks = fetch_stocks(pool_id)
    logger.info("pool_refresh_completed", pool_id=pool_id, count=len(stocks))
```

#### 改动模板
1. 替换 `import logging` → `import structlog`
2. 替换 `logging.getLogger` → `structlog.get_logger`
3. 替换字符串拼接 → 键值对参数
4. 为关键操作添加 `@log_execution` 装饰器

#### 自动化工具
```bash
# 批量替换（需人工审核）
find application/services -name "*.py" -exec sed -i '' \
  's/import logging$/import structlog/g' {} \;

find application/services -name "*.py" -exec sed -i '' \
  's/logging.getLogger/structlog.get_logger/g' {} \;
```

---

### 优化 4: Repository 层迁移到结构化日志（1天）

#### 范围
`adapters/outbound/repositories/` 目录下约 30 个文件

#### 重点改造
- 所有数据库操作记录耗时
- 所有异常记录详细上下文
- 使用 `@log_execution` 装饰器

#### 示例
```python
from infrastructure.logging import log_execution
import structlog

logger = structlog.get_logger(__name__)

class StockRepository:
    
    @log_execution("get_stock")
    def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        logger.info("query_stock", symbol=symbol)
        
        try:
            stock = self.session.query(Stock).filter_by(symbol=symbol).first()
            
            if stock:
                logger.info("stock_found", symbol=symbol)
            else:
                logger.warning("stock_not_found", symbol=symbol)
            
            return stock
            
        except Exception as e:
            logger.error(
                "query_stock_failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

---

### 优化 5: 替换 print() 为 logger（1天）

#### 范围
全项目 146 处 `print()` 调用

#### 替换规则
```python
# 规则 1: 信息输出 → logger.info
print(f"Processing {symbol}...")
→ logger.info("processing_symbol", symbol=symbol)

# 规则 2: 错误输出 → logger.error
print(f"ERROR: {error}")
→ logger.error("operation_failed", error=str(error))

# 规则 3: 调试输出 → logger.debug
print(f"DEBUG: value = {value}")
→ logger.debug("debug_value", value=value)

# 规则 4: 警告输出 → logger.warning
print(f"WARNING: {msg}")
→ logger.warning("warning_message", message=msg)
```

#### 检测工具
```bash
# 查找所有 print() 调用
grep -rn "print(" --include="*.py" . | grep -v "# print" | wc -l

# 分文件统计
grep -rn "print(" --include="*.py" . | cut -d: -f1 | sort | uniq -c | sort -rn | head -20
```

---

## 📊 P2 优化 - 持续执行

### 优化 6: 清理 logging.basicConfig（半天）

#### 范围
38 个文件中的独立配置

#### 操作
```bash
# 查找所有 basicConfig
grep -rn "logging.basicConfig" --include="*.py" . | cut -d: -f1 | sort -u

# 逐个检查并删除
# 确保这些模块从启动入口继承配置
```

---

### 优化 7: 补充单元测试（1-2天）

#### 目标
测试覆盖率从当前水平提升到 80%+

#### 重点测试
1. **SimulationBroker**:
   - 买入/卖出订单
   - 手续费计算
   - 滑点计算
   - Decimal 精度验证

2. **SimulationTrader**:
   - 完整交易周期
   - 账户状态管理
   - 风险控制

3. **Repository**:
   - CRUD 操作
   - 事务管理
   - 异常处理

#### 测试模板
```python
import pytest
from decimal import Decimal
from live_trading.simulation_broker import SimulationBroker

class TestSimulationBroker:
    
    def test_buy_order_precision(self):
        """测试买入订单的 Decimal 精度"""
        broker = SimulationBroker(commission_rate=0.0003)
        
        result = broker.buy(
            symbol='600000',
            shares=100,
            price=Decimal('10.00'),
            order_type='limit'
        )
        
        # 验证精度
        expected_amount = Decimal('100') * Decimal('10.00')
        expected_commission = max(expected_amount * Decimal('0.0003'), Decimal('5'))
        
        assert Decimal(str(result['amount'])) == expected_amount
        assert Decimal(str(result['commission'])) == expected_commission
```

---

## 🔧 实施计划

### Week 1: P0 优化（3小时）
- **Day 1 上午**: 优化 1 - 统一日志启动配置（1h）
- **Day 1 下午**: 优化 2 - 模拟账户使用 Decimal（2h）
- **Day 1 晚上**: 验证测试 + 提交代码

### Week 2: P1 优化（2-3天）
- **Day 2**: 优化 3 - Service 层结构化日志（1d）
- **Day 3**: 优化 4 - Repository 层结构化日志（1d）
- **Day 4**: 优化 5 - 替换 print() 为 logger（1d）
- **Code Review + 测试**

### Week 3+: P2 优化（持续）
- **持续**: 清理 logging.basicConfig（遇到相关文件时顺便清理）
- **持续**: 补充单元测试（每次改动代码时补充对应测试）

---

## 📈 成功指标

### 量化指标
| 指标 | 当前值 | 目标值 | 完成标准 |
|------|--------|--------|----------|
| 独立日志配置文件数 | 38 | 0 | 所有文件使用统一配置 |
| print() 调用数 | 146 | 0 | 全部替换为 logger |
| 使用结构化日志的文件比例 | 0% | 80%+ | 核心模块全覆盖 |
| 模拟账户 float 使用 | 100% | 0% | 全部改为 Decimal |
| 测试覆盖率 | ? | 80%+ | pytest-cov 报告 |

### 质量指标
- ✅ 生产环境日志可被 ElasticSearch 解析
- ✅ 可通过 Trace ID 追踪完整请求链路
- ✅ 金融计算精度误差为 0
- ✅ 无日志配置冲突警告
- ✅ CI 检查通过（禁止新增 print/basicConfig）

---

## ⚠️ 风险与对策

### 风险 1: 日志格式变更影响下游
**影响**: 依赖日志格式的监控系统可能失效  
**对策**: 
- 在测试环境验证新格式
- 提供环境变量控制（`LOG_FORMAT=json` 或 `text`）
- 通知运维团队更新监控规则

### 风险 2: Decimal 性能影响
**影响**: Decimal 比 float 慢 10-20x  
**对策**:
- 仅在金融计算中使用 Decimal
- 非关键路径仍可使用 float
- 性能测试验证影响可接受

### 风险 3: 大量代码改动引入 Bug
**影响**: 可能破坏现有功能  
**对策**:
- 分批次小步迁移
- 每次改动运行完整测试套件
- 使用 Git 分支，合并前 Code Review

---

## 📚 参考文档

1. [日志规范化报告](docs/logging-standardization-report.md)
2. [模拟账户规范标准](docs/simulation-account-standard.md)
3. [structlog 官方文档](https://www.structlog.org/)
4. [Python Decimal 文档](https://docs.python.org/3/library/decimal.html)

---

## ✅ 检查清单

### P0 优化
- [ ] 优化 1: 统一日志启动配置（1h）
  - [ ] start_all.py 改造
  - [ ] main.py 改造
  - [ ] websocket_server.py 改造
  - [ ] 验证测试

- [ ] 优化 2: 模拟账户使用 Decimal（2h）
  - [ ] simulation_broker.py 改造
  - [ ] simulation_trader.py 改造
  - [ ] 单元测试
  - [ ] 集成测试

### P1 优化
- [ ] 优化 3: Service 层结构化日志
- [ ] 优化 4: Repository 层结构化日志
- [ ] 优化 5: 替换 print() 为 logger

### P2 优化
- [ ] 优化 6: 清理 logging.basicConfig
- [ ] 优化 7: 补充单元测试

---

**下一步**: 执行 P0 优化任务（预计 3 小时）
