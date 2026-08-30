# Phase 3 - 业务逻辑问题调查报告

**日期**: 2026-08-29  
**调查范围**: 3 个业务逻辑问题工具  
**状态**: 🔍 调查完成，待修复

---

## 一、问题概览

| 工具名称 | 错误现象 | 根本原因 | 修复优先级 |
|---------|---------|---------|-----------|
| opportunity_scan | success: false, error: "'NoneType' object has no attribute 'batch_get_quarterly_margins'" | 后端数据源问题 | P1 - 高 |
| trade_monitor | 404 Not Found | API 端点未实现 | P0 - 最高 |
| risk_barra_decomposition | 404 Not Found | API 参数不匹配 | P1 - 高 |

---

## 二、详细调查结果

### 2.1 opportunity_scan - 数据源空指针异常

#### 工具信息

- **位置**: `agent-dh/packages/strategy/src/tools/OpportunityScanTool/`
- **API 调用**: `qv2.scanOpportunities()` → `POST /api/signals/scan`
- **后端实现**: `quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py:125`

#### 错误现象

```bash
$ curl -X POST "http://localhost:5001/api/signals/scan" \
  -H "Content-Type: application/json" \
  -d '{"scan_type":"hybrid","min_score":60}'

{
  "success": false,
  "error": "'NoneType' object has no attribute 'batch_get_quarterly_margins'"
}
```

#### 根本原因

**后端数据源对象未初始化** - 代码调用链分析：

1. `signals_async.py:179` 调用 `scoring_service.score_stocks()`
2. `scoring_service` 内部调用财务数据获取方法
3. 某个数据源对象（可能是 `ds.financials` 或 `ds.stock`）为 `None`
4. 尝试调用 `None.batch_get_quarterly_margins()` 导致 AttributeError

**可能的原因**：
- 数据源服务未正确初始化
- 依赖注入失败
- 数据库连接问题
- 数据源配置错误

#### 工具代码结构

```typescript
// OpportunityScanTool.ts
export class OpportunityScanTool extends BaseTool<OpportunityScanParams, OpportunityScanResult> {
  protected async execute(args: OpportunityScanParams, _context: ToolContext): Promise<OpportunityScanResult> {
    return this.qv2.scanOpportunities({
      scan_type: args.scan_type || 'hybrid',
      pool_id: args.pool_id,
      symbols: args.symbols,
      min_score: args.min_score || 60,
    }) as any;
  }
}
```

**工具层没有问题** - 已正确继承 BaseTool，参数校验完整。

#### 修复方案

**方案 A: 修复数据源初始化（推荐）**

1. 定位数据源初始化代码
2. 确保 `scoring_service` 的依赖正确注入
3. 添加空值检查和降级处理

**修复位置**: 
- `quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py`
- `quantsys-v2/domain/services/scoring_service.py`

**修复步骤**:
```python
# 1. 在 scoring_service 中添加空值检查
def score_stocks(symbols, filters, weights, no_cache):
    if ds.financials is None:
        logger.error("Financials data source not initialized")
        # 降级：仅使用技术指标评分
        return _score_with_technical_only(symbols)
    
    # 正常流程
    ...
```

**方案 B: 临时绕过（不推荐）**

在 `signals_async.py` 中捕获异常并返回空结果：
```python
try:
    opportunities = scoring_service.score_stocks(...)
except AttributeError as e:
    logger.error(f"Scoring failed: {e}")
    opportunities = []
```

**预估工期**: 2-4 小时（需要调试数据源初始化）

---

### 2.2 trade_monitor - API 端点未实现

#### 工具信息

- **位置**: `agent-dh/packages/trading/src/tools/TradeMonitorTool/`
- **API 调用**: `qv2.getTradeHistory()` → `GET /api/trades/list`
- **后端实现**: ❌ **不存在**

#### 错误现象

```bash
$ curl "http://localhost:5001/api/trades/list?account_name=agent_virtual"

{
  "success": false,
  "error_code": "HTTP_404",
  "message": "Not Found"
}
```

#### 根本原因

**API 端点缺失** - FastAPI 后端没有实现 `/api/trades/list` 路由。

**调查结果**：
- `orders_async.py` 中只有 3 个路由：
  - `POST /api/orders/algo-execute`
  - `GET /api/portfolio/positions`
  - `GET /api/portfolio/summary`
- **没有** `/api/trades/list` 路由
- **没有** 交易历史查询接口

#### 工具代码结构

```typescript
// TradeMonitorTool.ts
export class TradeMonitorTool extends BaseTool<TradeMonitorParams, TradeMonitorResult> {
  protected async execute(args: TradeMonitorParams, _context: ToolContext): Promise<TradeMonitorResult> {
    const result = await this.qv2.getTradeHistory({
      account_name: args.account_name || 'agent_virtual',
      order_id: args.order_id,
    });
    return result as unknown as TradeMonitorResult;
  }

  protected wrap(result: TradeMonitorResult, _context: ToolContext): ToolResponse<TradeMonitorResult> {
    // 完善的数据校验
    if (!result.orders || !Array.isArray(result.orders)) {
      return { success: false, error: { ... } };
    }
    return { success: true, data: result };
  }
}
```

**工具层没有问题** - 已正确实现 BaseTool 接口，包含完善的数据校验。

#### 客户端调用

```typescript
// quantsys-v2-client/src/client.ts:669
async getTradeHistory(params?: {
  account_name?: string;
  order_id?: string;
  symbol?: string;
  direction?: string;
  page?: number;
  pageSize?: number;
}): Promise<TradeHistoryResponse> {
  const response = await this.client.get('/api/trades/list', { params });
  return this.unwrap<TradeHistoryResponse>(response.data, 'getTradeHistory');
}
```

**客户端代码正确** - 调用的是合理的 RESTful 接口。

#### 修复方案

**必须实现后端 API** - 这不是工具问题，而是后端功能缺失。

**实施计划**：

1. **创建路由文件** (新建或修改 `orders_async.py`)

```python
@router.get('/api/trades/list')
@handle_api_error
def get_trade_history(
    account_name: Optional[str] = Query('agent_virtual'),
    order_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100)
):
    """
    查询交易历史
    
    返回格式:
    {
        "success": true,
        "data": {
            "orders": [...],
            "pending_count": 0,
            "filled_count": 5,
            "total": 5,
            "page": 1,
            "page_size": 20
        }
    }
    """
    from domain.services.trade_service import trade_service
    
    # 查询交易记录
    orders = trade_service.get_trades(
        account_name=account_name,
        order_id=order_id,
        symbol=symbol,
        direction=direction,
        page=page,
        page_size=pageSize
    )
    
    # 统计状态
    pending = [o for o in orders if o['status'] in ['pending', 'partial']]
    filled = [o for o in orders if o['status'] == 'filled']
    
    return api_response({
        'orders': orders,
        'pending_count': len(pending),
        'filled_count': len(filled),
        'total': len(orders),
        'page': page,
        'page_size': pageSize
    })
```

2. **实现 trade_service.get_trades()** (如果不存在)

```python
# domain/services/trade_service.py

class TradeService:
    def get_trades(self, account_name, order_id=None, symbol=None, direction=None, page=1, page_size=20):
        """从数据库查询交易记录"""
        from infrastructure.persistence.orm.repositories.trade_repository import TradeRepository
        
        repo = TradeRepository()
        filters = {'account_name': account_name}
        if order_id:
            filters['order_id'] = order_id
        if symbol:
            filters['symbol'] = symbol
        if direction:
            filters['action'] = direction
        
        offset = (page - 1) * page_size
        trades = repo.find_all(filters, limit=page_size, offset=offset)
        
        return [self._format_trade(t) for t in trades]
    
    def _format_trade(self, trade):
        """格式化交易记录"""
        return {
            'order_id': trade.order_id,
            'symbol': trade.symbol,
            'action': trade.action,
            'status': trade.status,
            'price': trade.price,
            'shares': trade.shares,
            'filled_shares': trade.filled_shares,
            'created_at': trade.created_at.isoformat(),
            'updated_at': trade.updated_at.isoformat(),
        }
```

3. **注册路由** (如果需要)

在 `fastapi_app/main.py` 中确认 `orders_async` 路由已包含。

**预估工期**: 4-6 小时（包括测试）

---

### 2.3 risk_barra_decomposition - API 参数不匹配

#### 工具信息

- **位置**: `agent-dh/packages/risk/src/tools/BarraDecompositionTool/`
- **API 调用**: `qv2.getBarraDecomposition()` → `POST /api/factor-models/barra/calculate`
- **后端实现**: ✅ 存在 (`factor_models_async.py:205`)

#### 错误现象

```bash
$ curl -X POST "http://localhost:5001/api/factor-models/barra/calculate" \
  -H "Content-Type: application/json" \
  -d '{"account_name":"agent_virtual"}'

{
  "success": false,
  "error_code": "HTTP_404",
  "message": "Not Found"
}
```

**注意**: 404 可能是测试时后端未正确启动，但更可能是参数校验失败。

#### 根本原因

**API 参数契约不匹配** - 后端期望 `symbols`，工具传 `account_name`。

**后端 API 定义** (`factor_models_async.py:207-232`):

```python
@router.post('/api/factor-models/barra/calculate')
@handle_api_error
def barra_calculate(payload: Optional[Dict[str, Any]] = Body(None)):
    """Barra 风险模型分析

    请求参数:
    - symbols: list[str] - 股票代码列表 (必需)
    - start_date: str - 开始日期
    - end_date: str - 结束日期
    - weights: list[float] (可选) - 持仓权重，默认等权
    """
    data = _require_json_body(payload)

    symbols = data.get('symbols', [])
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    weights = data.get('weights')

    if not symbols:
        return api_response(None, success=False, message="symbols is required")
    ...
```

**工具调用** (`BarraDecompositionTool.ts:38-42`):

```typescript
protected async execute(args: BarraDecompositionParams, _context: ToolContext): Promise<BarraDecompositionResult> {
  const result: any = await this.qv2.getBarraDecomposition({
    account_name: args.account_name || 'agent_virtual',  // ❌ 传了 account_name
  });
  ...
}
```

**客户端调用** (`client.ts:826-832`):

```typescript
async getBarraDecomposition(params?: {
  account_name?: string;      // ❌ 定义了 account_name
  returns?: number[];
  positions?: any[];
}): Promise<BarraDecompositionResponse> {
  const response = await this.client.post('/api/factor-models/barra/calculate', params ?? {});
  return this.unwrap<BarraDecompositionResponse>(response.data, 'getBarraDecomposition');
}
```

**问题**：
- 后端需要 `symbols: list[str]`（必需参数）
- 工具传 `account_name: string`
- 参数完全不匹配

#### 业务逻辑分析

**Barra 风险分解的两种用途**：

1. **分析指定股票列表**（当前后端实现）
   - 输入：`symbols` + 可选的权重
   - 用途：分析任意股票组合的风险

2. **分析账户持仓**（工具期望）
   - 输入：`account_name`
   - 后端自动查询该账户的持仓
   - 用途：分析实际账户的风险

**工具的设计意图是正确的** - Agent 应该能够直接查询账户的 Barra 风险分解，而不需要手动传入持仓。

#### 修复方案

**方案 A: 扩展后端 API 支持 account_name（推荐）**

修改后端支持两种调用方式：

```python
@router.post('/api/factor-models/barra/calculate')
@handle_api_error
def barra_calculate(payload: Optional[Dict[str, Any]] = Body(None)):
    """Barra 风险模型分析

    请求参数（两种方式二选一）:
    
    方式1: 指定股票列表
    - symbols: list[str] - 股票代码列表 (必需)
    - weights: list[float] (可选) - 持仓权重
    - start_date: str - 开始日期
    - end_date: str - 结束日期
    
    方式2: 基于账户持仓
    - account_name: str - 账户名称 (必需)
    - start_date: str - 开始日期
    - end_date: str - 结束日期
    """
    data = _require_json_body(payload)

    account_name = data.get('account_name')
    symbols = data.get('symbols', [])
    
    # 如果提供了 account_name，从持仓中获取 symbols 和 weights
    if account_name:
        from domain.services.portfolio_service import portfolio_service
        positions = portfolio_service.get_positions(account_name)
        
        if not positions:
            return api_response(None, success=False, 
                message=f"Account {account_name} has no positions")
        
        symbols = [p['symbol'] for p in positions]
        total_value = sum(p['market_value'] for p in positions)
        weights = [p['market_value'] / total_value for p in positions]
    else:
        # 方式1：使用传入的 symbols
        if not symbols:
            return api_response(None, success=False, 
                message="Either account_name or symbols is required")
        weights = data.get('weights')
        if weights is None:
            weights = [1.0 / len(symbols)] * len(symbols)
    
    # 后续计算逻辑不变
    ...
```

**修改位置**:
- `quantsys-v2/adapters/inbound/fastapi_app/routes/factor_models_async.py:207-254`

**方案 B: 修改工具传参（不推荐）**

让工具先查询账户持仓，再调用 Barra API：

```typescript
protected async execute(args: BarraDecompositionParams, _context: ToolContext): Promise<BarraDecompositionResult> {
  // 1. 查询账户持仓
  const positions = await this.qv2.getPositions({ 
    account_name: args.account_name || 'agent_virtual' 
  });
  
  if (!positions || positions.length === 0) {
    throw new Error('No positions found for account');
  }
  
  // 2. 提取 symbols 和 weights
  const symbols = positions.map(p => p.symbol);
  const totalValue = positions.reduce((sum, p) => sum + p.market_value, 0);
  const weights = positions.map(p => p.market_value / totalValue);
  
  // 3. 调用 Barra API
  const result: any = await this.qv2.getBarraDecomposition({
    symbols,
    weights,
  });
  ...
}
```

**缺点**：
- 增加了一次额外的 API 调用
- 逻辑复杂化
- 不符合业务语义（应该是后端职责）

**推荐方案 A** - 后端应该支持基于账户的风险分解。

**预估工期**: 2-3 小时

---

## 三、修复优先级与工作量

| 工具 | 问题类型 | 修复难度 | 预估工期 | 优先级 |
|------|---------|---------|---------|--------|
| trade_monitor | API 未实现 | 中 | 4-6h | P0 - 最高 |
| opportunity_scan | 数据源异常 | 中-高 | 2-4h | P1 - 高 |
| risk_barra_decomposition | 参数不匹配 | 低-中 | 2-3h | P1 - 高 |
| **总计** | | | **8-13h** | |

---

## 四、修复计划

### Phase 3.1: trade_monitor API 实现（P0）

**工作内容**:
1. 在 `orders_async.py` 中实现 `GET /api/trades/list` 路由
2. 实现 `trade_service.get_trades()` 方法（如果不存在）
3. 编写单元测试
4. 集成测试

**验收标准**:
```bash
$ curl "http://localhost:5001/api/trades/list?account_name=agent_virtual"
{
  "success": true,
  "data": {
    "orders": [...],
    "pending_count": 0,
    "filled_count": 5,
    "total": 5
  }
}
```

**预估工期**: 4-6 小时

---

### Phase 3.2: opportunity_scan 数据源修复（P1）

**工作内容**:
1. 调试 `scoring_service` 定位空指针位置
2. 检查数据源初始化代码
3. 添加空值检查和降级处理
4. 测试评分流程

**验收标准**:
```bash
$ curl -X POST "http://localhost:5001/api/signals/scan" \
  -H "Content-Type: application/json" \
  -d '{"scan_type":"hybrid","min_score":60}'
{
  "success": true,
  "scan_mode": "score",
  "opportunities": [...]
}
```

**预估工期**: 2-4 小时

---

### Phase 3.3: risk_barra_decomposition 参数扩展（P1）

**工作内容**:
1. 修改 `factor_models_async.py:barra_calculate()` 支持 `account_name`
2. 添加账户持仓查询逻辑
3. 更新 API 文档
4. 测试两种调用方式

**验收标准**:
```bash
# 方式1: 基于账户
$ curl -X POST "http://localhost:5001/api/factor-models/barra/calculate" \
  -H "Content-Type: application/json" \
  -d '{"account_name":"agent_virtual"}'
{
  "success": true,
  "data": {
    "total_risk": 0.15,
    "factor_risks": [...],
    "idiosyncratic_risk": 0.03
  }
}

# 方式2: 指定股票（原有功能）
$ curl -X POST "http://localhost:5001/api/factor-models/barra/calculate" \
  -H "Content-Type: application/json" \
  -d '{"symbols":["600519","000858"]}'
{
  "success": true,
  "data": { ... }
}
```

**预估工期**: 2-3 小时

---

## 五、总结

### 关键发现

1. **trade_monitor** - API 完全缺失，需要完整实现
2. **opportunity_scan** - 后端数据源初始化问题，需要调试和修复
3. **risk_barra_decomposition** - API 存在但参数契约不匹配，需要扩展

### 工具层质量

✅ **所有 3 个工具的前端实现都是正确的**：
- 正确继承 `BaseTool`
- 完善的参数校验
- 完整的数据包装逻辑
- 符合架构规范

❌ **问题全部在后端**：
- API 未实现
- 数据源异常
- 参数契约不匹配

### 修复策略

**按优先级顺序修复**：
1. **Phase 3.1**: trade_monitor（P0，4-6h）- 核心交易监控功能
2. **Phase 3.2**: opportunity_scan（P1，2-4h）- 策略核心功能
3. **Phase 3.3**: risk_barra_decomposition（P1，2-3h）- 风险管理功能

**总工期**: 8-13 小时（1-2 个工作日）

---

**报告完成时间**: 2026-08-29 20:00  
**报告作者**: Agent-Self
