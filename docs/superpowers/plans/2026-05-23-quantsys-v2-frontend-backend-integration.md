# QuantSys V2 前后端对接实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过5个并行 Agent 实现31个 REST API 接口，完成 Vue 前端与 Flask 后端的完整对接

**Architecture:** 直接在 `quantsys-v2/api/server.py` 添加新路由，复用现有 service 层（order_service, trade_service, strategy_code_service 等），后端内部使用 snake_case，API 响应转换为 camelCase 给前端

**Tech Stack:** Flask, Python 3.x, DataService, PostgreSQL, Vue 3, TypeScript, Axios

---

## 文件结构

### 修改的文件
- **Modify**: `quantsys-v2/api/server.py` - 添加31个新接口和工具函数
- **Modify**: `quantsys-v2/repositories/signal_repository.py` - 可能需要添加状态更新方法

### 测试文件
- **Create**: `quantsys-v2/tests/test_api_integration.py` - API 集成测试

---

## 前置任务：准备工具函数

### Task 0: 添加字段转换和响应工具函数

**Files:**
- Modify: `quantsys-v2/api/server.py:1-50`

- [ ] **Step 1: 在 server.py 顶部添加导入**

在现有导入后添加：

```python
import re
from typing import Any, Dict, List, Union
from functools import wraps
import logging
```

- [ ] **Step 2: 添加字段命名转换函数**

在 `sanitize_for_json()` 函数后添加：

```python
def to_camel_case(snake_str: str) -> str:
    """下划线转驼峰"""
    if not isinstance(snake_str, str):
        return snake_str
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_snake_case(camel_str: str) -> str:
    """驼峰转下划线"""
    if not isinstance(camel_str, str):
        return camel_str
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

- [ ] **Step 3: 添加统一响应函数**

```python
def api_response(data: Any, success: bool = True, message: str = None) -> Dict:
    """
    统一API响应格式，自动转换为驼峰命名
    """
    response = {
        'success': success,
        'data': convert_keys_to_camel(sanitize_for_json(data))
    }
    if message:
        response['message'] = message
    return jsonify(response)
```

- [ ] **Step 4: 添加错误处理装饰器**

```python
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

- [ ] **Step 5: 测试工具函数**

创建临时测试脚本验证：

```python
# 测试驼峰转换
test_data = {
    'order_id': 123,
    'created_at': '2026-05-23',
    'order_type': 'limit'
}
result = convert_keys_to_camel(test_data)
print(result)  # 应该输出: {'orderId': 123, 'createdAt': '2026-05-23', 'orderType': 'limit'}
```

- [ ] **Step 6: Commit 工具函数**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
git add api/server.py
git commit -m "feat: add field conversion and response utility functions for API"
```

---

## Agent 1: 交易模块（8个接口）

### Task 1.1: 订单列表接口

**Files:**
- Modify: `quantsys-v2/api/server.py` (添加在订单管理区域)

- [ ] **Step 1: 添加订单列表路由**

在 server.py 的 "订单管理" 注释区域添加：

```python
# ==================== 订单管理 ====================

@app.route('/api/orders/list', methods=['GET'])
@handle_api_error
def get_orders_list():
    """获取订单列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('status')
    symbol = request.args.get('symbol')
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 构建查询条件
    filters = {}
    if status:
        filters['status'] = status
    if symbol:
        filters['symbol'] = symbol
    
    # 查询订单
    orders = ds.portfolio.get_orders(limit=page_size + offset)
    
    # 过滤
    if filters:
        orders = [o for o in orders if all(
            o.get(k) == v for k, v in filters.items()
        )]
    
    # 分页
    total = len(orders)
    orders_page = orders[offset:offset + page_size]
    
    return api_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': orders_page
    })
```

- [ ] **Step 2: 测试订单列表接口**

```bash
# 启动服务器（如果未启动）
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python api/server.py &

# 测试接口
curl "http://localhost:5000/api/orders/list?page=1&pageSize=20"
```

预期响应：
```json
{
  "success": true,
  "data": {
    "total": 0,
    "page": 1,
    "pageSize": 20,
    "items": []
  }
}
```

- [ ] **Step 3: Commit 订单列表接口**

```bash
git add api/server.py
git commit -m "feat(api): add GET /api/orders/list endpoint"
```

### Task 1.2: 订单详情接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加订单详情路由**

```python
@app.route('/api/orders/detail/<int:order_id>', methods=['GET'])
@handle_api_error
def get_order_detail(order_id):
    """获取订单详情"""
    order = ds.portfolio.get_order_by_id(order_id)
    
    if not order:
        return jsonify({'success': False, 'error': '订单不存在'}), 404
    
    return api_response(order)
```

- [ ] **Step 2: 测试订单详情接口**

```bash
curl http://localhost:5000/api/orders/detail/1
```

预期响应（如果订单不存在）：
```json
{
  "success": false,
  "error": "订单不存在"
}
```

- [ ] **Step 3: Commit 订单详情接口**

```bash
git add api/server.py
git commit -m "feat(api): add GET /api/orders/detail/:id endpoint"
```

### Task 1.3: 创建订单接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 导入 order_service**

在文件顶部添加：

```python
from services import order_service
```

- [ ] **Step 2: 添加创建订单路由**

```python
@app.route('/api/orders/create', methods=['POST'])
@handle_api_error
def create_order():
    """创建订单"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400
    
    # 转换驼峰为下划线
    order_data = convert_keys_to_snake(data)
    
    # 必填字段验证
    required_fields = ['symbol', 'action', 'order_type', 'quantity']
    for field in required_fields:
        if field not in order_data:
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400
    
    # 调用 order_service 创建订单
    order_id = order_service.create_order(
        ds=ds,
        symbol=order_data['symbol'],
        action=order_data['action'],
        order_type=order_data['order_type'],
        quantity=order_data['quantity'],
        price=order_data.get('price'),
        reason=order_data.get('reason'),
        signal_id=order_data.get('signal_id')
    )
    
    # 获取创建的订单
    order = ds.portfolio.get_order_by_id(order_id)
    
    return api_response(order, message='订单创建成功')
```

- [ ] **Step 3: 测试创建订单接口**

```bash
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
```

预期响应：
```json
{
  "success": true,
  "data": {
    "orderId": 1,
    "symbol": "000001.SZ",
    "action": "buy",
    "orderType": "limit",
    "quantity": 100,
    "price": 15.5,
    "status": "pending",
    "createdAt": "2026-05-23T10:30:00"
  },
  "message": "订单创建成功"
}
```

- [ ] **Step 4: Commit 创建订单接口**

```bash
git add api/server.py
git commit -m "feat(api): add POST /api/orders/create endpoint"
```

### Task 1.4: 取消订单接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加取消订单路由**

```python
@app.route('/api/orders/cancel/<int:order_id>', methods=['POST'])
@handle_api_error
def cancel_order(order_id):
    """取消订单"""
    # 检查订单是否存在
    order = ds.portfolio.get_order_by_id(order_id)
    if not order:
        return jsonify({'success': False, 'error': '订单不存在'}), 404
    
    # 调用 order_service 取消订单
    order_service.cancel_order(ds, order_id)
    
    # 获取更新后的订单
    updated_order = ds.portfolio.get_order_by_id(order_id)
    
    return api_response(updated_order, message='订单已取消')
```

- [ ] **Step 2: 测试取消订单接口**

```bash
curl -X POST http://localhost:5000/api/orders/cancel/1
```

预期响应：
```json
{
  "success": true,
  "data": {
    "orderId": 1,
    "status": "cancelled",
    "cancelledAt": "2026-05-23T10:35:00"
  },
  "message": "订单已取消"
}
```

- [ ] **Step 3: Commit 取消订单接口**

```bash
git add api/server.py
git commit -m "feat(api): add POST /api/orders/cancel/:id endpoint"
```

### Task 1.5: 修改订单接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加修改订单路由**

```python
@app.route('/api/orders/update/<int:order_id>', methods=['POST'])
@handle_api_error
def update_order(order_id):
    """修改订单"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400
    
    # 检查订单是否存在
    order = ds.portfolio.get_order_by_id(order_id)
    if not order:
        return jsonify({'success': False, 'error': '订单不存在'}), 404
    
    # 转换驼峰为下划线
    update_data = convert_keys_to_snake(data)
    
    # 更新订单（假设 portfolio repository 有 update_order 方法）
    # 如果没有，需要直接更新数据库
    allowed_fields = ['price', 'quantity', 'order_type']
    update_fields = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if not update_fields:
        return jsonify({'success': False, 'error': '没有可更新的字段'}), 400
    
    # 更新订单
    ds.portfolio.update_order(order_id, update_fields)
    
    # 获取更新后的订单
    updated_order = ds.portfolio.get_order_by_id(order_id)
    
    return api_response(updated_order, message='订单已更新')
```

- [ ] **Step 2: 测试修改订单接口**

```bash
curl -X POST http://localhost:5000/api/orders/update/1 \
  -H "Content-Type: application/json" \
  -d '{"price": 16.0, "quantity": 200}'
```

预期响应：
```json
{
  "success": true,
  "data": {
    "orderId": 1,
    "price": 16.0,
    "quantity": 200,
    "updatedAt": "2026-05-23T10:40:00"
  },
  "message": "订单已更新"
}
```

- [ ] **Step 3: Commit 修改订单接口**

```bash
git add api/server.py
git commit -m "feat(api): add POST /api/orders/update/:id endpoint"
```

### Task 1.6: 交易历史接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加交易历史路由**

```python
# ==================== 交易记录 ====================

@app.route('/api/trades/list', methods=['GET'])
@handle_api_error
def get_trades_list():
    """获取交易历史"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    symbol = request.args.get('symbol')
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    
    # 计算偏移量
    offset = (page - 1) * page_size
    
    # 查询交易记录
    trades = ds.portfolio.get_trades(limit=page_size + offset)
    
    # 过滤
    if symbol:
        trades = [t for t in trades if t.get('symbol') == symbol]
    if start_date:
        trades = [t for t in trades if t.get('trade_date', '') >= start_date]
    if end_date:
        trades = [t for t in trades if t.get('trade_date', '') <= end_date]
    
    # 分页
    total = len(trades)
    trades_page = trades[offset:offset + page_size]
    
    return api_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': trades_page
    })
```

- [ ] **Step 2: 测试交易历史接口**

```bash
curl "http://localhost:5000/api/trades/list?page=1&pageSize=20"
```

预期响应：
```json
{
  "success": true,
  "data": {
    "total": 0,
    "page": 1,
    "pageSize": 20,
    "items": []
  }
}
```

- [ ] **Step 3: Commit 交易历史接口**

```bash
git add api/server.py
git commit -m "feat(api): add GET /api/trades/list endpoint"
```

### Task 1.7: 持仓列表接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加持仓列表路由**

```python
# ==================== 持仓管理 ====================

@app.route('/api/portfolio/positions', methods=['GET'])
@handle_api_error
def get_portfolio_positions():
    """获取持仓列表"""
    holdings = ds.portfolio.get_all_holdings()
    
    # 转换为前端需要的格式
    positions = []
    for holding in holdings:
        # 获取最新价格
        kline = ds.kline.get_latest_daily_kline(holding['symbol'])
        current_price = kline['close'] if kline else holding.get('cost_price', 0)
        
        # 计算盈亏
        cost = holding['quantity'] * holding.get('cost_price', 0)
        market_value = holding['quantity'] * current_price
        profit = market_value - cost
        profit_percent = (profit / cost * 100) if cost > 0 else 0
        
        positions.append({
            'symbol': holding['symbol'],
            'name': holding.get('name', ''),
            'quantity': holding['quantity'],
            'available_quantity': holding.get('available_quantity', holding['quantity']),
            'cost_price': holding.get('cost_price', 0),
            'current_price': current_price,
            'market_value': market_value,
            'profit': profit,
            'profit_percent': profit_percent,
            'updated_at': holding.get('updated_at')
        })
    
    return api_response({'items': positions})
```

- [ ] **Step 2: 测试持仓列表接口**

```bash
curl http://localhost:5000/api/portfolio/positions
```

预期响应：
```json
{
  "success": true,
  "data": {
    "items": []
  }
}
```

- [ ] **Step 3: Commit 持仓列表接口**

```bash
git add api/server.py
git commit -m "feat(api): add GET /api/portfolio/positions endpoint"
```

### Task 1.8: 持仓汇总接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加持仓汇总路由**

```python
@app.route('/api/portfolio/summary', methods=['GET'])
@handle_api_error
def get_portfolio_summary():
    """获取持仓汇总"""
    # 获取账户余额
    balance = ds.risk.get_latest_balance()
    
    # 获取所有持仓
    holdings = ds.portfolio.get_all_holdings()
    
    # 计算总市值和盈亏
    total_market_value = 0
    total_cost = 0
    
    for holding in holdings:
        kline = ds.kline.get_latest_daily_kline(holding['symbol'])
        current_price = kline['close'] if kline else holding.get('cost_price', 0)
        
        market_value = holding['quantity'] * current_price
        cost = holding['quantity'] * holding.get('cost_price', 0)
        
        total_market_value += market_value
        total_cost += cost
    
    # 计算总资产
    cash = balance.get('cash', 0) if balance else 0
    total_assets = cash + total_market_value
    
    # 计算总盈亏
    total_profit = total_market_value - total_cost
    total_profit_percent = (total_profit / total_cost * 100) if total_cost > 0 else 0
    
    summary = {
        'total_assets': total_assets,
        'cash': cash,
        'market_value': total_market_value,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'total_profit_percent': total_profit_percent,
        'position_count': len(holdings),
        'updated_at': datetime.now().isoformat()
    }
    
    return api_response(summary)
```

- [ ] **Step 2: 测试持仓汇总接口**

```bash
curl http://localhost:5000/api/portfolio/summary
```

预期响应：
```json
{
  "success": true,
  "data": {
    "totalAssets": 100000.0,
    "cash": 100000.0,
    "marketValue": 0,
    "totalCost": 0,
    "totalProfit": 0,
    "totalProfitPercent": 0,
    "positionCount": 0,
    "updatedAt": "2026-05-23T10:50:00"
  }
}
```

- [ ] **Step 3: Commit 持仓汇总接口**

```bash
git add api/server.py
git commit -m "feat(api): add GET /api/portfolio/summary endpoint"
```

- [ ] **Step 4: Agent 1 完成标记**

交易模块8个接口全部完成，创建完成标记：

```bash
echo "Agent 1 - 交易模块完成" > /tmp/agent1_done.txt
```

---

## Agent 2: 策略模块（8个接口）

### Task 2.1: 导入 StrategyCodeService

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加 StrategyCodeService 导入**

在文件顶部添加：

```python
from services.strategy_code_service import StrategyCodeService
```

- [ ] **Step 2: 初始化 StrategyCodeService 实例**

在 `ds = DataService()` 后添加：

```python
strategy_service = StrategyCodeService()
```

- [ ] **Step 3: Commit 导入**

```bash
git add api/server.py
git commit -m "feat(api): import StrategyCodeService for strategy management"
```

### Task 2.2: 策略列表接口

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 添加策略列表路由**

```python
# ==================== 策略管理 ====================

@app.route('/api/strategies/list', methods=['GET'])
@handle_api_error
def get_strategies_list():
    """获取策略列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('status')
    
    # 查询策略（code_type='strategy'）
    strategies = strategy_service.list_strategies(code_type='strategy')
    
    # 过滤状态
    if status:
        strategies = [s for s in strategies if s.get('status') == status]
    
    # 分页
    total = len(strategies)
    offset = (page - 1) * page_size
    strategies_page = strategies[offset:offset + page_size]
    
    return api_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': strategies_page
    })
```

- [ ] **Step 2: 测试策略列表接口**

```bash
curl "http://localhost:5000/api/strategies/list?page=1&pageSize=20"
```

预期响应：
```json
{
  "success": true,
  "data": {
    "total": 0,
    "page": 1,
    "pageSize": 20,
    "items": []
  }
}
```

- [ ] **Step 3: Commit 策略列表接口**

```bash
git add api/server.py
git commit -m "feat(api): add GET /api/strategies/list endpoint"
```

