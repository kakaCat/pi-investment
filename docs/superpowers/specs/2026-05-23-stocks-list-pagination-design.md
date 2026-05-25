# 股票列表分页功能设计文档

## 概述

为 `/api/stocks/list` 端点添加分页功能，并提供可复用的分页工具函数供其他端点使用。

**设计日期：** 2026-05-23  
**目标端点：** `GET /api/stocks/list`  
**数据规模：** < 100 只股票  
**分页策略：** OFFSET/LIMIT 分页

## 背景

当前 `/api/stocks/list` 端点返回所有符合筛选条件的股票，前端传递了 `page` 和 `pageSize` 参数但后端未实现分页逻辑。虽然当前数据量较小（< 100 条），但为了 UX 一致性和未来扩展性，需要实现标准的分页功能。

## 设计目标

1. **实现分页功能** - 支持 page 和 pageSize 参数，返回完整的分页元数据
2. **可复用设计** - 抽象分页逻辑为工具函数，供其他端点使用
3. **向后兼容** - 保持现有筛选功能（market, has_data）不变
4. **参数验证** - 对分页参数进行严格验证，返回清晰的错误信息

## API 接口设计

### 请求参数

**端点：** `GET /api/stocks/list`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码，从 1 开始 |
| pageSize | integer | 否 | 10 | 每页条数，范围 1-100 |
| market | string | 否 | - | 市场筛选 (A/HK) |
| has_data | boolean | 否 | false | 是否只返回有K线数据的股票 |

### 响应格式

**成功响应 (200)：**

```json
{
  "success": true,
  "data": {
    "stocks": [
      {
        "symbol": "600036",
        "name": "招商银行",
        "market": "A"
      }
    ],
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "total": 41,
      "totalPages": 5,
      "hasNext": true,
      "hasPrev": false
    }
  }
}
```

**错误响应 (400)：**

```json
{
  "success": false,
  "error": "Invalid page parameter: must be >= 1"
}
```

### 分页元数据说明

- `page`: 当前页码
- `pageSize`: 每页条数
- `total`: 符合筛选条件的总记录数
- `totalPages`: 总页数，计算公式：`ceil(total / pageSize)`
- `hasNext`: 是否有下一页，计算公式：`page < totalPages`
- `hasPrev`: 是否有上一页，计算公式：`page > 1`

## 数据库查询设计

### 查询策略

采用两步查询法：

**步骤 1：获取总数**

```sql
-- 基础查询
SELECT COUNT(*) FROM stocks WHERE [filters]

-- has_data=true 时
SELECT COUNT(DISTINCT s.symbol) 
FROM stocks s 
INNER JOIN daily_klines k ON s.symbol = k.symbol 
WHERE [filters]
```

**步骤 2：获取分页数据**

```sql
-- 基础查询
SELECT symbol, name, market 
FROM stocks 
WHERE [filters]
ORDER BY symbol 
LIMIT ? OFFSET ?

-- has_data=true 时
SELECT DISTINCT s.symbol, s.name, s.market
FROM stocks s
INNER JOIN daily_klines k ON s.symbol = k.symbol
WHERE [filters]
ORDER BY s.symbol
LIMIT ? OFFSET ?
```

### 计算逻辑

- `OFFSET = (page - 1) * pageSize`
- `LIMIT = pageSize`
- `totalPages = ceil(total / pageSize)`
- `hasNext = page < totalPages`
- `hasPrev = page > 1`

### PostgreSQL 兼容性

现有代码使用 `PostgresCompatCursor` 自动处理 SQL 转换：
- `?` 占位符 → `%s`
- `stocks` → `quant_compat.stocks`
- `daily_klines` → `quant_compat.daily_klines`

分页查询无需特殊处理，自动兼容。

## 可复用的分页工具函数

### 函数设计

**1. `_validate_pagination_params(page, page_size, max_page_size=100)`**

验证并规范化分页参数。

**参数：**
- `page`: 页码（可能为 None）
- `page_size`: 每页条数（可能为 None）
- `max_page_size`: 最大每页条数，默认 100

**返回：**
- `(validated_page, validated_page_size)` 元组

**异常：**
- `ValueError`: 参数无效时抛出，包含清晰的错误信息

**验证规则：**
- page < 1 → ValueError("Invalid page parameter: must be >= 1")
- page_size < 1 → ValueError("Invalid pageSize parameter: must be >= 1")
- page_size > max_page_size → ValueError(f"Invalid pageSize parameter: must be <= {max_page_size}")

---

**2. `_calculate_pagination_metadata(page, page_size, total)`**

计算分页元数据。

**参数：**
- `page`: 当前页码
- `page_size`: 每页条数
- `total`: 总记录数

**返回：**
```python
{
    "page": int,
    "pageSize": int,
    "total": int,
    "totalPages": int,
    "hasNext": bool,
    "hasPrev": bool
}
```

**计算逻辑：**
```python
import math
total_pages = math.ceil(total / page_size) if total > 0 else 0
has_next = page < total_pages
has_prev = page > 1
```

---

**3. `_paginate_query(query, params, page, page_size)`**

在 SQL 查询末尾添加 LIMIT 和 OFFSET。

**参数：**
- `query`: 原始 SQL 查询字符串
- `params`: 原始查询参数列表
- `page`: 页码
- `page_size`: 每页条数

**返回：**
- `(paginated_query, paginated_params)` 元组

**实现：**
```python
offset = (page - 1) * page_size
paginated_query = f"{query} LIMIT ? OFFSET ?"
paginated_params = params + [page_size, offset]
return (paginated_query, paginated_params)
```

---

**4. `_build_paginated_response(items, page, page_size, total, items_key='items')`**

构建标准的分页响应格式。

**参数：**
- `items`: 数据列表
- `page`: 当前页码
- `page_size`: 每页条数
- `total`: 总记录数
- `items_key`: 数据列表的键名，默认 'items'

**返回：**
```python
{
    "success": True,
    "data": {
        items_key: items,
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
            "hasNext": has_next,
            "hasPrev": has_prev
        }
    }
}
```

## 错误处理和边界情况

### 参数验证错误

| 场景 | HTTP 状态码 | 错误信息 |
|------|-------------|----------|
| page < 1 | 400 | "Invalid page parameter: must be >= 1" |
| page 不是整数 | 400 | "Invalid page parameter: must be an integer" |
| pageSize < 1 | 400 | "Invalid pageSize parameter: must be >= 1" |
| pageSize > 100 | 400 | "Invalid pageSize parameter: must be <= 100" |
| pageSize 不是整数 | 400 | "Invalid pageSize parameter: must be an integer" |

### 边界情况处理

**空结果集（total=0）：**
```json
{
  "success": true,
  "data": {
    "stocks": [],
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "total": 0,
      "totalPages": 0,
      "hasNext": false,
      "hasPrev": false
    }
  }
}
```

**请求页码超出范围：**

例如：total=41, pageSize=10, totalPages=5, 但请求 page=10

**处理方式：** 返回空数组，但 pagination 元数据仍然正确显示总数和页数信息，让前端可以引导用户返回有效页码。

```json
{
  "success": true,
  "data": {
    "stocks": [],
    "pagination": {
      "page": 10,
      "pageSize": 10,
      "total": 41,
      "totalPages": 5,
      "hasNext": false,
      "hasPrev": true
    }
  }
}
```

**数据库连接失败：**
- 返回 500: `{"success": false, "error": "Database error: [具体错误信息]"}`
- 保持现有的异常处理机制

## 实现细节

### 修改文件

`quant/api/server.py`

### 实现步骤

**步骤 1：添加分页工具函数**

在文件顶部工具函数区域（约第 400 行附近，`_normalize_symbols` 等函数之后）添加四个分页工具函数。

**步骤 2：修改 `get_stock_list()` 函数**

位置：第 1938-1984 行

修改逻辑：
1. 提取和验证分页参数（使用 `_validate_pagination_params`）
2. 构建 COUNT 查询获取总数
3. 计算分页元数据（使用 `_calculate_pagination_metadata`）
4. 构建分页查询（使用 `_paginate_query`）
5. 执行查询获取数据
6. 构建响应（使用 `_build_paginated_response`，items_key='stocks'）

### 代码风格

- 遵循现有代码风格（4 空格缩进）
- 使用现有的错误处理模式（try-except + jsonify）
- 使用现有的数据库连接方式（`get_db()`）
- 保持与其他端点一致的响应格式

### 向后兼容性

- 不传分页参数时，默认 page=1, pageSize=10
- 现有的 `market` 和 `has_data` 参数功能完全保持不变
- 响应格式改为嵌套结构（data.stocks），但 stocks 数组的数据格式不变

## 可扩展性

这些分页工具函数可以轻松应用到其他需要分页的端点：

### 潜在应用场景

1. **`/api/signals/history`** - 信号历史列表
2. **`/api/jobs`** - 任务列表
3. **`/api/strategies`** - 策略列表
4. **`/api/training/history`** - 训练历史列表
5. **`/api/backtest/runs`** - 回测运行列表

### 使用示例

```python
@app.route('/api/signals/history', methods=['GET'])
def get_signals_history():
    try:
        # 1. 验证分页参数
        page, page_size = _validate_pagination_params(
            request.args.get('page', type=int, default=1),
            request.args.get('pageSize', type=int, default=10)
        )
        
        # 2. 获取总数
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        
        # 3. 执行分页查询
        query = "SELECT * FROM signals ORDER BY date DESC"
        paginated_query, params = _paginate_query(query, [], page, page_size)
        cursor = conn.execute(paginated_query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # 4. 转换数据格式
        signals = [_normalize_signal(dict(row)) for row in rows]
        
        # 5. 构建响应
        return jsonify(_build_paginated_response(
            signals, page, page_size, total, items_key='signals'
        ))
        
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

## 测试计划

### 基本功能测试

| 测试场景 | 预期结果 |
|---------|---------|
| 不传分页参数 | 返回第 1 页，每页 10 条 |
| page=2, pageSize=20 | 返回第 2 页，每页 20 条 |
| 最后一页不满页 | 正确返回剩余数据 |
| 空结果集 | 返回空数组，totalPages=0 |

### 参数验证测试

| 测试场景 | 预期结果 |
|---------|---------|
| page=0 | 400 错误："must be >= 1" |
| page=-1 | 400 错误："must be >= 1" |
| pageSize=0 | 400 错误："must be >= 1" |
| pageSize=101 | 400 错误："must be <= 100" |
| page="abc" | 400 错误："must be an integer" |

### 边界情况测试

| 测试场景 | 预期结果 |
|---------|---------|
| page=999（超出范围） | 返回空数组，元数据正确 |
| total=0 | totalPages=0, hasNext=false, hasPrev=false |
| total=1, pageSize=10 | totalPages=1, hasNext=false |
| total=10, pageSize=10 | totalPages=1, hasNext=false |
| total=11, pageSize=10 | totalPages=2, hasNext=true |

### 现有功能兼容性测试

| 测试场景 | 预期结果 |
|---------|---------|
| market="A" + 分页 | 正确筛选和分页 |
| has_data=true + 分页 | 正确筛选和分页 |
| market="A" + has_data=true + 分页 | 组合筛选正确 |

### 数据库兼容性测试

| 测试场景 | 预期结果 |
|---------|---------|
| PostgreSQL 环境 | SQL 正确转换（? → %s） |
| 表名映射 | stocks → quant_compat.stocks |

### 手动测试命令

```bash
# 测试默认分页
curl "http://localhost:5001/api/stocks/list"

# 测试指定页码
curl "http://localhost:5001/api/stocks/list?page=2&pageSize=20"

# 测试参数验证
curl "http://localhost:5001/api/stocks/list?page=0"

# 测试组合筛选
curl "http://localhost:5001/api/stocks/list?market=A&page=1&pageSize=10"

# 测试超出范围
curl "http://localhost:5001/api/stocks/list?page=999"

# 测试边界值
curl "http://localhost:5001/api/stocks/list?pageSize=1"
curl "http://localhost:5001/api/stocks/list?pageSize=100"
```

### 前端集成测试

- 确认前端表格组件能正确显示分页数据
- 确认页码切换功能正常
- 确认总数和页数显示正确
- 确认筛选 + 分页组合功能正常

## 性能考虑

### 当前场景（< 100 条数据）

- **COUNT 查询：** < 1ms
- **分页查询：** < 1ms
- **总响应时间：** < 5ms

OFFSET/LIMIT 方案完全满足性能需求。

### 未来扩展（> 1000 条数据）

如果数据量增长到数千条，可以考虑以下优化：

1. **添加索引：** 在 `symbol` 列上添加索引（已存在）
2. **游标分页：** 改用 `WHERE symbol > last_symbol LIMIT n` 的游标分页
3. **缓存总数：** 对 COUNT 查询结果进行短期缓存（5-10 分钟）
4. **估算总数：** 使用 PostgreSQL 的统计信息估算总数，避免精确 COUNT

当前设计为这些优化预留了空间，工具函数可以在不影响调用方的情况下升级实现。

## 实现优先级

1. **P0（必须）：** 实现四个分页工具函数
2. **P0（必须）：** 修改 `/api/stocks/list` 端点
3. **P1（建议）：** 为其他列表端点添加分页（如 `/api/strategies`）
4. **P2（可选）：** 添加单元测试覆盖分页工具函数

## 总结

本设计采用标准的 OFFSET/LIMIT 分页方案，通过抽象可复用的工具函数，为项目提供统一的分页能力。设计充分考虑了向后兼容性、参数验证、错误处理和未来扩展性，适合当前数据规模，并为未来增长预留了优化空间。
