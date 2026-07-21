# 指标管理 API 实现总结

## 实现概述

在 `api/server.py` 中成功实现了7个指标管理 REST API 接口，位于 **"指标管理"** 区域（第1339-1531行）。

## 核心设计理念

**指标复用策略服务**：指标本质上是 `code_type='indicator'` 的策略代码，因此所有接口都复用 `StrategyCodeService`，避免重复实现。

```python
# 关键设计
indicators = strategy_service.list_strategies(code_type='indicator')
```

## 实现的7个接口

### 1. GET /api/indicators/list - 获取指标列表

**功能**：分页获取所有指标

**参数**：
- `page` (query, 可选): 页码，默认1
- `pageSize` (query, 可选): 每页数量，默认20

**响应示例**：
```json
{
  "success": true,
  "data": {
    "total": 10,
    "page": 1,
    "pageSize": 20,
    "items": [
      {
        "id": 1,
        "name": "双均线指标",
        "codeType": "indicator",
        "isActive": true,
        "validationStatus": "valid",
        "createdAt": "2024-01-01T00:00:00"
      }
    ]
  }
}
```

**实现要点**：
- 调用 `strategy_service.list_strategies(code_type='indicator')`
- 内存分页处理
- 自动转换为驼峰命名

---

### 2. GET /api/indicators/detail/<indicator_id> - 获取指标详情

**功能**：获取指定指标的完整信息

**参数**：
- `indicator_id` (path, 必需): 指标ID

**响应示例**：
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "双均线指标",
    "codeContent": "def calculate(df): ...",
    "codeType": "indicator",
    "description": "简单的双均线交叉指标",
    "parsedParams": [],
    "riskConfig": {},
    "validationStatus": "valid",
    "isActive": true,
    "createdAt": "2024-01-01T00:00:00",
    "lastExecutedAt": "2024-01-02T00:00:00"
  }
}
```

**实现要点**：
- 验证指标是否存在
- 验证 `code_type` 是否为 'indicator'
- 返回完整的指标信息

---

### 3. POST /api/indicators/create - 创建指标

**功能**：创建新的自定义指标

**请求体**：
```json
{
  "name": "测试指标",
  "code": "def calculate(df):\n    df['buy'] = ...\n    df['sell'] = ...\n    return df",
  "description": "指标描述",
  "params": {}
}
```

**响应示例**：
```json
{
  "success": true,
  "message": "指标创建成功",
  "data": {
    "strategyId": 1,
    "name": "测试指标",
    "codeType": "indicator",
    "validation": {
      "valid": true,
      "syntaxOk": true,
      "hasBuySignal": true,
      "hasSellSignal": true,
      "params": [],
      "riskConfig": {}
    }
  }
}
```

**实现要点**：
- 验证必需参数 `name` 和 `code`
- 调用 `strategy_service.create_strategy()` 并指定 `code_type='indicator'`
- 自动进行代码验证
- 返回验证结果

---

### 4. POST /api/indicators/update/<indicator_id> - 更新指标

**功能**：更新指标的代码、参数或状态

**请求体**：
```json
{
  "code": "def calculate(df): ...",
  "params": {},
  "isActive": true
}
```

**响应示例**：
```json
{
  "success": true,
  "message": "指标更新成功",
  "data": {
    "id": 1,
    "name": "测试指标",
    "codeContent": "...",
    "isActive": true
  }
}
```

**实现要点**：
- 验证指标存在且类型正确
- 支持部分更新（code、params、isActive）
- 更新代码时自动重新验证

---

### 5. POST /api/indicators/delete/<indicator_id> - 删除指标

**功能**：删除指定的指标

**响应示例**：
```json
{
  "success": true,
  "message": "指标删除成功",
  "data": {
    "indicatorId": 1
  }
}
```

**实现要点**：
- 验证指标存在且类型正确
- 调用 `strategy_service.delete_strategy()`
- 物理删除（非软删除）

---

### 6. POST /api/indicators/run/<indicator_id> - 运行指标

**功能**：对指定股票运行指标，生成实时信号

**请求体**：
```json
{
  "symbol": "000001.SZ",
  "limit": 100
}
```

**响应示例**：
```json
{
  "success": true,
  "message": "指标运行成功",
  "data": {
    "symbol": "000001.SZ",
    "latestSignal": "buy",
    "confidence": 0.8,
    "price": 15.68,
    "date": "2024-01-15",
    "indicators": {
      "ma5": 15.5,
      "ma20": 15.2
    }
  }
}
```

**实现要点**：
- 验证必需参数 `symbol`
- 验证指标存在、类型正确且验证通过
- 调用 `strategy_service.run_strategy()`
- 返回最新信号和指标值

---

### 7. POST /api/indicators/backtest - 回测指标

**功能**：对指标进行历史回测

**请求体**：
```json
{
  "indicatorId": 1,
  "symbol": "000001.SZ",
  "startDate": "2024-01-01",
  "endDate": "2024-12-31",
  "initialCash": 1000000
}
```

**响应示例**：
```json
{
  "success": true,
  "message": "指标回测完成",
  "data": {
    "totalReturn": 0.15,
    "sharpeRatio": 1.8,
    "maxDrawdown": -0.12,
    "winRate": 0.65,
    "totalTrades": 45,
    "trades": [...],
    "equityCurve": [...]
  }
}
```

**实现要点**：
- 验证必需参数：`indicatorId`, `symbol`, `startDate`, `endDate`
- 验证指标存在、类型正确且验证通过
- 调用 `strategy_service.backtest_strategy()`
- 返回完整的回测指标

---

## 如何复用 StrategyCodeService

所有指标接口都通过以下方式复用策略服务：

### 1. 列表查询
```python
indicators = strategy_service.list_strategies(code_type='indicator')
```

### 2. 创建指标
```python
result = strategy_service.create_strategy(
    name=name,
    code=code,
    code_type='indicator',  # 关键：指定类型为 indicator
    params=params,
    description=description
)
```

### 3. 其他操作
```python
# 获取详情
indicator = strategy_service.get_strategy(indicator_id)

# 更新
updated = strategy_service.update_strategy(strategy_id, code, params, is_active)

# 删除
success = strategy_service.delete_strategy(strategy_id)

# 运行
result = strategy_service.run_strategy(strategy_id, symbol, limit)

# 回测
result = strategy_service.backtest_strategy(
    strategy_id, symbol, start_date, end_date, initial_cash
)
```

### 4. 类型验证
所有接口都包含类型验证，确保只操作 `code_type='indicator'` 的策略：

```python
if indicator.get('code_type') != 'indicator':
    return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400
```

---

## 测试方法

### 使用测试脚本
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
./test_indicator_apis.sh
```

### 手动测试

#### 1. 获取指标列表
```bash
curl "http://localhost:5000/api/indicators/list"
```

#### 2. 创建指标
```bash
curl -X POST http://localhost:5000/api/indicators/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试指标",
    "code": "def calculate(df):\n    df[\"ma5\"] = df[\"close\"].rolling(5).mean()\n    df[\"buy\"] = df[\"ma5\"] > df[\"close\"]\n    df[\"sell\"] = df[\"ma5\"] < df[\"close\"]\n    return df"
  }'
```

#### 3. 运行指标
```bash
curl -X POST http://localhost:5000/api/indicators/run/1 \
  -H "Content-Type: application/json" \
  -d '{"symbol": "000001.SZ"}'
```

#### 4. 回测指标
```bash
curl -X POST http://localhost:5000/api/indicators/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "indicatorId": 1,
    "symbol": "000001.SZ",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }'
```

---

## 技术特性

### 1. 统一错误处理
所有接口使用 `@handle_api_error` 装饰器：
- 自动捕获 `ValueError` 返回 400
- 自动捕获 `KeyError` 返回 400
- 自动捕获其他异常返回 500
- 记录详细错误日志

### 2. 命名转换
- **请求**：前端驼峰 → 后端下划线（`convert_keys_to_snake`）
- **响应**：后端下划线 → 前端驼峰（`convert_keys_to_camel`）

### 3. 统一响应格式
```python
{
  "success": true/false,
  "data": {...},
  "message": "操作成功"  // 可选
}
```

### 4. 数据清理
自动处理 NaN/Infinity/日期对象，确保 JSON 序列化成功。

---

## 文件位置

- **实现文件**：`/Users/mac/Documents/ai/pi-investment/quantsys-v2/api/server.py`
- **实现区域**：第1339-1531行（"指标管理" 区域）
- **测试脚本**：`/Users/mac/Documents/ai/pi-investment/quantsys-v2/test_indicator_apis.sh`

---

## 依赖服务

- **StrategyCodeService**：策略代码管理服务
- **IndicatorStrategyExecutor**：指标执行引擎
- **CodeValidator**：代码验证器
- **ParamParser**：参数解析器
- **KlineRepository**：K线数据仓储

---

## 注意事项

1. **类型隔离**：指标和策略共享同一张表，通过 `code_type` 字段区分
2. **验证机制**：创建和更新时自动验证代码语法和结构
3. **执行限制**：只有 `validation_status='valid'` 的指标才能运行和回测
4. **分页处理**：列表接口使用内存分页，适合中小规模数据
5. **错误处理**：所有接口都有完善的错误处理和验证

---

## 下一步

1. 启动 API 服务器：`python api/server.py`
2. 运行测试脚本验证接口
3. 集成到前端应用
4. 添加更多指标模板和示例

