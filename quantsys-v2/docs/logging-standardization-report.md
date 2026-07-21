# quantsys-v2 日志规范统一报告

**生成时间**: 2026-06-29  
**诊断范围**: 全项目 Python 代码

---

## 📊 当前状态诊断

### 1. 日志使用统计

| 指标 | 数量 | 说明 |
|------|------|------|
| 使用 `logging.getLogger` 的文件 | 820 | ✅ 推荐方式 |
| 使用 `logging.basicConfig` 的文件 | 38 | ⚠️ 需要统一 |
| 使用 `print()` 输出的文件 | 146 | ❌ 需要替换为 logging |
| 已有结构化日志配置 | 1 | ✅ 但未被使用 |

### 2. 日志配置混乱问题

#### ❌ **问题 1: 多处重复配置 `logging.basicConfig`**

发现 **38 个文件**独立配置日志，导致：
- 日志格式不统一
- 配置相互覆盖（后加载的覆盖先加载的）
- 难以集中管理日志级别

**典型示例**:
```python
# start_all.py
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# simulation_trader.py
logging.basicConfig(
    level=self.config['logging']['level'],
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[...]
)

# fastapi_app/main.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

#### ❌ **问题 2: 使用 `print()` 而非日志**

发现 **146 处** `print()` 调用，主要在：
- API 路由文件
- Service 层
- 脚本文件

**问题**:
- 无法控制输出级别（不能按需关闭）
- 无法记录到文件
- 无法添加上下文（时间戳、模块名）
- 生产环境难以调试

#### ⚠️ **问题 3: 已有结构化日志配置但未使用**

项目中已实现 `infrastructure/logging/config.py`，提供：
- ✅ 结构化日志（structlog）
- ✅ JSON 格式输出
- ✅ Trace ID 追踪
- ✅ 敏感信息过滤
- ✅ 装饰器支持

但**没有任何文件使用**这套配置！

---

## 🎯 规范方案

### 推荐架构

```
┌─────────────────────────────────────────────┐
│  启动入口 (start_all.py, main.py)          │
│  调用一次: configure_structured_logging()   │
└────────────┬────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────┐
│  各模块代码                                 │
│  import structlog                           │
│  logger = structlog.get_logger(__name__)    │
│  logger.info("event", key=value)            │
└─────────────────────────────────────────────┘
```

### 规范标准

#### 1. **启动时配置一次**

**在应用启动入口**（start_all.py, fastapi_app/main.py）配置：

```python
from infrastructure.logging import configure_structured_logging

# 开发环境：彩色控制台输出
configure_structured_logging(
    level="INFO",
    json_format=False,  # 易读的控制台格式
    enable_trace_id=True
)

# 生产环境：JSON 格式（便于日志收集系统解析）
configure_structured_logging(
    level="WARNING",
    json_format=True,  # 结构化 JSON
    enable_trace_id=True
)
```

#### 2. **模块中使用结构化日志**

```python
import structlog

logger = structlog.get_logger(__name__)

# ✅ 推荐：结构化日志（键值对）
logger.info(
    "trade_executed",
    symbol="600000",
    action="BUY",
    shares=100,
    price=10.50,
    account="default"
)

# 输出（开发环境）:
# 2026-06-29T12:00:00Z [info] trade_executed symbol=600000 action=BUY shares=100 price=10.50

# 输出（生产环境 JSON）:
# {"event": "trade_executed", "symbol": "600000", "action": "BUY", 
#  "shares": 100, "price": 10.50, "timestamp": "2026-06-29T12:00:00Z", "level": "info"}
```

#### 3. **敏感信息自动过滤**

```python
# 密码、Token 自动脱敏
logger.info("user_login", username="alice", password="secret123")
# 输出: {"event": "user_login", "username": "alice", "password": "***REDACTED***"}
```

#### 4. **使用装饰器记录函数执行**

```python
from infrastructure.logging import log_execution

@log_execution("ml_predict")
def predict_stock_price(symbol: str) -> float:
    # 自动记录开始/结束/耗时/异常
    return model.predict(symbol)

# 自动输出:
# ml_predict_started operation=ml_predict function=predict_stock_price
# ml_predict_completed operation=ml_predict duration_ms=245.3
```

#### 5. **Trace ID 追踪请求链路**

```python
from infrastructure.logging import get_trace_id, set_trace_id

# API 入口处设置 trace ID（从 header 传递）
@app.before_request
def before_request():
    trace_id = request.headers.get('X-Trace-ID')
    if trace_id:
        set_trace_id(trace_id)

# 后续所有日志自动包含相同的 trace_id
logger.info("processing_request", endpoint="/api/stocks")
# {"event": "processing_request", "endpoint": "/api/stocks", "trace_id": "a3b2c1d4"}
```

---

## 🔧 迁移计划

### Phase 1: 启动入口统一（P0 - 立即执行）

**目标**: 在所有启动入口配置统一日志

**改动文件**:
1. `start_all.py` (REST API, WebSocket, Scheduler)
2. `adapters/inbound/fastapi_app/main.py`
3. `adapters/inbound/fastapi_app/websocket_server.py`

**操作**:
```python
# 删除所有 logging.basicConfig
# 添加统一配置
from infrastructure.logging import configure_structured_logging

# 在 main() 或 lifespan() 中调用一次
configure_structured_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=os.getenv("LOG_FORMAT") == "json",
    enable_trace_id=True
)
```

### Phase 2: 核心模块迁移（P0）

**目标**: 核心业务逻辑使用结构化日志

**范围**:
- `application/services/`（所有 service 层）
- `adapters/outbound/repositories/`（数据访问层）
- `live_trading/simulation_trader.py`（模拟交易）

**操作**:
```python
# 替换
import logging
logger = logging.getLogger(__name__)

# 为
import structlog
logger = structlog.get_logger(__name__)

# 替换日志调用
logger.info(f"Trade executed: {symbol} {action}")
# 为
logger.info("trade_executed", symbol=symbol, action=action)
```

### Phase 3: 替换 print() 为 logger（P1）

**目标**: 消除所有 `print()` 调用

**操作**:
```python
# 替换
print(f"Processing {symbol}...")

# 为
logger.info("processing_symbol", symbol=symbol)

# 替换
print(f"ERROR: {error}")

# 为
logger.error("operation_failed", error=str(error))
```

### Phase 4: 清理遗留配置（P2）

**目标**: 删除所有独立的 `logging.basicConfig` 配置

**操作**:
- 删除 38 个文件中的 `logging.basicConfig` 调用
- 确保这些模块从启动入口继承配置

---

## 📋 标准模板

### 模板 1: Service 层

```python
"""
Stock Pool Service
"""
import structlog
from infrastructure.logging import log_execution

logger = structlog.get_logger(__name__)


class StockPoolService:
    
    @log_execution("refresh_pool")
    def refresh_pool(self, pool_id: str) -> dict:
        """刷新股票池"""
        logger.info("pool_refresh_started", pool_id=pool_id)
        
        try:
            # 业务逻辑
            stocks = self._fetch_stocks(pool_id)
            
            logger.info(
                "pool_refresh_completed",
                pool_id=pool_id,
                stock_count=len(stocks)
            )
            
            return {"success": True, "count": len(stocks)}
            
        except Exception as e:
            logger.error(
                "pool_refresh_failed",
                pool_id=pool_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

### 模板 2: API 路由

```python
"""
Stock API Routes
"""
import structlog
from fastapi import APIRouter, Request
from infrastructure.logging import set_trace_id

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/stocks")
async def get_stocks(request: Request, market: str = "A"):
    # 设置 trace ID（从 header 传递）
    trace_id = request.headers.get("X-Trace-ID")
    if trace_id:
        set_trace_id(trace_id)
    
    logger.info("api_request", endpoint="/stocks", market=market)
    
    try:
        stocks = await stock_service.get_stocks(market)
        
        logger.info(
            "api_response",
            endpoint="/stocks",
            status="success",
            count=len(stocks)
        )
        
        return {"success": True, "data": stocks}
        
    except Exception as e:
        logger.error(
            "api_error",
            endpoint="/stocks",
            error=str(e)
        )
        raise
```

### 模板 3: 脚本文件

```python
"""
Data Import Script
"""
import structlog
from infrastructure.logging import configure_structured_logging

# 脚本启动时配置日志
configure_structured_logging(level="INFO", json_format=False)
logger = structlog.get_logger(__name__)


def main():
    logger.info("script_started", script="import_data")
    
    try:
        # 执行任务
        result = import_stock_data()
        
        logger.info(
            "script_completed",
            script="import_data",
            records_imported=result['count']
        )
        
    except Exception as e:
        logger.error(
            "script_failed",
            script="import_data",
            error=str(e)
        )
        raise


if __name__ == "__main__":
    main()
```

---

## ✅ 迁移检查清单

- [ ] Phase 1: 启动入口统一（3 个文件）
- [ ] Phase 2: 核心模块迁移（~100 个文件）
- [ ] Phase 3: 替换 print()（146 处）
- [ ] Phase 4: 清理 basicConfig（38 个文件）
- [ ] 添加环境变量配置（LOG_LEVEL, LOG_FORMAT）
- [ ] 更新 CLAUDE.md 文档
- [ ] 团队培训：使用规范

---

## 🎁 收益

### 开发环境
- ✅ 彩色控制台输出（易读）
- ✅ 自动时间戳和模块名
- ✅ 异常堆栈自动格式化

### 生产环境
- ✅ JSON 格式（ElasticSearch/Splunk 可解析）
- ✅ Trace ID 追踪请求链路
- ✅ 敏感信息自动脱敏
- ✅ 结构化查询（按字段过滤）

### 代码质量
- ✅ 统一日志格式
- ✅ 更好的可测试性（mock logger）
- ✅ 减少字符串拼接（性能提升）
- ✅ 类型安全（键值对，不是字符串模板）

---

## 📚 参考文档

- [structlog 官方文档](https://www.structlog.org/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- 本项目实现: `infrastructure/logging/config.py`
