# FastAPI 迁移缺失内容清单

**生成日期**: 2026-06-26  
**当前状态**: 阶段 0 完成，58 个 Flask 路由待迁移

---

## 📊 迁移进度概览

### 当前状态
- ✅ **FastAPI 基础设施**: 100% 完成
- ⏳ **路由迁移**: 1/58 完成（2%）
- ⏳ **WebSocket**: 未开始
- ⏳ **Service 层异步改造**: 未开始
- ⏳ **数据库异步适配**: 未开始

### 统计
```
Flask 路由文件: 58 个
FastAPI 路由文件: 1 个 (health.py)
迁移进度: 2% (1/58)
剩余工作量: 6-8 周
```

---

## 🔴 需要迁移的核心内容

### 1. API 路由层（58 个文件）

#### 优先级 P0 - 高并发/实时性模块（5-10 个）

**游戏智能相关**:
```
✅ test_di.py            - DI 测试（已完成）
❌ game_intelligence.py  - 对手行为分析
❌ game_alert.py         - 博弈告警
❌ decision_tracking.py  - 决策追踪
❌ knowledge_management.py - 知识管理
❌ learning_system.py    - 学习系统
```

**盘中监控相关**（新功能）:
```
❌ monitoring/alerts.py      - 告警管理（新建）
❌ monitoring/realtime.py    - 实时监控（新建）
```

**实时信号**:
```
❌ realtime_signals.py   - 实时信号推送
❌ signals_push.py       - 信号推送
```

#### 优先级 P1 - 常用模块（15-20 个）

**股票池管理**:
```
❌ pools.py              - 股票池 CRUD
❌ pool_scan.py          - 池子扫描
❌ pool_health.py        - 池子健康度
```

**策略管理**:
```
❌ strategies.py         - 策略 CRUD
❌ strategy_validation.py - 策略验证
```

**信号管理**:
```
❌ signals.py            - 信号查询
❌ signal_execution.py   - 信号执行
```

**回测系统**:
```
❌ backtest.py           - 回测执行
❌ backtest_history.py   - 回测历史
```

**分析工具**:
```
❌ analysis.py           - 数据分析
❌ charts.py             - 图表生成
❌ sentiment.py          - 情绪分析
```

**市场数据**:
```
❌ quote.py              - 行情数据
❌ quote_v2.py           - 行情数据 V2
❌ market_style.py       - 市场风格
```

#### 优先级 P2 - 其他模块（30+ 个）

**配置管理**:
```
❌ config.py             - 配置管理
❌ auth.py               - 认证授权
```

**订单和交易**:
```
❌ orders.py             - 订单管理
❌ executions.py         - 执行记录
❌ portfolio.py          - 投资组合
```

**数据质量**:
```
❌ data_quality.py       - 数据质量检查
❌ diagnosis.py          - 系统诊断
```

**其他**:
```
❌ benchmarks.py         - 基准管理
❌ chan.py               - 缠论分析
❌ opportunities.py      - 机会扫描
❌ watchlist.py          - 自选股
❌ risk_metrics.py       - 风险指标
... 剩余 20+ 个文件
```

---

### 2. WebSocket 实时推送

**Flask-SocketIO** (当前):
```python
# adapters/inbound/api/server_websocket.py
from flask_socketio import SocketIO

socketio = SocketIO(app)

@socketio.on('subscribe_alerts')
def handle_subscribe(data):
    emit('alert', {'message': 'New alert'})
```

**FastAPI WebSocket** (目标):
```python
# adapters/inbound/fastapi_app/websocket/alerts.py
from fastapi import WebSocket

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        await websocket.send_json({"type": "alert", "data": data})
```

**需要迁移的 WebSocket**:
- ❌ 告警推送 - `/ws/alerts`
- ❌ 行情推送 - `/ws/market`
- ❌ 信号推送 - `/ws/signals`

---

### 3. Service 层异步改造

**当前（同步）**:
```python
# application/services/opponent_behavior_service.py
class OpponentBehaviorService:
    def analyze_current_behavior(self):
        # 同步数据库查询
        data = self.repo.fetch_data()
        return self._analyze(data)
```

**目标（异步）**:
```python
class OpponentBehaviorService:
    async def analyze_current_behavior(self):
        # 异步数据库查询
        data = await self.repo.fetch_data_async()
        return self._analyze(data)
```

**需要改造的 Service**（估计 20-30 个）:
- ❌ OpponentBehaviorService
- ❌ BattlefieldAssessor
- ❌ ManipulationDetector
- ❌ StockPoolService
- ❌ StrategyCodeService
- ❌ SignalExecutionScheduler
- ... 其他 15-25 个

---

### 4. Repository 层异步改造

**当前（psycopg2 同步）**:
```python
import psycopg2

class MarketRepository:
    def fetch_data(self):
        conn = psycopg2.connect(...)
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchall()
```

**目标（asyncpg 异步）**:
```python
import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession

class MarketRepository:
    async def fetch_data_async(self):
        async with AsyncSession(self.engine) as session:
            result = await session.execute(query)
            return result.scalars().all()
```

**需要改造的 Repository**（估计 15-20 个）:
- ❌ StockPoolORMRepository
- ❌ StrategyORMRepository
- ❌ KlineORMRepository
- ❌ StockORMRepository
- ... 其他 11-16 个

---

### 5. 数据模型定义（Pydantic）

**需要创建的模型**（估计 50-100 个）:

#### 请求模型（Request Models）
```python
class CreatePoolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    pool_type: str
    symbols: Optional[List[str]] = None
    filter_template: Optional[dict] = None
    description: Optional[str] = None

class UpdateStrategyRequest(BaseModel):
    ...

class ExecuteSignalRequest(BaseModel):
    ...
```

#### 响应模型（Response Models）
```python
class PoolResponse(BaseModel):
    id: int
    name: str
    pool_type: str
    member_count: int
    created_at: datetime

class StrategyResponse(BaseModel):
    ...

class SignalResponse(BaseModel):
    ...
```

#### 业务模型（Domain Models）
```python
class OpponentBehavior(BaseModel):
    retail: dict
    institution: dict
    hot_money: dict
    market_phase: str

class BattlefieldAssessment(BaseModel):
    ...
```

**估计需要定义的模型**:
- 请求模型: 30-40 个
- 响应模型: 30-40 个
- 业务模型: 20-30 个
- **总计**: 80-110 个 Pydantic 模型

---

### 6. 依赖注入集成

**需要完成**:
- ❌ 修复 Service 类型注解问题（10-15 个文件）
- ❌ 创建 FastAPI 兼容的 DI 容器
- ❌ 为 FastAPI 路由配置依赖注入

**FastAPI 依赖注入示例**:
```python
from fastapi import Depends

def get_stock_pool_service():
    return container.stock_pool_service()

@router.get("/pools")
async def list_pools(
    service: StockPoolService = Depends(get_stock_pool_service)
):
    pools = await service.list_pools_async()
    return {"data": pools}
```

---

### 7. 中间件和工具

**需要迁移/创建**:
- ❌ 异常处理中间件（已有全局处理，需扩展）
- ❌ 请求日志中间件
- ❌ 认证中间件（JWT）
- ❌ 限流中间件
- ❌ CORS 配置（已完成）

---

### 8. 测试用例

**需要编写**:
- ❌ FastAPI 路由单元测试（58 个路由）
- ❌ WebSocket 测试
- ❌ 异步 Service 测试
- ❌ 异步 Repository 测试
- ❌ 集成测试

**估计测试用例数量**: 150-200 个

---

### 9. 部署配置

**需要创建**:
- ❌ Dockerfile（FastAPI + Uvicorn）
- ❌ docker-compose.yml
- ❌ Gunicorn + Uvicorn workers 配置
- ❌ Nginx 反向代理配置
- ❌ Systemd service 文件

---

### 10. 文档和示例

**需要完善**:
- ❌ API 使用示例（基于 Swagger）
- ❌ WebSocket 客户端示例
- ❌ 性能对比报告
- ❌ 迁移检查清单
- ❌ 故障排查指南

---

## 📋 详细迁移清单（按模块）

### 游戏智能模块（7 个路由）
```
[ ] game_intelligence.py       - 对手行为、战场评估、操纵检测
[ ] game_alert.py              - 博弈告警
[ ] decision_tracking.py       - 决策追踪
[ ] knowledge_management.py    - 知识管理
[ ] learning_system.py         - 学习系统
[ ] opponent_flow.py           - 对手资金流向（如果存在）
[ ] market_regime.py           - 市场状态检测（如果存在）
```

### 股票池模块（3 个路由）
```
[ ] pools.py                   - 池子 CRUD、刷新、验证
[ ] pool_scan.py               - 池子扫描
[ ] pool_health.py             - 池子健康度（如果独立文件）
```

### 策略模块（2-3 个路由）
```
[ ] strategies.py              - 策略 CRUD
[ ] strategy_validation.py     - 策略验证（如果独立）
```

### 信号模块（4 个路由）
```
[ ] signals.py                 - 信号查询
[ ] realtime_signals.py        - 实时信号
[ ] signals_push.py            - 信号推送
[ ] signal_execution.py        - 信号执行（如果独立）
```

### 回测模块（2 个路由）
```
[ ] backtest.py                - 回测执行
[ ] backtest_history.py        - 回测历史
```

### 分析模块（4 个路由）
```
[ ] analysis.py                - 综合分析
[ ] charts.py                  - 图表生成
[ ] sentiment.py               - 情绪分析
[ ] risk_metrics.py            - 风险指标
```

### 市场数据模块（4 个路由）
```
[ ] quote.py                   - 行情查询
[ ] quote_v2.py                - 行情 V2
[ ] market_style.py            - 市场风格
[ ] market_data.py             - 市场数据（如果存在）
```

### 交易模块（3 个路由）
```
[ ] orders.py                  - 订单管理
[ ] executions.py              - 执行记录
[ ] portfolio.py               - 投资组合
```

### 系统模块（5 个路由）
```
[x] test_di.py                 - DI 测试（已迁移）
[ ] config.py                  - 配置管理
[ ] auth.py                    - 认证授权
[ ] diagnosis.py               - 系统诊断
[ ] data_quality.py            - 数据质量
```

### 其他模块（20+ 个路由）
```
[ ] benchmarks.py              - 基准管理
[ ] chan.py                    - 缠论分析
[ ] opportunities.py           - 机会扫描
[ ] watchlist.py               - 自选股
[ ] pipeline.py                - ML 管道
[ ] ... 其他路由
```

---

## ⏱️ 工作量估算

### 路由迁移（58 个）
- **简单路由**（30 个）: 30分钟/个 = 15 小时
- **中等路由**（20 个）: 1小时/个 = 20 小时
- **复杂路由**（8 个）: 2小时/个 = 16 小时
- **小计**: 51 小时 ≈ **6-7 天**

### Service 异步改造（20-30 个）
- **简单 Service**（15 个）: 30分钟/个 = 7.5 小时
- **复杂 Service**（10 个）: 1-2小时/个 = 15 小时
- **小计**: 22.5 小时 ≈ **3 天**

### Repository 异步改造（15-20 个）
- **平均**: 1小时/个
- **小计**: 17.5 小时 ≈ **2-3 天**

### Pydantic 模型定义（80-110 个）
- **平均**: 15分钟/个
- **小计**: 20-27.5 小时 ≈ **3-4 天**

### WebSocket 迁移
- **3 个 WebSocket 端点**: 2小时/个 = 6 小时 ≈ **1 天**

### 测试编写
- **单元测试**: 150-200 个 × 15分钟 = 37.5-50 小时 ≈ **5-6 天**

### 部署和文档
- **2-3 天**

---

## 📊 总工作量

```
路由迁移:         6-7 天
Service 改造:     3 天
Repository 改造:  2-3 天
Pydantic 模型:    3-4 天
WebSocket:        1 天
测试编写:         5-6 天
部署文档:         2-3 天
---
总计:             22-27 天 (约 5-6 周)
```

考虑调试、返工、集成问题等，**实际需要 6-8 周**。

---

## 🎯 推荐迁移策略

### 阶段 1: 核心高并发模块（1-2 周）
1. 游戏智能 API (7 个路由)
2. 实时信号 (2 个路由)
3. WebSocket 推送 (3 个端点)

### 阶段 2: 常用业务模块（2-3 周）
1. 股票池管理 (3 个路由)
2. 策略管理 (2 个路由)
3. 信号管理 (2 个路由)
4. 回测系统 (2 个路由)

### 阶段 3: 其他模块（2-3 周）
1. 分析工具 (4 个路由)
2. 市场数据 (4 个路由)
3. 交易模块 (3 个路由)
4. 系统模块 (4 个路由)
5. 其他模块 (20+ 个路由)

---

## 📝 下一步行动

**立即执行（选择一个）**:

**A. 开始迁移游戏智能 API**（推荐）
- 从 game_intelligence.py 开始
- 高价值模块，优先迁移

**B. 完善 FastAPI 基础设施**
- 添加认证中间件
- 配置依赖注入
- 创建更多工具函数

**C. 创建 Pydantic 模型库**
- 先定义核心模型
- 为后续路由迁移打基础

**D. 查看详细迁移计划**
- 了解每个模块的具体工作

---

**需要我开始哪个任务？**
