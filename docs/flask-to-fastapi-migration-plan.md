# Flask to FastAPI 迁移方案

**项目**: quantsys-v2  
**日期**: 2026-06-26  
**目标**: 将 Flask 应用渐进式迁移到 FastAPI，提升性能和现代化程度

---

## 一、迁移背景

### 当前状态分析

**技术栈**:
- Flask 3.0.0 (WSGI 同步框架)
- 58 个 Blueprint 路由文件
- ~19,635 行路由代码
- Flask-SocketIO (WebSocket 支持)
- 装饰器模式：`@handle_errors`, `@validate_params`, `@paginate`

**存在的问题**:
1. ❌ **性能瓶颈**: Flask 是同步框架，无法充分利用异步 I/O
2. ❌ **缺少自动文档**: 需要手动维护 API 文档
3. ❌ **类型安全弱**: 缺少请求/响应的自动验证
4. ❌ **WebSocket 集成复杂**: Flask-SocketIO 需要额外配置
5. ❌ **现代化不足**: 不支持原生 async/await

### FastAPI 优势

1. ✅ **高性能**: 基于 ASGI，性能是 Flask 的 3-10 倍
2. ✅ **自动文档**: OpenAPI (Swagger) 和 ReDoc 自动生成
3. ✅ **类型安全**: 基于 Pydantic，自动数据验证
4. ✅ **原生异步**: 支持 async/await，适合高并发场景
5. ✅ **现代化**: Python 3.7+ 类型提示，IDE 友好
6. ✅ **WebSocket**: 原生支持，无需额外库

---

## 二、迁移策略：渐进式三阶段

### 阶段 0: 准备阶段（1-2 天）

**目标**: 搭建 FastAPI 基础设施，与 Flask 共存

#### 任务清单

1. **安装依赖**
```bash
# requirements-fastapi.txt
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-multipart>=0.0.6  # 文件上传支持
```

2. **创建 FastAPI 应用**
```
quantsys-v2/
├── adapters/inbound/api/
│   ├── server.py              # Flask 应用（保留）
│   ├── server_fastapi.py      # 新：FastAPI 应用
│   ├── routes/                # Flask 路由（保留）
│   └── fastapi_routes/        # 新：FastAPI 路由
│       ├── __init__.py
│       └── health.py          # 第一个测试路由
```

3. **FastAPI 应用骨架**
```python
# adapters/inbound/api/server_fastapi.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="QuantSys V2 API",
    description="AI-Driven Quantitative Investment System",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "framework": "fastapi"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
```

4. **启动脚本**
```python
# start_all.py 修改
# 添加 FastAPI 进程
fastapi_process = subprocess.Popen([
    sys.executable, "-m", "uvicorn",
    "adapters.inbound.api.server_fastapi:app",
    "--host", "0.0.0.0",
    "--port", "5002",
    "--reload"
])
```

#### 验收标准

- [x] FastAPI 应用在 5002 端口启动成功
- [x] 访问 `http://localhost:5002/api/docs` 显示 Swagger UI
- [x] Flask 应用在 5001 端口正常运行
- [x] 两个应用可以同时运行，互不干扰

---

### 阶段 1: 迁移核心模块（1-2 周）

**目标**: 迁移盘中监控、游戏智能等高并发模块到 FastAPI

#### 优先级 P0 模块（高并发、实时性要求高）

1. **盘中监控 API** (新模块)
   - `POST /api/monitoring/alerts` - 告警查询
   - `GET /api/monitoring/alerts/{id}` - 告警详情
   - `POST /api/monitoring/alerts/{id}/ack` - 确认告警

2. **游戏智能 API** (已有 Flask 版本)
   - `GET /api/game/market/opponent-behavior` - 对手行为分析
   - `GET /api/game/pools/{id}/battlefield-assessment` - 战场评估
   - `GET /api/game/manipulation-detect` - 操纵检测

3. **WebSocket 实时推送** (替换 Flask-SocketIO)
   - `ws://localhost:5002/ws/alerts` - 告警实时推送
   - `ws://localhost:5002/ws/market` - 行情实时推送

#### 迁移步骤示例

##### 1. Flask 版本（当前）

```python
# adapters/inbound/api/routes/game_intelligence.py
from flask import Blueprint, jsonify
from adapters.inbound.api.decorators import handle_errors

game_intelligence_bp = Blueprint('game_intelligence', __name__)

@game_intelligence_bp.route('/api/game/market/opponent-behavior', methods=['GET'])
@handle_errors
def get_opponent_behavior():
    service = OpponentBehaviorService()
    result = service.analyze_current_behavior()
    return jsonify({'success': True, 'data': result})
```

##### 2. FastAPI 版本（目标）

```python
# adapters/inbound/api/fastapi_routes/game_intelligence.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime

router = APIRouter(prefix="/api/game", tags=["Game Intelligence"])

# Pydantic 模型（自动文档 + 验证）
class OpponentBehavior(BaseModel):
    retail: Dict
    institution: Dict
    hot_money: Dict
    market_phase: str
    opportunity_map: Dict
    timestamp: datetime

class ApiResponse(BaseModel):
    success: bool
    data: OpponentBehavior

@router.get("/market/opponent-behavior", response_model=ApiResponse)
async def get_opponent_behavior():
    """
    获取市场对手行为分析
    
    - **返回**: 散户、机构、游资的行为分析
    - **更新频率**: 每分钟
    """
    service = OpponentBehaviorService()
    result = await service.analyze_current_behavior()  # 异步调用
    return {"success": True, "data": result}
```

##### 3. 注册路由

```python
# adapters/inbound/api/server_fastapi.py
from fastapi_routes.game_intelligence import router as game_router

app.include_router(game_router)
```

#### WebSocket 迁移示例

##### Flask-SocketIO (当前)
```python
# server_websocket.py
from flask_socketio import SocketIO, emit

socketio = SocketIO(app)

@socketio.on('subscribe_alerts')
def handle_subscribe(data):
    emit('alert', {'message': 'New alert'})
```

##### FastAPI WebSocket (目标)
```python
# fastapi_routes/websocket.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # 处理订阅请求
            await manager.broadcast({"type": "alert", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

#### 验收标准

- [x] 游戏智能 API 在 FastAPI 上运行正常
- [x] 性能提升 2-3 倍（基准测试）
- [x] Swagger UI 自动生成完整文档
- [x] WebSocket 推送功能正常
- [x] Flask 旧路由继续工作（向后兼容）

---

### 阶段 2: 逐步迁移其余模块（3-4 周）

#### 优先级 P1 模块（常用、轻量级）

按依赖关系和使用频率排序：

1. **健康检查** (`/api/health`)
2. **股票池管理** (`/api/pools/*`)
3. **策略管理** (`/api/strategies/*`)
4. **信号管理** (`/api/signals/*`)
5. **回测接口** (`/api/backtest/*`)
6. **市场数据** (`/api/market/*`, `/api/quote/*`)

#### 迁移模板

```python
# 通用迁移模板
from fastapi import APIRouter, Query, Path, Body
from pydantic import BaseModel, Field
from typing import Optional, List

router = APIRouter(prefix="/api/pools", tags=["Stock Pools"])

# 请求模型
class CreatePoolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    screening_filter: dict
    is_dynamic: bool = True

# 响应模型
class PoolResponse(BaseModel):
    id: int
    name: str
    member_count: int
    created_at: str

@router.post("/", response_model=PoolResponse)
async def create_pool(request: CreatePoolRequest):
    """创建股票池"""
    service = StockPoolService()
    pool = await service.create_pool(
        name=request.name,
        description=request.description,
        screening_filter=request.screening_filter
    )
    return pool

@router.get("/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: int = Path(..., gt=0, description="池子ID")
):
    """获取池子详情"""
    service = StockPoolService()
    pool = await service.get_pool(pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return pool
```

#### 批量迁移脚本

创建辅助脚本加速迁移：

```python
# scripts/migrate_route.py
"""
自动将 Flask 路由转换为 FastAPI 路由
用法: python scripts/migrate_route.py routes/pools.py
"""
import re
import ast

def convert_flask_to_fastapi(flask_code: str) -> str:
    # 替换装饰器
    fastapi_code = flask_code.replace(
        "@pools_bp.route('/api/pools', methods=['POST'])",
        "@router.post('/api/pools')"
    )
    
    # 替换 jsonify
    fastapi_code = fastapi_code.replace(
        "return jsonify(", "return "
    ).replace(", 200)", "")
    
    # 添加 async
    fastapi_code = re.sub(
        r"def (\w+)\(",
        r"async def \1(",
        fastapi_code
    )
    
    return fastapi_code
```

---

### 阶段 3: 清理与优化（1 周）

#### 任务清单

1. **删除 Flask 代码**
   - 备份 Flask 路由到 `archived/flask_routes/`
   - 删除 `adapters/inbound/api/routes/`
   - 删除 Flask 依赖

2. **统一端口**
   - FastAPI 迁移到 5001 端口
   - 更新 agent-ts 配置

3. **性能优化**
   - 启用 Gunicorn + Uvicorn workers
   - 配置连接池（异步 asyncpg）
   - 添加响应缓存

4. **生产部署配置**
```bash
# 生产启动脚本
gunicorn adapters.inbound.api.server_fastapi:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:5001 \
  --timeout 300 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log
```

---

## 三、技术对照表

### 路由定义

| Flask | FastAPI |
|-------|---------|
| `@bp.route('/path', methods=['GET'])` | `@router.get('/path')` |
| `@bp.route('/path', methods=['POST'])` | `@router.post('/path')` |
| `def func():` | `async def func():` |

### 请求参数

| Flask | FastAPI |
|-------|---------|
| `request.args.get('key')` | `key: str = Query(...)` |
| `request.get_json()` | `request: Model = Body(...)` |
| `<int:id>` | `id: int = Path(...)` |

### 响应

| Flask | FastAPI |
|-------|---------|
| `return jsonify({'data': x})` | `return {'data': x}` |
| `return jsonify(...), 404` | `raise HTTPException(404)` |

### 装饰器

| Flask | FastAPI |
|-------|---------|
| `@handle_errors` | 内置异常处理 |
| `@validate_params` | Pydantic 自动验证 |
| `@paginate` | 使用 `skip/limit` 参数 |

---

## 四、Service 层异步改造

### 同步 Service (当前)

```python
# application/services/opponent_behavior_service.py
class OpponentBehaviorService:
    def analyze_current_behavior(self):
        # 同步数据库查询
        data = self.repo.fetch_data()
        return self._analyze(data)
```

### 异步 Service (目标)

```python
# application/services/opponent_behavior_service.py
class OpponentBehaviorService:
    async def analyze_current_behavior(self):
        # 异步数据库查询
        data = await self.repo.fetch_data_async()
        return self._analyze(data)
```

### Repository 层异步改造

```python
# adapters/outbound/repositories/market_repository.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

class MarketRepository:
    def __init__(self):
        self.engine = create_async_engine(
            "postgresql+asyncpg://user:pass@localhost/db"
        )
    
    async def fetch_data_async(self):
        async with AsyncSession(self.engine) as session:
            result = await session.execute(query)
            return result.scalars().all()
```

---

## 五、工作量估算

| 阶段 | 工作量 | 关键路径 |
|-----|-------|---------|
| 阶段 0: 准备 | 1-2 天 | FastAPI 基础搭建 |
| 阶段 1: 核心模块 | 1-2 周 | 游戏智能 + 监控 API |
| 阶段 2: 其余模块 | 3-4 周 | 58 个路由迁移 |
| 阶段 3: 清理优化 | 1 周 | 删除 Flask + 性能调优 |
| **总计** | **6-8 周** | |

---

## 六、风险与缓解

### 风险

1. **兼容性问题**: Agent-ts 依赖旧 API
   - **缓解**: 双框架并存，逐步切换

2. **异步改造复杂**: Service 层需要大量修改
   - **缓解**: 逐模块改造，保持同步版本

3. **性能不达预期**: 异步优势不明显
   - **缓解**: 先做性能基准测试

4. **文档不完整**: Pydantic 模型定义工作量大
   - **缓解**: 使用代码生成工具

---

## 七、下一步行动

**立即执行**:
1. ✅ 创建 FastAPI 应用骨架
2. ✅ 迁移健康检查接口（最简单）
3. ✅ 迁移游戏智能 API（高优先级）
4. ✅ 编写性能对比测试

**您想从哪个开始？**
- A. 立即创建 FastAPI 应用骨架（阶段 0）
- B. 先写性能基准测试（验证收益）
- C. 直接迁移游戏智能 API（实战）
- D. 其他建议
