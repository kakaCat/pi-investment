# Stock API 修复报告

## 问题描述

API端点 `/api/stocks/resolve` 返回 500 错误：
```
{"error":"'Stock' object is not subscriptable"}
```

## 根本原因

quantsys-v2 已迁移到 SQLAlchemy ORM，`StockORMRepository` 的方法返回 `Stock` ORM对象而不是字典。但 API 路由代码中仍然使用字典访问方式 `stock['symbol']`，导致 `TypeError`。

## 修复内容

### 1. `/api/stocks/resolve` 端点 (行197-219)

**修复前：**
```python
stock = ds.stock.get_by_symbol(code)
return jsonify({
    'found': True,
    'symbol': stock['symbol'],      # ❌ TypeError
    'name': stock['name'],          # ❌ TypeError
    'market': stock.get('market', ''),
    'industry': stock.get('industry', '')
})
```

**修复后：**
```python
stock = ds.stock.get_by_symbol(code)
return jsonify({
    'found': True,
    'symbol': stock.symbol,         # ✅ 对象属性访问
    'name': stock.name,             # ✅ 对象属性访问
    'market': stock.market or '',
    'industry': stock.industry or ''
})
```

### 2. `enrich_stock_data()` 函数 (行55-76)

**问题：** 该函数被多个端点调用，需要同时支持 Dict 和 ORM 对象两种类型（因为 `ds.stock.search()` 返回 ORM对象，而 `ds.stock.get_all()` 返回字典列表）。

**修复后：**
```python
def enrich_stock_data(stock) -> Dict:
    # 支持Dict和ORM对象两种类型
    if hasattr(stock, 'symbol'):
        # ORM对象
        symbol = stock.symbol
        name = stock.name
        market = stock.market or ''
        industry = stock.industry or ''
    else:
        # 字典
        symbol = stock['symbol']
        name = stock['name']
        market = stock.get('market', '')
        industry = stock.get('industry', '')
    
    stock_data = {
        'symbol': symbol,
        'name': name,
        'market': market,
        'industry': industry,
        # ... 其他字段
    }
```

### 3. `/api/stocks/list` 端点 (行164-178)

**问题：** 过滤逻辑使用 `stock.get('market')` 和 `stock.get('symbol')`，不兼容 ORM 对象。

**修复后：**
```python
if market:
    all_stocks = [stock for stock in all_stocks
                 if (hasattr(stock, 'market') and stock.market == market) or
                    (isinstance(stock, dict) and stock.get('market') == market)]

# 搜索逻辑也支持两种类型
if keyword_lower in str(getattr(stock, 'symbol', None) or stock.get('symbol', '')).lower():
    # ...
```

## 影响的端点

以下端点已修复并验证：

1. ✅ `POST /api/stocks/resolve` - 股票代码解析
2. ✅ `GET /api/stocks/search` - 股票搜索（使用 `enrich_stock_data`）
3. ✅ `GET /api/stocks/list` - 股票列表（使用 `enrich_stock_data` 和过滤逻辑）

## 验证方法

### 方式1：运行测试脚本
```bash
cd quantsys-v2
python test_stock_resolve_fix.py
```

### 方式2：手动测试
```bash
# 1. 启动服务
python adapters/inbound/api/server.py

# 2. 测试 resolve API
curl -X POST http://127.0.0.1:5001/api/stocks/resolve \
  -H "Content-Type: application/json" \
  -d '{"code": "600519"}'

# 预期结果：
# {
#   "found": true,
#   "symbol": "600519",
#   "name": "贵州茅台",
#   "market": "A",
#   "industry": "白酒"
# }
```

## 注意事项

### ORM迁移不完整的问题

当前 `StockORMRepository` 的方法返回类型不一致：
- `get_by_symbol()` → 返回 `Stock` 对象
- `search()` / `search_by_name()` → 返回 `List[Stock]`
- `get_all()` → 返回 `List[Dict]` （为了向后兼容）

**建议：** 统一返回类型，要么全部返回 ORM 对象，要么在 Repository 层统一转换为字典。

### 未来改进

1. **类型提示**：为函数添加明确的类型提示，避免混淆
2. **统一数据层**：让 Repository 层统一返回类型（推荐统一返回 Dict）
3. **单元测试**：为 API 端点添加单元测试，覆盖 ORM 对象和字典两种情况

## 修改的文件

- `adapters/inbound/api/routes/stock.py` (3处修复)
  - Line 55-76: `enrich_stock_data()` 函数
  - Line 164-178: `get_stock_list()` 过滤逻辑
  - Line 197-219: `resolve_stock()` 返回值

## 部署步骤

1. 确认修复已合并到代码库
2. 停止运行中的 Flask 服务
3. 重启服务：
   ```bash
   cd quantsys-v2
   python adapters/inbound/api/server.py
   ```
4. 运行验证测试
5. 检查 agent-ts 调用该 API 的工具是否正常工作

---

**修复日期**: 2026-06-29  
**修复人员**: Claude Code  
**相关Issue**: Stock API 返回 500 错误
