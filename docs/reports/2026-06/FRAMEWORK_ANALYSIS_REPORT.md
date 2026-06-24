# quantsys-v2 项目框架分析报告

**分析日期**: 2026-06-24  
**项目**: pi-investment (AI 股票投资顾问系统)  
**架构**: TypeScript Agent (前端) + Python quantsys-v2 (后端)

---

## 📊 执行摘要

### 当前框架覆盖率

| 维度 | TypeScript (agent-ts) | Python (quantsys-v2) | 状态 |
|------|----------------------|---------------------|------|
| **测试框架** | ✅ Jest + Vitest (243 测试文件) | ✅ Pytest (1919 测试文件) | 良好 |
| **日志系统** | ⚠️ 自定义 observable-logger | ❌ 缺少结构化日志 | 需改进 |
| **错误监控** | ❌ 无 APM (Sentry/DataDog) | ❌ 无异常追踪 | 严重缺失 |
| **数据验证** | ❌ 缺少 schema 验证 | ⚠️ 部分使用 Pydantic | 需加强 |
| **性能监控** | ❌ 无性能分析工具 | ❌ 无性能追踪 | 缺失 |
| **API 网关** | ❌ 直接调用后端 | ❌ 无 API 管理 | 需添加 |
| **缓存层** | ❌ 无缓存策略 | ⚠️ Redis (配置未知) | 待验证 |
| **重试机制** | ❌ 无统一重试 | ❌ 无容错处理 | 严重缺失 |
| **健康检查** | ❌ 无健康探针 | ❌ 无服务监控 | 缺失 |

### 核心问题

🔴 **P0 - 生产级问题**:
1. **错误监控缺失**: 无法追踪生产环境异常（工具崩溃、数据计算错误）
2. **日志系统不完整**: 工具调用参数记录为 null，无法复现问题
3. **数据验证不足**: ML 工具崩溃（Segmentation Fault）由 NaN 值传播引起

🟡 **P1 - 稳定性问题**:
4. **重试机制缺失**: Python 脚本失败后静默退出，无重试
5. **性能监控缺失**: 无法识别性能瓶颈和内存泄漏
6. **健康检查缺失**: 无法及时发现后端服务异常

---

## 🔍 详细分析


### 1. 测试框架 ✅ (已有，但覆盖率不足)

#### 当前状态
- **TypeScript**: Jest + Vitest，243 个测试文件
- **Python**: Pytest，1919 个测试文件
- **配置**: 完整的 jest.config.js 和 pytest.ini

#### 问题
```
❌ 缺少集成测试覆盖工具调用链（TypeScript → Python）
❌ 缺少端到端测试（E2E）验证完整流程
❌ 测试覆盖率未知（未运行 coverage report）
⚠️ 单元测试可能未覆盖边界条件（NaN、空数据、网络超时）
```

#### 建议框架
**现有框架保留**，但需要增强：

1. **集成测试层** (优先级 P0)
   - 框架: **Playwright** (已安装) 或 **Supertest**
   - 用途: 测试 TypeScript 工具 → Python API 的完整调用链
   - 示例:
     ```typescript
     // agent-ts/src/__tests__/integration/model-predict.integration.test.ts
     describe('model_predict tool integration', () => {
       it('should handle insufficient data gracefully', async () => {
         const result = await modelPredictTool.execute({
           symbol: '600000',
           model_id: 'latest'
         });
         expect(result.success).toBe(true);
         expect(result.data).not.toContain('NaN');
       });
     });
     ```

2. **Contract Testing** (优先级 P1)
   - 框架: **Pact** 或 **OpenAPI Validator**
   - 用途: 确保 TypeScript 和 Python API 契约一致
   - 配置:
     ```json
     // package.json
     {
       "devDependencies": {
         "@pact-foundation/pact": "^12.0.0"
       }
     }
     ```

3. **Coverage 报告自动化** (优先级 P1)
   - 集成 codecov 或 coveralls
   - CI/CD 中强制最低覆盖率 (推荐 80%)

---

### 2. 日志系统 ⚠️ (自定义实现，不完整)

#### 当前状态
- **TypeScript**: 自定义 `observable-logger.ts`
  - 记录工具调用、LLM 请求、对话历史
  - **问题**: 工具参数记录为 `params: null`（TOOL_ERROR_ANALYSIS.md 第 12-26 行）

- **Python**: 基础 logging 模块
  - 缺少结构化日志
  - 缺少分布式追踪（无 trace ID）

#### 问题
```
🔴 工具调用参数丢失，无法调试失败原因
🔴 无法关联跨服务日志（TypeScript → Python 调用链）
🔴 日志格式不统一（JSON vs 文本）
❌ 缺少日志聚合和搜索能力
```

#### 建议框架

**1. TypeScript 日志框架** (优先级 P0)
- 框架: **Winston** 或 **Pino**（性能更好）
- 理由:
  - 结构化 JSON 日志
  - 支持多种 transport（文件、console、远程）
  - 性能优秀（Pino 比 Winston 快 5x）

**实施方案**:
```typescript
// agent-ts/src/infrastructure/logging/logger.ts
import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
      translateTime: 'SYS:standard',
      ignore: 'pid,hostname'
    }
  },
  formatters: {
    level: (label) => ({ level: label.toUpperCase() }),
  },
  base: {
    env: process.env.NODE_ENV,
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

// 为每个请求添加 trace ID
export function createRequestLogger(traceId: string) {
  return logger.child({ traceId });
}
```

**修复 params: null 问题**:
```typescript
// session-factory.ts (根据 TOOL_ERROR_ANALYSIS.md 建议)
case 'tool_execution_start': {
  const fullInput = event.input || event.toolInput || event.params;
  logger.info({
    event: 'tool.call',
    toolName: event.toolName,
    toolId: event.toolCallId,
    params: fullInput, // ✅ 完整参数
  });
  
  if (event.toolName === 'bash' && fullInput?.command) {
    logger.debug(`Bash command: ${fullInput.command.substring(0, 500)}`);
  }
  break;
}
```

**2. Python 日志框架** (优先级 P0)
- 框架: **structlog**
- 理由:
  - 结构化 JSON 输出
  - 支持上下文绑定（trace ID）
  - 与 Pydantic 配合良好

**实施方案**:
```python
# quantsys-v2/infrastructure/logging/logger.py
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# 使用示例
logger.info("ml_predict_called", symbol="600000", model_version="v2.3.1")
```

**3. 分布式追踪** (优先级 P1)
- 框架: **OpenTelemetry** (轻量级) 或 **Jaeger** (完整方案)
- 用途: 追踪请求跨 TypeScript → Python → Database 的完整路径

```bash
# 添加依赖
npm install @opentelemetry/api @opentelemetry/sdk-node
pip install opentelemetry-api opentelemetry-sdk
```

---

### 3. 错误监控 ❌ (严重缺失)

#### 当前状态
```
❌ 无 APM (Application Performance Monitoring)
❌ 无异常追踪系统
❌ 生产环境错误需要手动查日志
❌ 无告警机制
```

#### 问题案例
根据 TOOL_ERROR_ANALYSIS.md 和 URGENT_ML_PREDICT_FIX.md：
- ML 工具崩溃（Segmentation Fault）无法自动捕获
- 数据计算错误（-8761% 涨跌幅）无告警
- 工具静默失败（exit code 1，无输出）无通知

#### 建议框架

**方案 A: Sentry (推荐，开源免费版可用)** (优先级 P0)

**优势**:
- ✅ 自动捕获未处理异常
- ✅ 支持 TypeScript + Python
- ✅ 提供 Source Maps 支持
- ✅ 性能监控（慢查询、API 延迟）
- ✅ 免费额度足够小规模项目

**实施**:
```bash
# TypeScript
npm install @sentry/node @sentry/profiling-node

# Python
pip install sentry-sdk
```

```typescript
// agent-ts/src/infrastructure/monitoring/sentry.ts
import * as Sentry from '@sentry/node';
import { ProfilingIntegration } from '@sentry/profiling-node';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1, // 10% 性能追踪
  profilesSampleRate: 0.1,
  integrations: [
    new ProfilingIntegration(),
  ],
  beforeSend(event, hint) {
    // 过滤敏感信息
    if (event.request?.headers) {
      delete event.request.headers['authorization'];
    }
    return event;
  },
});

// 工具调用包装
export async function safeToolCall<T>(
  toolName: string,
  fn: () => Promise<T>
): Promise<T> {
  const transaction = Sentry.startTransaction({
    name: `tool.${toolName}`,
    op: 'tool.execute',
  });

  try {
    const result = await fn();
    transaction.setStatus('ok');
    return result;
  } catch (error) {
    transaction.setStatus('internal_error');
    Sentry.captureException(error, {
      tags: { tool: toolName },
      contexts: {
        tool: {
          name: toolName,
          timestamp: Date.now(),
        },
      },
    });
    throw error;
  } finally {
    transaction.finish();
  }
}
```

```python
# quantsys-v2/infrastructure/monitoring/sentry_init.py
import sentry_sdk
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    integrations=[
        SqlalchemyIntegration(),
    ],
    before_send=filter_sensitive_data,
)

# 包装 ML 工具调用
from sentry_sdk import start_transaction

def ml_predict_with_monitoring(symbol: str, model_id: str):
    with start_transaction(op="ml.predict", name=f"predict_{symbol}"):
        try:
            result = _ml_predict_core(symbol, model_id)
            return result
        except Exception as e:
            sentry_sdk.capture_exception(e)
            sentry_sdk.set_context("ml_context", {
                "symbol": symbol,
                "model_id": model_id,
                "data_points": len(data),
            })
            raise
```

**方案 B: 自建 - ELK Stack** (优先级 P2，成本较高)
- Elasticsearch + Logstash + Kibana
- 适合大规模部署
- 需要额外运维成本

**方案 C: 云原生 - AWS CloudWatch / Azure Monitor** (优先级 P2)
- 如果已使用云平台，可直接集成
- 成本按用量计费

---

### 4. 数据验证 ⚠️ (部分缺失)

#### 当前状态
- **Python**: 使用 Pydantic v2 (requirements.txt 第 27 行)
- **TypeScript**: 使用 @sinclair/typebox (package.json 第 33 行)

#### 问题
根据 URGENT_ML_PREDICT_FIX.md：
```
🔴 NaN 值传播到 sklearn.StandardScaler 导致崩溃
🔴 数据计算错误（-8761% 涨跌幅）未被验证层捕获
❌ API 响应未进行 schema 验证
❌ 工具输入参数缺少严格验证
```

#### 建议框架

**1. Python 输入/输出验证** (优先级 P0)

**增强 Pydantic 验证**:
```python
# quantsys-v2/domain/models/ml_request.py
from pydantic import BaseModel, Field, validator
import numpy as np
import pandas as pd

class MLPredictRequest(BaseModel):
    symbol: str = Field(..., pattern=r'^\d{6}$')  # 6 位数字
    model_version: str
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Symbol must be 6-digit code')
        return v

class FeatureDataFrame(BaseModel):
    """验证特征 DataFrame"""
    
    @validator('*', pre=True)
    def check_no_nan(cls, v):
        if isinstance(v, (pd.DataFrame, pd.Series)):
            if v.isnull().any().any():
                raise ValueError(f"NaN values found in features")
        if isinstance(v, np.ndarray):
            if np.isnan(v).any():
                raise ValueError(f"NaN values in array")
        return v
    
    @validator('*', pre=True)
    def check_no_inf(cls, v):
        if isinstance(v, (pd.DataFrame, pd.Series)):
            if np.isinf(v.values).any():
                raise ValueError(f"Inf values found in features")
        return v

# 在特征工程中应用
def prepare_features_safe(df: pd.DataFrame) -> pd.DataFrame:
    features = prepare_features(df)
    
    # 验证步骤
    if features.isnull().any().any():
        logger.error(f"NaN detected: {features.isnull().sum()}")
        raise ValueError("Features contain NaN after preparation")
    
    if np.isinf(features.values).any():
        logger.error(f"Inf detected in features")
        raise ValueError("Features contain Inf after preparation")
    
    return features
```

**2. TypeScript API 响应验证** (优先级 P0)

**使用 Zod 或 TypeBox 验证 Python API 响应**:
```typescript
// agent-ts/src/infrastructure/adapters/quant/schemas.ts
import { Type, Static } from '@sinclair/typebox';

export const MLPredictResponseSchema = Type.Object({
  success: Type.Boolean(),
  data: Type.Optional(Type.Object({
    symbol: Type.String(),
    prediction: Type.Number({ minimum: -100, maximum: 100 }), // ✅ 防止 -8761% 异常值
    confidence: Type.Number({ minimum: 0, maximum: 1 }),
    features_used: Type.Array(Type.String()),
  })),
  error: Type.Optional(Type.String()),
});

export type MLPredictResponse = Static<typeof MLPredictResponseSchema>;

// 验证响应
import Ajv from 'ajv';
const ajv = new Ajv();

async function callMLPredict(symbol: string): Promise<MLPredictResponse> {
  const response = await fetch(`${API_BASE}/ml/predict`, {
    method: 'POST',
    body: JSON.stringify({ symbol }),
  });
  
  const data = await response.json();
  
  // ✅ 验证 schema
  const validate = ajv.compile(MLPredictResponseSchema);
  if (!validate(data)) {
    logger.error('Invalid API response', {
      errors: validate.errors,
      data: JSON.stringify(data).substring(0, 500),
    });
    throw new Error(`API response validation failed: ${ajv.errorsText(validate.errors)}`);
  }
  
  return data;
}
```

**3. 数据质量检查框架** (优先级 P1)

**添加 Great Expectations**:
```python
# quantsys-v2/infrastructure/data_quality/expectations.py
from great_expectations.dataset import PandasDataset

def validate_stock_data(df: pd.DataFrame) -> bool:
    """验证股票数据质量"""
    ge_df = PandasDataset(df)
    
    # 检查必需列
    ge_df.expect_column_to_exist('close')
    ge_df.expect_column_to_exist('volume')
    
    # 检查价格范围
    ge_df.expect_column_values_to_be_between('close', min_value=0.01, max_value=10000)
    
    # 检查无 NaN
    ge_df.expect_column_values_to_not_be_null('close')
    
    # 检查成交量正数
    ge_df.expect_column_values_to_be_greater_than('volume', 0)
    
    results = ge_df.validate()
    if not results.success:
        logger.error(f"Data quality check failed: {results}")
    return results.success
```

---


### 5. 重试机制 ❌ (严重缺失)

#### 当前状态
```
❌ Python 脚本失败后静默退出（exit code 1，无输出）
❌ 网络请求（akshare、baostock）无重试
❌ 数据库连接失败无重试
❌ ML 模型调用失败无降级
```

#### 问题案例
TOOL_ERROR_ANALYSIS.md 显示：
- Turn 65-69: 3 次连续 bash 调用失败，无输出
- Turn 82-83: 2 次失败，无重试
- 总计 11 次失败，无任何重试尝试

#### 建议框架

**1. TypeScript 重试框架** (优先级 P0)
- 框架: **p-retry** 或 **axios-retry**

```typescript
// agent-ts/src/infrastructure/adapters/retry.ts
import pRetry from 'p-retry';

export async function retryableRequest<T>(
  fn: () => Promise<T>,
  options: {
    retries?: number;
    minTimeout?: number;
    onFailedAttempt?: (error: any) => void;
  } = {}
): Promise<T> {
  return pRetry(fn, {
    retries: options.retries ?? 3,
    minTimeout: options.minTimeout ?? 1000,
    maxTimeout: 10000,
    factor: 2, // 指数退避
    onFailedAttempt: (error) => {
      logger.warn(`Attempt ${error.attemptNumber} failed`, {
        retriesLeft: error.retriesLeft,
        error: error.message,
      });
      options.onFailedAttempt?.(error);
    },
  });
}

// 使用示例 - Python API 调用
export async function callQuantsysAPI(endpoint: string, params: any) {
  return retryableRequest(
    async () => {
      const response = await fetch(`${QUANTSYS_API}${endpoint}`, {
        method: 'POST',
        body: JSON.stringify(params),
        timeout: 30000,
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      return response.json();
    },
    {
      retries: 3,
      onFailedAttempt: (error) => {
        Sentry.captureMessage(`API retry attempt ${error.attemptNumber}`, {
          level: 'warning',
          tags: { endpoint },
        });
      },
    }
  );
}
```

**2. Python 重试框架** (优先级 P0)
- 框架: **tenacity** (更强大) 或 **backoff**

```python
# quantsys-v2/infrastructure/retry/decorators.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)

# 网络请求重试装饰器
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def fetch_stock_data(symbol: str):
    """带重试的股票数据获取"""
    try:
        data = akshare.stock_zh_a_hist(symbol=symbol)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch {symbol}: {e}")
        raise

# 数据库操作重试
from sqlalchemy.exc import OperationalError, DBAPIError

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((OperationalError, DBAPIError)),
)
def db_query_with_retry(query_func):
    """数据库查询重试包装"""
    return query_func()

# ML 模型调用带降级
from tenacity import RetryError

def ml_predict_with_fallback(symbol: str, model_id: str):
    """ML 预测带降级策略"""
    try:
        @retry(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=5),
        )
        def predict():
            return _ml_predict_core(symbol, model_id)
        
        return predict()
    except RetryError:
        logger.warning(f"ML predict failed after retries, using rule-based fallback")
        return rule_based_signal(symbol)  # 降级到规则策略
```

**3. Circuit Breaker 熔断器** (优先级 P1)
- 框架: **pybreaker** (Python) + **opossum** (TypeScript)
- 用途: 防止级联失败，保护下游服务

```python
# quantsys-v2/infrastructure/circuit_breaker/breaker.py
from pybreaker import CircuitBreaker

# 为外部 API 创建熔断器
akshare_breaker = CircuitBreaker(
    fail_max=5,           # 5 次失败后开启
    timeout_duration=60,  # 60 秒后尝试恢复
)

@akshare_breaker
def fetch_from_akshare(symbol: str):
    return akshare.stock_zh_a_hist(symbol=symbol)

# 熔断时的回调
from pybreaker import CircuitBreakerError

def fetch_with_fallback(symbol: str):
    try:
        return fetch_from_akshare(symbol)
    except CircuitBreakerError:
        logger.warning(f"Circuit breaker open, using baostock fallback")
        return baostock.query_history_k_data(code=symbol)
```

---

### 6. API 网关 ❌ (缺失)

#### 当前状态
```
❌ TypeScript 直接调用 Python HTTP API
❌ 无 API 版本管理
❌ 无请求限流
❌ 无统一鉴权
❌ 无 API 文档自动生成
```

#### 建议框架

**方案 A: 轻量级 - Express Gateway + FastAPI** (优先级 P1)

**1. Python 侧 - FastAPI 替换 Flask**
```python
# quantsys-v2/api/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Quantsys V2 API",
    version="2.0.0",
    docs_url="/api/docs",  # 自动生成 Swagger UI
    redoc_url="/api/redoc",
)

# 中间件
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求/响应模型
class MLPredictRequest(BaseModel):
    symbol: str
    model_version: str = "latest"

class MLPredictResponse(BaseModel):
    success: bool
    prediction: float | None = None
    confidence: float | None = None
    error: str | None = None

# 路由
@app.post("/api/v2/ml/predict", response_model=MLPredictResponse)
async def predict(request: MLPredictRequest):
    try:
        result = await ml_predict_service.predict(
            request.symbol,
            request.model_version
        )
        return MLPredictResponse(
            success=True,
            prediction=result['prediction'],
            confidence=result['confidence'],
        )
    except Exception as e:
        logger.exception("ML predict failed")
        return MLPredictResponse(success=False, error=str(e))

# 健康检查
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
    }
```

**2. 请求限流**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/v2/ml/predict")
@limiter.limit("10/minute")  # 每分钟最多 10 次
async def predict(request: Request, data: MLPredictRequest):
    # ...
```

**方案 B: 完整方案 - Kong Gateway** (优先级 P2)
- 适合微服务架构
- 提供插件生态（限流、鉴权、监控）
- 学习曲线较高

---

### 7. 缓存层 ⚠️ (配置待验证)

#### 当前状态
- **Redis**: requirements.txt 中已包含 (第 38-39 行)
- **状态未知**: 未找到 Redis 配置文件

#### 问题
```
❌ 不确定 Redis 是否已启用
❌ 缺少缓存策略定义
❌ 股票数据、因子计算结果未缓存
❌ API 响应未缓存
```

#### 建议框架

**1. Python 缓存框架** (优先级 P1)
- 框架: **redis-py** + **cachetools** (本地缓存)

```python
# quantsys-v2/infrastructure/cache/redis_cache.py
import redis
from functools import wraps
import pickle
from typing import Any, Callable
import hashlib

class CacheManager:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=False)
    
    def cache_result(
        self,
        ttl: int = 3600,
        key_prefix: str = "",
    ):
        """装饰器：缓存函数结果"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                key_data = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()
                
                # 尝试从缓存读取
                cached = self.redis.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit: {func.__name__}")
                    return pickle.loads(cached)
                
                # 执行函数
                result = func(*args, **kwargs)
                
                # 写入缓存
                self.redis.setex(
                    cache_key,
                    ttl,
                    pickle.dumps(result)
                )
                return result
            return wrapper
        return decorator

cache_manager = CacheManager()

# 使用示例
@cache_manager.cache_result(ttl=300, key_prefix="stock_data")
def fetch_stock_data(symbol: str):
    """缓存 5 分钟"""
    return akshare.stock_zh_a_hist(symbol=symbol)

@cache_manager.cache_result(ttl=3600, key_prefix="factor")
def calculate_factors(symbol: str, start_date: str):
    """因子计算结果缓存 1 小时"""
    return expensive_factor_calculation(symbol, start_date)
```

**2. TypeScript 缓存** (优先级 P1)
- 框架: **ioredis** 或 **node-cache** (内存缓存)

```typescript
// agent-ts/src/infrastructure/cache/cache-manager.ts
import Redis from 'ioredis';

export class CacheManager {
  private redis: Redis;
  
  constructor() {
    this.redis = new Redis({
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      retryStrategy: (times) => Math.min(times * 50, 2000),
    });
  }
  
  async getOrCompute<T>(
    key: string,
    compute: () => Promise<T>,
    ttl: number = 3600
  ): Promise<T> {
    // 尝试获取缓存
    const cached = await this.redis.get(key);
    if (cached) {
      return JSON.parse(cached);
    }
    
    // 计算结果
    const result = await compute();
    
    // 写入缓存
    await this.redis.setex(key, ttl, JSON.stringify(result));
    
    return result;
  }
}

// 使用示例
const cache = new CacheManager();

async function getStockQuote(symbol: string) {
  return cache.getOrCompute(
    `quote:${symbol}`,
    () => fetchFromQuantsysAPI(symbol),
    60 // 1 分钟 TTL
  );
}
```

**3. 缓存策略定义** (优先级 P1)

| 数据类型 | TTL | 缓存键模式 | 失效策略 |
|---------|-----|----------|---------|
| 股票实时行情 | 60s | `quote:{symbol}` | 时间过期 |
| 日 K 线数据 | 1 天 | `kline:daily:{symbol}:{date}` | 时间过期 |
| 因子计算结果 | 1 小时 | `factor:{symbol}:{factor_name}` | LRU |
| ML 模型预测 | 30 分钟 | `ml:predict:{symbol}:{model_id}` | 时间过期 |
| 行业数据 | 1 小时 | `sector:{sector_name}` | 手动刷新 |

---

### 8. 性能监控 ❌ (缺失)

#### 当前状态
```
❌ 无性能追踪
❌ 无慢查询监控
❌ 无内存泄漏检测
❌ 不知道哪些 API 调用最慢
```

#### 建议框架

**1. APM (Application Performance Monitoring)** (优先级 P1)

**方案 A: Sentry Performance** (推荐)
- 集成在错误监控中，无需额外服务
- 自动追踪 HTTP 请求、数据库查询

```typescript
// 已在 Sentry 配置中启用
Sentry.init({
  tracesSampleRate: 0.1, // ✅ 10% 请求采样
});

// 手动追踪关键代码段
const transaction = Sentry.startTransaction({
  name: 'factor_calculation',
  op: 'compute',
});

const span = transaction.startChild({
  op: 'db.query',
  description: 'fetch historical data',
});

await fetchData();
span.finish();

transaction.finish();
```

**方案 B: New Relic / DataDog** (优先级 P2)
- 更强大，但成本较高
- 适合生产环境大规模部署

**2. 数据库查询监控** (优先级 P1)

```python
# quantsys-v2/infrastructure/monitoring/db_profiler.py
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration = time.time() - context._query_start_time
    
    if duration > 1.0:  # 慢查询：> 1 秒
        logger.warning(f"Slow query detected: {duration:.2f}s", extra={
            "query": statement[:200],
            "duration": duration,
        })
        
        # 发送到 Sentry
        sentry_sdk.capture_message(
            f"Slow query: {duration:.2f}s",
            level="warning",
            extras={"query": statement},
        )
```

**3. 自定义性能指标** (优先级 P1)

```python
# quantsys-v2/infrastructure/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# 定义指标
ml_predict_duration = Histogram(
    'ml_predict_duration_seconds',
    'ML prediction duration',
    ['model_version'],
)
ml_predict_errors = Counter(
    'ml_predict_errors_total',
    'ML prediction errors',
    ['error_type'],
)
data_fetch_duration = Histogram(
    'data_fetch_duration_seconds',
    'Data fetching duration',
    ['source'],
)

# 使用示例
def ml_predict_instrumented(symbol: str, model_id: str):
    start = time.time()
    try:
        result = ml_predict(symbol, model_id)
        ml_predict_duration.labels(model_version=model_id).observe(time.time() - start)
        return result
    except Exception as e:
        ml_predict_errors.labels(error_type=type(e).__name__).inc()
        raise
```

---

### 9. 健康检查 ❌ (缺失)

#### 当前状态
```
❌ 无服务健康探针
❌ 无依赖检查（数据库、Redis、外部 API）
❌ 无自动重启机制
❌ 无降级状态标识
```

#### 建议框架

**1. 健康检查端点** (优先级 P0)

```python
# quantsys-v2/api/health.py
from fastapi import APIRouter, Response, status
from datetime import datetime
import asyncio

router = APIRouter()

@router.get("/health")
async def health():
    """基础健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@router.get("/health/ready")
async def readiness():
    """就绪检查：验证所有依赖"""
    checks = {}
    all_healthy = True
    
    # 检查数据库
    try:
        db.execute("SELECT 1")
        checks['database'] = 'healthy'
    except Exception as e:
        checks['database'] = f'unhealthy: {e}'
        all_healthy = False
    
    # 检查 Redis
    try:
        redis_client.ping()
        checks['redis'] = 'healthy'
    except Exception as e:
        checks['redis'] = f'unhealthy: {e}'
        all_healthy = False
    
    # 检查外部 API
    try:
        response = await fetch_with_timeout('http://akshare-api.com/health', timeout=2)
        checks['akshare'] = 'healthy'
    except Exception as e:
        checks['akshare'] = f'degraded: {e}'
        # 不影响整体状态（可降级）
    
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response(
        content=json.dumps({
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }),
        status_code=status_code,
        media_type="application/json",
    )

@router.get("/health/live")
async def liveness():
    """存活检查：仅验证进程运行"""
    return {"status": "alive"}
```

**2. 进程管理器** (优先级 P1)
- 框架: **PM2** (Node.js) + **Supervisor** (Python)

```bash
# ecosystem.config.js (PM2 配置)
module.exports = {
  apps: [{
    name: 'quantsys-api',
    script: 'python',
    args: '-m uvicorn api.main:app --host 0.0.0.0 --port 8000',
    cwd: '/path/to/quantsys-v2',
    instances: 2,
    exec_mode: 'cluster',
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
    },
    health_check: {
      url: 'http://localhost:8000/health',
      interval: 30000,
      timeout: 5000,
    },
  }],
};
```

---


## 🎯 优先级实施路线图

### 阶段 1: 立即修复 (P0 - 本周完成)

**目标**: 修复影响系统稳定性的关键问题

#### 1.1 修复日志系统 (2 天)
```bash
# TypeScript
npm install pino pino-pretty

# Python
cd quantsys-v2 && pip install structlog
```

**任务清单**:
- [ ] 替换 observable-logger 为 Pino
- [ ] 修复 `params: null` 问题（session-factory.ts）
- [ ] 在 Python 中实施 structlog
- [ ] 添加 trace ID 关联跨服务日志

**验收标准**:
- 所有工具调用参数完整记录
- JSON 格式日志可搜索
- 能通过 trace ID 追踪完整请求链路

#### 1.2 实施错误监控 (1 天)
```bash
npm install @sentry/node @sentry/profiling-node
pip install sentry-sdk
```

**任务清单**:
- [ ] 注册 Sentry 账号（免费版）
- [ ] 集成 TypeScript 错误捕获
- [ ] 集成 Python 异常追踪
- [ ] 配置告警规则（Slack/邮件）

**验收标准**:
- ML 工具崩溃自动上报到 Sentry
- 数据计算异常触发告警
- 能查看完整堆栈和上下文

#### 1.3 增强数据验证 (1 天)

**任务清单**:
- [ ] 在特征工程中添加 NaN/Inf 检查
- [ ] 实施 Pydantic 输入验证
- [ ] 添加 API 响应 schema 验证（TypeBox）
- [ ] 添加百分比计算边界检查（-100% ~ +100%）

**验收标准**:
- NaN 值无法传递到 sklearn
- 百分比异常值（-8761%）被拒绝
- 所有工具调用参数通过验证

#### 1.4 实施重试机制 (1 天)
```bash
npm install p-retry
pip install tenacity
```

**任务清单**:
- [ ] 包装所有网络请求（akshare、baostock）
- [ ] 包装数据库查询
- [ ] 添加 ML 预测降级逻辑
- [ ] 配置指数退避策略

**验收标准**:
- 网络瞬断自动重试 3 次
- 数据库连接失败自动重连
- ML 失败降级到规则策略

---

### 阶段 2: 稳定性提升 (P1 - 2 周完成)

**目标**: 提升系统可靠性和可观测性

#### 2.1 实施 API 网关 (3 天)
```bash
cd quantsys-v2
pip install fastapi uvicorn slowapi
```

**任务清单**:
- [ ] Flask → FastAPI 迁移
- [ ] 添加自动 API 文档（Swagger）
- [ ] 实施请求限流
- [ ] 添加 CORS 和 GZIP 中间件

**验收标准**:
- API 文档自动生成（/api/docs）
- 限流生效（每分钟 10 次）
- 响应时间 < 200ms (P95)

#### 2.2 完善缓存层 (2 天)
```bash
npm install ioredis
pip install redis hiredis
```

**任务清单**:
- [ ] 启动 Redis 服务
- [ ] 实施缓存管理器（Python + TypeScript）
- [ ] 缓存股票数据（TTL 60s）
- [ ] 缓存因子计算（TTL 1h）
- [ ] 监控缓存命中率

**验收标准**:
- 重复查询命中缓存
- API 响应时间减少 50%+
- 缓存命中率 > 70%

#### 2.3 性能监控 (2 天)

**任务清单**:
- [ ] 启用 Sentry Performance（已包含在错误监控中）
- [ ] 实施慢查询监控（> 1s）
- [ ] 添加自定义指标（Prometheus）
- [ ] 创建性能监控仪表板

**验收标准**:
- 能识别最慢的 API 端点
- 慢查询自动告警
- 追踪内存使用趋势

#### 2.4 健康检查与自动恢复 (2 天)
```bash
npm install -g pm2
```

**任务清单**:
- [ ] 实施健康检查端点（/health, /ready, /live）
- [ ] 配置 PM2 进程管理
- [ ] 实施自动重启策略
- [ ] 添加降级状态标识

**验收标准**:
- 服务崩溃自动重启
- 健康检查失败触发告警
- 依赖不可用时服务降级运行

---

### 阶段 3: 测试覆盖 (P1 - 2 周完成)

**目标**: 提升测试覆盖率，防止回归

#### 3.1 集成测试 (3 天)

**任务清单**:
- [ ] 创建 TypeScript → Python 集成测试套件
- [ ] 测试所有关键工具调用链
- [ ] 测试错误场景（NaN、超时、限流）
- [ ] CI/CD 集成

**验收标准**:
- 集成测试覆盖率 > 80%
- 所有 P0 bug 有回归测试
- CI 中自动运行

#### 3.2 Contract Testing (2 天)
```bash
npm install @pact-foundation/pact
```

**任务清单**:
- [ ] 定义 API 契约（Pact）
- [ ] TypeScript 消费者测试
- [ ] Python 提供者验证
- [ ] 契约版本管理

**验收标准**:
- API 变更自动检测
- 不兼容变更阻止部署
- 契约文档自动生成

#### 3.3 性能测试 (2 天)
```bash
npm install -g autocannon
pip install locust
```

**任务清单**:
- [ ] 编写负载测试脚本
- [ ] 测试 API 吞吐量
- [ ] 测试并发极限
- [ ] 识别性能瓶颈

**验收标准**:
- API 支持 100 QPS
- P99 延迟 < 500ms
- 内存使用稳定

---

### 阶段 4: 高级特性 (P2 - 1 个月完成)

**目标**: 实施生产级企业特性

#### 4.1 分布式追踪 (1 周)
```bash
npm install @opentelemetry/api @opentelemetry/sdk-node
pip install opentelemetry-api opentelemetry-sdk
```

**任务清单**:
- [ ] 集成 OpenTelemetry
- [ ] 追踪跨服务调用链
- [ ] 可视化追踪（Jaeger/Zipkin）

#### 4.2 熔断器 (3 天)
```bash
npm install opossum
pip install pybreaker
```

**任务清单**:
- [ ] 为外部 API 添加熔断器
- [ ] 配置降级策略
- [ ] 监控熔断事件

#### 4.3 数据质量框架 (1 周)
```bash
pip install great-expectations
```

**任务清单**:
- [ ] 定义数据质量期望
- [ ] 自动数据验证
- [ ] 生成数据质量报告

---

## 📦 推荐框架总结

### TypeScript (agent-ts)

| 领域 | 框架 | 优先级 | 理由 |
|-----|------|-------|------|
| **日志** | Pino | P0 | 高性能，结构化，生态完善 |
| **错误监控** | Sentry | P0 | 开源免费版，功能强大 |
| **重试** | p-retry | P0 | 简单易用，支持指数退避 |
| **缓存** | ioredis | P1 | Redis 官方推荐，性能优秀 |
| **测试** | Jest (已有) + Playwright | P1 | 生态成熟，E2E 测试强大 |
| **验证** | TypeBox (已有) + Zod | P1 | 类型安全，运行时验证 |
| **APM** | Sentry Performance | P1 | 包含在 Sentry 中，无额外成本 |
| **追踪** | OpenTelemetry | P2 | 云原生标准，厂商中立 |
| **熔断** | Opossum | P2 | 成熟稳定，功能完善 |

### Python (quantsys-v2)

| 领域 | 框架 | 优先级 | 理由 |
|-----|------|-------|------|
| **日志** | structlog | P0 | 结构化，性能好，易集成 |
| **错误监控** | Sentry SDK | P0 | 与 TypeScript 统一监控 |
| **重试** | tenacity | P0 | 功能最强大，配置灵活 |
| **API** | FastAPI | P1 | 现代化，自动文档，异步支持 |
| **缓存** | redis-py (已有) | P1 | 官方客户端，稳定可靠 |
| **测试** | Pytest (已有) | P1 | Python 标准，插件丰富 |
| **验证** | Pydantic v2 (已有) | P0 | 类型安全，性能优秀 |
| **限流** | slowapi | P1 | Flask-Limiter 替代品 |
| **熔断** | pybreaker | P2 | 久经考验，配置简单 |
| **数据质量** | Great Expectations | P2 | 行业标准，报告完善 |

---

## 💰 成本估算

### 开发成本

| 阶段 | 工时 | 说明 |
|-----|-----|------|
| P0 立即修复 | 5 人日 | 日志、监控、验证、重试 |
| P1 稳定性提升 | 9 人日 | API 网关、缓存、性能监控、健康检查 |
| P1 测试覆盖 | 7 人日 | 集成测试、契约测试、性能测试 |
| P2 高级特性 | 10 人日 | 分布式追踪、熔断器、数据质量 |
| **总计** | **31 人日** | 约 6-8 周（1 人全职） |

### 基础设施成本（月度）

| 服务 | 方案 | 成本 | 说明 |
|-----|------|-----|------|
| **错误监控** | Sentry 免费版 | $0 | 5K errors/月 |
| | Sentry Team | $26/月 | 50K errors/月，推荐 |
| **Redis** | 自建 | $0 | 1GB 内存足够 |
| | Upstash (Serverless) | $10/月 | 托管方案 |
| **APM** | Sentry Performance | 包含 | 已含在 Sentry 订阅中 |
| | New Relic | $99/月 | 更强大，可选 |
| **日志存储** | 本地文件 | $0 | 短期可用 |
| | ELK Stack | $50+/月 | 长期推荐 |
| **总计（推荐配置）** | | **$36/月** | Sentry Team + Upstash |

---

## ⚠️ 风险与注意事项

### 技术风险

1. **迁移风险**
   - Flask → FastAPI 迁移可能影响现有客户端
   - **缓解**: 保持 API 兼容，使用版本前缀（/api/v2）

2. **性能开销**
   - 日志、监控、追踪增加 5-10% CPU 开销
   - **缓解**: 使用采样（10% 追踪，异步日志）

3. **学习曲线**
   - 团队需要学习新框架
   - **缓解**: 选择文档完善、社区活跃的框架

### 操作风险

1. **告警疲劳**
   - 过多告警导致忽略真实问题
   - **缓解**: 仅对 P0/P1 问题告警，设置合理阈值

2. **监控成本**
   - 日志和追踪数据量快速增长
   - **缓解**: 设置保留期（7-30 天），使用采样

---

## 🎬 下一步行动

### 本周立即开始

1. **今天**: 
   - [ ] 注册 Sentry 账号
   - [ ] 修复日志系统（params: null 问题）
   
2. **明天**:
   - [ ] 集成 Sentry（TypeScript + Python）
   - [ ] 实施数据验证（NaN/Inf 检查）

3. **本周末前**:
   - [ ] 实施重试机制
   - [ ] 部署到测试环境
   - [ ] 验证所有 P0 修复

### 本月目标

- [ ] 完成阶段 1 (P0 修复)
- [ ] 完成阶段 2 的 50% (API 网关 + 缓存)
- [ ] 建立 CI/CD 自动化测试

### 季度目标

- [ ] 完成所有 P0/P1 任务
- [ ] 测试覆盖率 > 80%
- [ ] 生产环境稳定运行 30 天无 P0 事故

---

## 📚 参考资源

### 文档
- [Pino 日志框架](https://getpino.io/)
- [Sentry Python SDK](https://docs.sentry.io/platforms/python/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Tenacity 重试库](https://tenacity.readthedocs.io/)
- [OpenTelemetry](https://opentelemetry.io/)

### 示例项目
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Node.js Production Practices](https://github.com/goldbergyoni/nodebestpractices)

### 监控配置
- [Sentry 最佳实践](https://docs.sentry.io/platforms/javascript/best-practices/)
- [Redis 缓存策略](https://redis.io/docs/manual/patterns/)

---

## 📝 附录：快速启动命令

### 安装所有 P0 依赖

```bash
# TypeScript
cd agent-ts
npm install pino pino-pretty p-retry @sentry/node @sentry/profiling-node

# Python
cd quantsys-v2
pip install structlog tenacity sentry-sdk fastapi uvicorn slowapi
```

### 启动完整堆栈

```bash
# 启动 Redis
redis-server

# 启动 Python 后端
cd quantsys-v2
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 启动 TypeScript Agent
cd agent-ts
npm run dev:log
```

### 运行测试

```bash
# TypeScript 测试
npm test -- --coverage

# Python 测试
pytest --cov=. --cov-report=html
```

---

**报告生成时间**: 2026-06-24  
**下次复审时间**: 2026-07-01 (完成阶段 1 后)  

