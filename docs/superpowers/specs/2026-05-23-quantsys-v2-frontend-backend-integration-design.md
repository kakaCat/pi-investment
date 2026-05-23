# QuantSys V2 前后端对接设计文档

**日期**: 2026-05-23  
**版本**: 1.0  
**状态**: 设计完成，待实施

## 1. 项目概述

### 1.1 目标

通过多 Agent 并行工作，实现 Vue 前端（`web-frontend/`）与 Flask 后端（`quantsys-v2/`）的完整对接，补充缺失的 REST API 接口。

### 1.2 现状分析

**已有接口（约15个）：**
- ✅ 股票查询、K线、因子、技术指标
- ✅ 信号查询和扫描
- ✅ 回测执行
- ✅ 基础风控检查
- ✅ 数据更新

**缺失接口（约31个）：**
- ❌ 订单管理（8个接口）
- ❌ 策略管理（8个接口）
- ❌ 指标管理（6个接口）
- ❌ 信号增强（5个接口）
- ❌ Pipeline管理（4个接口）

**匹配度**: 约 27%

### 1.3 实施策略

- **快速对接优先**：直接在 `quantsys-v2/api/server.py` 添加新路由
- **复用现有服务**：调用 `order_service.py`, `trade_service.py`, `strategy_code_service.py` 等
- **多 Agent 并行**：5个 Agent 按业务模块分工
- **统一规范**：遵循 RESTful 主流规范

## 2. 总体架构

### 2.1 多 Agent 协作模式

```
┌─────────────────────────────────────────────────────────┐
│                    主协调 Agent                          │
│              (brainstorming + 任务分配)                  │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Agent 1     │    │  Agent 2     │    │  Agent 3     │
│  交易模块    │    │  策略模块    │    │  指标模块    │
│  8个接口     │    │  8个接口     │    │  6个接口     │
└──────────────┘    └──────────────┘    └──────────────┘
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐
│  Agent 4     │    │  Agent 5     │
│  信号增强    │    │  Pipeline    │
│  5个接口     │    │  4个接口     │
└──────────────┘    └──────────────┘
        │                   │
        └───────────┬───────┘
                    ▼
        quantsys-v2/api/server.py
        (统一添加新路由)
```

### 2.2 技术栈

**后端：**
- Flask (Python 3.x)
- DataService 统一数据访问层
- PostgreSQL 数据库

**前端：**
- Vue 3 + TypeScript
- Axios HTTP 客户端
- Vite 构建工具

**通信：**
- REST API (HTTP/JSON)
- 端口：5000

## 3. API 设计规范

### 3.1 命名规范

#### URL 路径
- 小写字母 + 斜杠分隔
- 动词明确操作：`/list`, `/create`, `/update`, `/delete`, `/start`, `/stop`
- 示例：`/api/orders/list`, `/api/strategies/create`

#### HTTP 方法
- **GET**：查询操作（列表、详情、统计）
- **POST**：所有写操作（创建、更新、删除、启动、停止）

#### 参数命名
- **后端 Python 内部**：snake_case（`order_id`, `created_at`, `page_size`）
- **API 请求/响应**：camelCase（`orderId`, `createdAt`, `pageSize`）
- **转换层**：后端统一在响应时转换为驼峰

### 3.2 响应格式

#### 成功响应
```json
{
  "success": true,
  "data": {
    "orderId": 123,
    "symbol": "000001.SZ",
    "orderType": "limit",
    "createdAt": "2026-05-23T10:30:00"
  },
  "message": "操作成功"
}
```

#### 列表响应
```json
{
  "success": true,
  "data": {
    "total": 150,
    "page": 1,
    "pageSize": 20,
    "items": [...]
  }
}
```

#### 错误响应
```json
{
  "success": false,
  "error": "订单不存在",
  "code": "ORDER_NOT_FOUND"
}
```

### 3.3 分页参数

**请求参数：**
- `page`: 页码（从1开始）
- `pageSize`: 每页数量（默认20）

**响应字段：**
- `total`: 总记录数
- `page`: 当前页码
- `pageSize`: 每页数量
- `items`: 数据列表

### 3.4 错误码

- `400` - 参数错误
- `404` - 资源不存在
- `409` - 业务冲突（如重复创建）
- `500` - 服务器内部错误

## 4. 工具函数设计

### 4.1 字段命名转换

```python
import re
from typing import Any, Dict, List, Union

def to_camel_case(snake_str: str) -> str:
    """下划线转驼峰"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def to_snake_case(camel_str: str) -> str:
    """驼峰转下划线"""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()

def convert_keys_to_camel(obj: Any) -> Any:
    """
    递归转换字典的key为驼峰命名
    用于API响应前的数据转换
    """
    if isinstance(obj, dict):
        return {to_camel_case(k): convert_keys_to_camel(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_keys_to_camel(item) for item in obj]
    elif hasattr(obj, 'isoformat'):  # datetime 对象
        return obj.isoformat()
    return obj

def convert_keys_to_snake(obj: Any) -> Any:
    """
    递归转换字典的key为下划线命名
    用于接收前端请求参数
    """
    if isinstance(obj, dict):
        return {to_snake_case(k): convert_keys_to_snake(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_keys_to_snake(item) for item in obj]
    return obj
```

### 4.2 统一响应函数

```python
def api_response(data: Any, success: bool = True, message: str = None) -> Dict:
    """
    统一API响应格式，自动转换为驼峰命名
    """
    response = {
        'success': success,
        'data': convert_keys_to_camel(data)
    }
    if message:
        response['message'] = message
    return jsonify(response)
```

### 4.3 错误处理装饰器

```python
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def handle_api_error(f):
    """统一API错误处理"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except KeyError as e:
            return jsonify({'success': False, 'error': f'缺少参数: {e}'}), 400
        except Exception as e:
            logger.error(f"API错误: {e}", exc_info=True)
            return jsonify({'success': False, 'error': '服务器内部错误'}), 500
    return decorated_function
```

## 5. 业务模块设计

### 5.1 模块 1：交易模块（Agent 1）

**职责**: 订单管理 + 交易记录 + 持仓查询

**接口列表（8个）：**

| 接口 | 方法 | 路径 | Service 方法 | 说明 |
|------|------|------|-------------|------|
| 订单列表 | GET | `/api/orders/list` | `ds.portfolio.get_orders()` | 支持分页、状态筛选 |
| 订单详情 | GET | `/api/orders/detail/:id` | `ds.portfolio.get_order_by_id()` | 返回单个订单 |
| 创建订单 | POST | `/api/orders/create` | `order_service.create_order()` | 接收前端订单表单 |
| 取消订单 | POST | `/api/orders/cancel/:id` | `order_service.cancel_order()` | 更新订单状态 |
| 修改订单 | POST | `/api/orders/update/:id` | `order_service.update_order()` | 修改价格/数量 |
| 交易历史 | GET | `/api/trades/list` | `ds.portfolio.get_trades()` | 支持分页、日期筛选 |
| 持仓列表 | GET | `/api/portfolio/positions` | `ds.portfolio.get_all_holdings()` | 当前持仓 |
| 持仓汇总 | GET | `/api/portfolio/summary` | `ds.risk.get_latest_balance()` | 总资产、盈亏 |

**输入输出示例：**

```python
# 创建订单
POST /api/orders/create
Request:
{
  "symbol": "000001.SZ",
  "action": "buy",
  "orderType": "limit",
  "quantity": 100,
  "price": 15.50,
  "reason": "技术突破"
}

Response:
{
  "success": true,
  "data": {
    "orderId": 123,
    "symbol": "000001.SZ",
    "action": "buy",
    "orderType": "limit",
    "status": "pending",
    "createdAt": "2026-05-23T10:30:00"
  },
  "message": "订单创建成功"
}
```

**字段映射：**
- 前端 `orderType` → 后端 `order_type`
- 前端 `orderId` → 后端 `order_id`
- 前端 `createdAt` → 后端 `created_at`

**依赖服务：**
- `services/order_service.py`
- `services/trade_service.py`
- `DataService.portfolio`
- `DataService.risk`

### 5.2 模块 2：策略模块（Agent 2）

**职责**: 策略生命周期管理 + 绩效查询

**接口列表（8个）：**

| 接口 | 方法 | 路径 | Service 方法 | 说明 |
|------|------|------|-------------|------|
| 策略列表 | GET | `/api/strategies/list` | `StrategyCodeService.list_strategies()` | 支持分页、状态筛选 |
| 策略详情 | GET | `/api/strategies/detail/:id` | `StrategyCodeService.get_strategy()` | 包含代码、配置 |
| 创建策略 | POST | `/api/strategies/create` | `StrategyCodeService.create_strategy()` | 保存策略代码 |
| 更新策略 | POST | `/api/strategies/update/:id` | `StrategyCodeService.update_strategy()` | 修改策略 |
| 删除策略 | POST | `/api/strategies/delete/:id` | `StrategyCodeService.delete_strategy()` | 软删除 |
| 启动策略 | POST | `/api/strategies/start/:id` | `StrategyCodeService.run_strategy()` | 启动回测/实盘 |
| 停止策略 | POST | `/api/strategies/stop/:id` | 更新状态为 stopped | 停止运行 |
| 策略绩效 | GET | `/api/strategies/performance/:id` | 复用或新增 | 策略绩效数据 |

**输入输出示例：**

```python
# 创建策略
POST /api/strategies/create
Request:
{
  "name": "双均线策略",
  "code": "def strategy_logic():\n    ...",
  "description": "5日和20日均线交叉",
  "params": {
    "shortPeriod": 5,
    "longPeriod": 20
  }
}

Response:
{
  "success": true,
  "data": {
    "strategyId": 456,
    "name": "双均线策略",
    "status": "inactive",
    "createdAt": "2026-05-23T10:30:00"
  },
  "message": "策略创建成功"
}
```

**依赖服务：**
- `services/strategy_code_service.py`

### 5.3 模块 3：指标模块（Agent 3）

**职责**: 自定义指标 IDE

**接口列表（6个）：**

| 接口 | 方法 | 路径 | Service 方法 | 说明 |
|------|------|------|-------------|------|
| 指标列表 | GET | `/api/indicators/list` | `StrategyCodeService.list_strategies(code_type='indicator')` | 复用策略服务 |
| 指标详情 | GET | `/api/indicators/detail/:id` | `StrategyCodeService.get_strategy()` | 单个指标 |
| 创建指标 | POST | `/api/indicators/create` | `StrategyCodeService.create_strategy(code_type='indicator')` | 保存指标代码 |
| 更新指标 | POST | `/api/indicators/update/:id` | `StrategyCodeService.update_strategy()` | 修改指标 |
| 删除指标 | POST | `/api/indicators/delete/:id` | `StrategyCodeService.delete_strategy()` | 软删除 |
| 运行指标 | POST | `/api/indicators/run/:id` | `StrategyCodeService.run_strategy()` | 计算指标值 |
| 回测指标 | POST | `/api/indicators/backtest` | `StrategyCodeService.backtest_strategy()` | 指标回测 |

**关键设计：**
- 指标本质上是 `code_type='indicator'` 的策略代码
- 完全复用 `StrategyCodeService` 的能力
- 区别在于运行时的输出格式（指标值 vs 交易信号）

**依赖服务：**
- `services/strategy_code_service.py`

### 5.4 模块 4：信号增强（Agent 4）

**职责**: 信号审批流程 + 统计分析

**接口列表（5个）：**

| 接口 | 方法 | 路径 | Service 方法 | 说明 |
|------|------|------|-------------|------|
| 信号详情 | GET | `/api/signals/detail/:id` | `ds.signal.get_signal_by_id()` | 单个信号 |
| 批准信号 | POST | `/api/signals/approve/:id` | 更新 `status='approved'` | 审批通过 |
| 拒绝信号 | POST | `/api/signals/reject/:id` | 更新 `status='rejected'` | 审批拒绝 |
| 标记错误 | POST | `/api/signals/mark-error/:id` | 更新 `status='error'` | 标记异常 |
| 信号统计 | GET | `/api/signals/statistics` | 聚合查询 | 按状态、日期统计 |

**数据库扩展需求：**
- 需要在 `signals` 表添加 `status` 字段（如果没有）
- 可选值：`pending`, `approved`, `rejected`, `error`, `executed`
- 添加 `reject_reason` 字段存储拒绝原因

**输入输出示例：**

```python
# 批准信号
POST /api/signals/approve/123
Response:
{
  "success": true,
  "data": {
    "signalId": 123,
    "status": "approved",
    "approvedAt": "2026-05-23T10:30:00"
  },
  "message": "信号已批准"
}

# 信号统计
GET /api/signals/statistics?startDate=2026-05-01&endDate=2026-05-23
Response:
{
  "success": true,
  "data": {
    "total": 150,
    "pending": 20,
    "approved": 80,
    "rejected": 30,
    "error": 10,
    "executed": 60
  }
}
```

**依赖服务：**
- `DataService.signal`
- `repositories/signal_repository.py`

### 5.5 模块 5：Pipeline 管理（Agent 5）

**职责**: 量化流水线编排 + 任务调度

**接口列表（4个）：**

| 接口 | 方法 | 路径 | 实现方式 | 说明 |
|------|------|------|---------|------|
| Pipeline统计 | GET | `/api/pipeline/statistics` | 读取运行记录 | 运行中、完成、失败任务数 |
| 任务列表 | GET | `/api/pipeline/tasks/list` | 内存或文件存储 | 当前任务状态 |
| 运行历史 | GET | `/api/pipeline/runs/list` | 读取 `.pi-invest/pipeline-runs` | 历史记录 |
| 触发Pipeline | POST | `/api/pipeline/trigger` | 组合调用现有服务 | 数据更新→因子→信号→风控 |

**Pipeline 执行流程：**

```python
def trigger_pipeline(symbols, stages):
    """
    触发量化流水线
    
    Args:
        symbols: 股票代码列表
        stages: 执行阶段列表 ['data_update', 'factors', 'signals', 'risk']
    
    Returns:
        运行ID和状态
    """
    run_id = str(uuid.uuid4())
    start_time = datetime.now()
    
    results = {
        'run_id': run_id,
        'start_time': start_time.isoformat(),
        'status': 'running',
        'stages': []
    }
    
    try:
        # 阶段1: 数据更新
        if 'data_update' in stages:
            ds.update_data(symbols)
            results['stages'].append({
                'name': 'data_update',
                'status': 'completed',
                'duration': 10.5
            })
        
        # 阶段2: 因子计算
        if 'factors' in stages:
            for symbol in symbols:
                ds.compute_factors(symbol)
            results['stages'].append({
                'name': 'factors',
                'status': 'completed',
                'duration': 25.3
            })
        
        # 阶段3: 信号扫描
        if 'signals' in stages:
            signals = ds.signal.scan(symbols)
            results['stages'].append({
                'name': 'signals',
                'status': 'completed',
                'signal_count': len(signals)
            })
        
        # 阶段4: 风控检查
        if 'risk' in stages:
            for symbol in symbols:
                ds.risk.check(symbol)
            results['stages'].append({
                'name': 'risk',
                'status': 'completed'
            })
        
        results['status'] = 'completed'
        results['end_time'] = datetime.now().isoformat()
        
    except Exception as e:
        results['status'] = 'failed'
        results['error'] = str(e)
    
    # 保存运行记录
    save_pipeline_run(results)
    
    return results
```

**输入输出示例：**

```python
# 触发Pipeline
POST /api/pipeline/trigger
Request:
{
  "symbols": ["000001.SZ", "600000.SH"],
  "stages": ["data_update", "factors", "signals", "risk"]
}

Response:
{
  "success": true,
  "data": {
    "runId": "abc-123-def",
    "status": "running",
    "startTime": "2026-05-23T10:30:00"
  },
  "message": "Pipeline已启动"
}
```

**依赖服务：**
- `DataService` 所有模块
- 文件系统（存储运行记录）

## 6. 实施计划

### 6.1 Agent 任务分配

```yaml
Agent 1 - 交易模块:
  负责人: trading-agent
  接口数量: 8个
  预计工时: 2-3小时
  依赖: order_service.py, trade_service.py
  输出文件: server.py (订单、交易、持仓部分)
  
Agent 2 - 策略模块:
  负责人: strategy-agent
  接口数量: 8个
  预计工时: 2-3小时
  依赖: strategy_code_service.py
  输出文件: server.py (策略管理部分)
  
Agent 3 - 指标模块:
  负责人: indicator-agent
  接口数量: 6个
  预计工时: 2小时
  依赖: strategy_code_service.py (复用)
  输出文件: server.py (指标管理部分)
  
Agent 4 - 信号增强:
  负责人: signal-agent
  接口数量: 5个
  预计工时: 1-2小时
  依赖: signal_repository.py
  输出文件: server.py (信号增强部分)
  
Agent 5 - Pipeline:
  负责人: pipeline-agent
  接口数量: 4个
  预计工时: 2小时
  依赖: 组合现有服务
  输出文件: server.py (Pipeline管理部分)
```

### 6.2 并行工作流程

```
阶段1 - 并行开发（预计4-6小时）:
├─ Agent 1: 实现交易模块 8个接口
├─ Agent 2: 实现策略模块 8个接口
├─ Agent 3: 实现指标模块 6个接口
├─ Agent 4: 实现信号增强 5个接口
└─ Agent 5: 实现Pipeline 4个接口

阶段2 - 代码集成（预计1小时）:
├─ 合并所有代码到 server.py
├─ 解决命名冲突
├─ 统一导入和初始化
├─ 添加统一的错误处理
└─ 代码格式化和注释

阶段3 - 测试验证（预计2小时）:
├─ 启动后端服务
├─ 逐个测试接口（curl命令）
├─ 验证字段映射（驼峰转换）
├─ 检查数据库操作
└─ 前端联调测试

总预计时间: 7-9小时
```

### 6.3 代码组织结构

```python
# quantsys-v2/api/server.py 最终结构

"""
QuantSys V2 API 服务
"""
import json
import math
import os
import re
import threading
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Dict, List, Union

from flask import Flask, jsonify, request
from flask_cors import CORS

from services.data_service import DataService
from services import order_service, trade_service
from services.strategy_code_service import StrategyCodeService

app = Flask(__name__)
CORS(app)

# ==================== 全局服务实例 ====================
ds = DataService()
strategy_service = StrategyCodeService()

# ==================== 工具函数 ====================
# sanitize_for_json()
# to_camel_case()
# to_snake_case()
# convert_keys_to_camel()
# convert_keys_to_snake()
# api_response()
# handle_api_error() 装饰器

# ==================== 健康检查 ====================
# GET /api/health
# GET /api/platform/status

# ==================== 股票相关（已有，保持不变）====================
# GET  /api/stocks/search
# GET  /api/stocks/list
# POST /api/stocks/resolve
# POST /api/stocks/add
# GET  /api/stocks/data-status
# GET  /api/stock/<symbol>/klines
# GET  /api/stock/<symbol>/factors
# POST /api/stocks/compare
# GET  /api/stock/<symbol>/technical

# ==================== 信号相关（已有，保持不变）====================
# GET  /api/signals
# GET  /api/signals/history
# POST /api/signals/scan

# ==================== 回测相关（已有，保持不变）====================
# GET  /api/backtest/results
# POST /api/backtest

# ==================== 风控相关（已有，保持不变）====================
# POST /api/risk/check

# ==================== 数据更新（已有，保持不变）====================
# POST /api/data/update
# GET  /api/data/update/jobs/<job_id>

# ==================== 订单管理（Agent 1 新增）====================
# GET  /api/orders/list
# GET  /api/orders/detail/<order_id>
# POST /api/orders/create
# POST /api/orders/cancel/<order_id>
# POST /api/orders/update/<order_id>

# ==================== 交易记录（Agent 1 新增）====================
# GET /api/trades/list

# ==================== 持仓管理（Agent 1 新增）====================
# GET /api/portfolio/positions
# GET /api/portfolio/summary

# ==================== 策略管理（Agent 2 新增）====================
# GET  /api/strategies/list
# GET  /api/strategies/detail/<strategy_id>
# POST /api/strategies/create
# POST /api/strategies/update/<strategy_id>
# POST /api/strategies/delete/<strategy_id>
# POST /api/strategies/start/<strategy_id>
# POST /api/strategies/stop/<strategy_id>
# GET  /api/strategies/performance/<strategy_id>

# ==================== 指标管理（Agent 3 新增）====================
# GET  /api/indicators/list
# GET  /api/indicators/detail/<indicator_id>
# POST /api/indicators/create
# POST /api/indicators/update/<indicator_id>
# POST /api/indicators/delete/<indicator_id>
# POST /api/indicators/run/<indicator_id>
# POST /api/indicators/backtest

# ==================== 信号增强（Agent 4 新增）====================
# GET  /api/signals/detail/<signal_id>
# POST /api/signals/approve/<signal_id>
# POST /api/signals/reject/<signal_id>
# POST /api/signals/mark-error/<signal_id>
# GET  /api/signals/statistics

# ==================== Pipeline管理（Agent 5 新增）====================
# GET  /api/pipeline/statistics
# GET  /api/pipeline/tasks/list
# GET  /api/pipeline/runs/list
# POST /api/pipeline/trigger

# ==================== 启动服务 ====================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

## 7. 验收标准

### 7.1 每个 Agent 的交付物

1. **代码片段**：完整的路由函数代码（带注释）
2. **测试命令**：curl 命令验证接口可用性
3. **示例数据**：请求和响应的 JSON 示例
4. **字段映射表**：前端字段 ↔ 后端字段对照表

### 7.2 接口测试清单

```bash
# ==================== 后端启动 ====================
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python api/server.py

# ==================== 健康检查 ====================
curl http://localhost:5000/api/health

# ==================== 交易模块测试 ====================
# 订单列表
curl "http://localhost:5000/api/orders/list?page=1&pageSize=20"

# 创建订单
curl -X POST http://localhost:5000/api/orders/create \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "000001.SZ",
    "action": "buy",
    "orderType": "limit",
    "quantity": 100,
    "price": 15.5,
    "reason": "测试订单"
  }'

# 订单详情
curl http://localhost:5000/api/orders/detail/1

# 取消订单
curl -X POST http://localhost:5000/api/orders/cancel/1

# 交易历史
curl "http://localhost:5000/api/trades/list?page=1&pageSize=20"

# 持仓列表
curl http://localhost:5000/api/portfolio/positions

# 持仓汇总
curl http://localhost:5000/api/portfolio/summary

# ==================== 策略模块测试 ====================
# 策略列表
curl "http://localhost:5000/api/strategies/list?page=1&pageSize=20"

# 创建策略
curl -X POST http://localhost:5000/api/strategies/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试策略",
    "code": "def run():\n    pass",
    "description": "测试用策略"
  }'

# 策略详情
curl http://localhost:5000/api/strategies/detail/1

# 启动策略
curl -X POST http://localhost:5000/api/strategies/start/1

# 停止策略
curl -X POST http://localhost:5000/api/strategies/stop/1

# 策略绩效
curl http://localhost:5000/api/strategies/performance/1

# ==================== 指标模块测试 ====================
# 指标列表
curl "http://localhost:5000/api/indicators/list?page=1&pageSize=20"

# 创建指标
curl -X POST http://localhost:5000/api/indicators/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试指标",
    "code": "def calculate():\n    return 0"
  }'

# 运行指标
curl -X POST http://localhost:5000/api/indicators/run/1 \
  -H "Content-Type: application/json" \
  -d '{"symbol": "000001.SZ"}'

# ==================== 信号增强测试 ====================
# 信号详情
curl http://localhost:5000/api/signals/detail/1

# 批准信号
curl -X POST http://localhost:5000/api/signals/approve/1

# 拒绝信号
curl -X POST http://localhost:5000/api/signals/reject/1 \
  -H "Content-Type: application/json" \
  -d '{"reason": "不符合条件"}'

# 信号统计
curl "http://localhost:5000/api/signals/statistics?startDate=2026-05-01&endDate=2026-05-23"

# ==================== Pipeline测试 ====================
# Pipeline统计
curl http://localhost:5000/api/pipeline/statistics

# 任务列表
curl http://localhost:5000/api/pipeline/tasks/list

# 运行历史
curl http://localhost:5000/api/pipeline/runs/list

# 触发Pipeline
curl -X POST http://localhost:5000/api/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["000001.SZ", "600000.SH"],
    "stages": ["data_update", "factors", "signals"]
  }'
```

### 7.3 前端联调测试

```bash
# 启动前端
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run dev

# 访问 http://localhost:5173
# 测试以下页面：
# 1. 订单管理页面 - 能否加载订单列表
# 2. 持仓页面 - 能否显示持仓数据
# 3. 策略中心 - 能否创建和管理策略
# 4. 指标IDE - 能否创建和运行指标
# 5. 信号管理 - 能否审批信号
# 6. Pipeline页面 - 能否触发流水线
```

### 7.4 成功标准

**后端验收：**
- ✅ 所有31个新接口返回200状态码（或符合预期的错误码）
- ✅ 响应字段全部为驼峰命名（camelCase）
- ✅ 错误响应包含 `success: false` 和 `error` 字段
- ✅ 数据库操作正确（创建、查询、更新）
- ✅ 无 Python 运行时错误

**前端验收：**
- ✅ 所有页面能正常加载数据（无404错误）
- ✅ 控制台无 JavaScript 运行时错误
- ✅ 表单提交成功并显示反馈
- ✅ 列表分页正常工作
- ✅ 数据刷新正常

**集成验收：**
- ✅ 前端发送驼峰参数，后端正确接收
- ✅ 后端返回驼峰字段，前端正确解析
- ✅ 创建→查询→更新→删除 完整流程可用
- ✅ 错误场景有友好提示

## 8. 风险和注意事项

### 8.1 潜在风险

**技术风险：**
1. **端口冲突**：WebSocket 服务（`server_websocket.py`）也占用5000端口
2. **数据库表缺失**：某些功能可能需要新表或字段（如 signals.status）
3. **Service 方法不存在**：可能需要补充 service 层方法
4. **字段不匹配**：数据库字段和前端期望不一致
5. **并发冲突**：多个 Agent 同时修改 server.py 可能产生冲突

**业务风险：**
1. **数据一致性**：订单、持仓、交易数据需要保持一致
2. **权限控制**：当前设计未包含用户认证和权限
3. **性能问题**：大量数据查询可能影响响应速度

### 8.2 缓解措施

**技术措施：**
1. **端口冲突**：先只启动 REST 服务，WebSocket 后续单独处理或改用5001端口
2. **数据库检查**：每个 Agent 开始前先检查表结构，缺失字段标记为 TODO
3. **Service 补充**：优先使用现有方法，缺失的先返回模拟数据或空列表
4. **字段映射**：建立统一的字段映射文档，所有 Agent 遵循
5. **代码合并**：使用明确的分隔注释，按模块顺序合并

**业务措施：**
1. **数据验证**：在 service 层添加数据一致性检查
2. **权限预留**：响应结构预留 `userId` 字段，后续扩展
3. **性能优化**：添加分页、索引、缓存（后续优化）

### 8.3 已知限制

1. **无用户认证**：当前版本不包含登录、权限控制
2. **无实时推送**：WebSocket 暂不对接，使用轮询
3. **无事务处理**：跨表操作未使用数据库事务
4. **无日志审计**：操作日志记录不完整
5. **无性能监控**：缺少 API 性能指标

这些限制在第一阶段可接受，后续迭代优化。

## 9. 后续优化方向

### 9.1 第二阶段（重构优化）

1. **代码重构**：
   - 拆分 `server.py` 为 `routes/` 目录
   - 统一响应格式为 `{success, data, message}`
   - 提取公共逻辑到中间件

2. **性能优化**：
   - 添加 Redis 缓存
   - 数据库查询优化（索引、连接池）
   - 异步处理长时间任务

3. **功能增强**：
   - WebSocket 实时推送
   - 用户认证和权限控制
   - 操作日志和审计

### 9.2 第三阶段（生产就绪）

1. **监控告警**：
   - API 性能监控
   - 错误率告警
   - 资源使用监控

2. **测试覆盖**：
   - 单元测试
   - 集成测试
   - 端到端测试

3. **文档完善**：
   - API 文档（Swagger）
   - 部署文档
   - 运维手册

## 10. 总结

### 10.1 设计要点

1. **多 Agent 并行**：5个 Agent 按业务模块分工，提高效率
2. **快速对接优先**：直接在 server.py 添加路由，复用现有服务
3. **统一规范**：遵循 RESTful 主流规范，后端返回 camelCase
4. **灵活响应**：支持多种响应格式，保持向后兼容

### 10.2 关键决策

- ✅ 只用 GET/POST，路径语义化
- ✅ 后端内部 snake_case，API 响应 camelCase
- ✅ 不重构旧代码，新接口添加到 server.py
- ✅ 复用 StrategyCodeService 实现指标管理
- ✅ Pipeline 组合调用现有服务，不新建复杂架构

### 10.3 预期成果

- **31个新接口**：覆盖订单、策略、指标、信号、Pipeline
- **完整的交易闭环**：从信号→订单→交易→持仓
- **前端可用**：所有页面能正常加载和操作
- **可扩展架构**：为后续优化预留空间

---

**文档版本**: 1.0  
**最后更新**: 2026-05-23  
**下一步**: 调用 writing-plans skill 创建实施计划

