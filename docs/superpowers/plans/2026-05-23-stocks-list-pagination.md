# 股票列表分页功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `/api/stocks/list` 端点实现分页功能，并抽象出四个可复用的分页工具函数。

**Architecture:** 在 `quant/api/server.py` 中添加四个通用分页工具函数（参数验证、元数据计算、查询拼接、响应构建），然后修改 `get_stock_list()` 端点使用这些工具函数。已有 `list_trades()` 端点的手动分页模式作为参考。

**Tech Stack:** Python 3, Flask, PostgreSQL (via PostgresCompatCursor)

---

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `quant/api/server.py` | 修改 | 添加 4 个分页工具函数 + 修改 `get_stock_list()` 端点 |

所有修改在一个文件中，因为：
- 工具函数是 Flask 应用的内部辅助函数
- `get_stock_list()` 是该文件的 Flask 路由
- 遵循项目中已有的工具函数模式（如 `_normalize_symbols`、`_normalize_job_for_web` 等）

---

### Task 1: 添加分页工具函数

**文件：**
- 修改: `quant/api/server.py` 第 804 行之后（`_normalize_symbols` 之后，`_symbols_args` 之前）

**四个工具函数：**

1. `_validate_pagination_params(page, page_size, max_page_size=100)` — 验证并规范化分页参数，无效时抛出 `ValueError`
2. `_calculate_pagination_metadata(page, page_size, total)` — 计算分页元数据字典
3. `_paginate_query(query, params, page, page_size)` — 在 SQL 查询后追加 `LIMIT ? OFFSET ?`
4. `_build_paginated_response(items, page, page_size, total, items_key='items')` — 构建标准分页响应

- [ ] **Step 1: 添加 `_validate_pagination_params` 函数**

打开 `quant/api/server.py`，在 `_normalize_symbols` 函数之后（第 804 行空行之后）、`_symbols_args` 之前（第 807 行），插入以下代码：

```python
def _validate_pagination_params(page, page_size, max_page_size=100):
    """验证并规范化分页参数。

    Args:
        page: 页码（可能为 None 或未传递的默认值）
        page_size: 每页条数（可能为 None 或未传递的默认值）
        max_page_size: 最大每页条数，默认 100

    Returns:
        (validated_page, validated_page_size) 元组，均为整数

    Raises:
        ValueError: 参数无效时
    """
    if page is None:
        page = 1
    if page_size is None:
        page_size = 10

    if not isinstance(page, int):
        raise ValueError("Invalid page parameter: must be an integer")
    if not isinstance(page_size, int):
        raise ValueError("Invalid pageSize parameter: must be an integer")

    if page < 1:
        raise ValueError("Invalid page parameter: must be >= 1")
    if page_size < 1:
        raise ValueError("Invalid pageSize parameter: must be >= 1")
    if page_size > max_page_size:
        raise ValueError(f"Invalid pageSize parameter: must be <= {max_page_size}")

    return (page, page_size)
```

- [ ] **Step 2: 添加 `_calculate_pagination_metadata` 函数**

在上述函数之后插入：

```python
def _calculate_pagination_metadata(page, page_size, total):
    """计算分页元数据。

    Args:
        page: 当前页码
        page_size: 每页条数
        total: 总记录数

    Returns:
        包含 page, pageSize, total, totalPages, hasNext, hasPrev 的字典
    """
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrev": page > 1,
    }
```

- [ ] **Step 3: 添加 `_paginate_query` 函数**

在上述函数之后插入：

```python
def _paginate_query(query, params, page, page_size):
    """在 SQL 查询末尾添加 LIMIT 和 OFFSET 子句。

    Args:
        query: 原始 SQL 查询字符串
        params: 原始查询参数列表
        page: 页码
        page_size: 每页条数

    Returns:
        (paginated_query, paginated_params) 元组
    """
    offset = (page - 1) * page_size
    paginated_query = f"{query} LIMIT ? OFFSET ?"
    paginated_params = params + [page_size, offset]
    return (paginated_query, paginated_params)
```

- [ ] **Step 4: 添加 `_build_paginated_response` 函数**

在上述函数之后插入：

```python
def _build_paginated_response(items, page, page_size, total, items_key="items"):
    """构建标准的分页响应格式。

    Args:
        items: 数据列表
        page: 当前页码
        page_size: 每页条数
        total: 总记录数
        items_key: 数据列表在响应中的键名，默认 'items'

    Returns:
        {"success": True, "data": {items_key: [...], "pagination": {...}}}
    """
    pagination = _calculate_pagination_metadata(page, page_size, total)
    return {
        "success": True,
        "data": {
            items_key: items,
            "pagination": pagination,
        },
    }
```

- [ ] **Step 5: 验证语法正确**

运行 Python 语法检查：

```bash
cd quant && python3 -c "import py_compile; py_compile.compile('api/server.py', doraise=True); print('OK')"
```

预期输出: `OK`

---

### Task 2: 修改 `get_stock_list()` 端点为分页版本

**文件：**
- 修改: `quant/api/server.py` 第 1938-1984 行

- [ ] **Step 1: 替换 `get_stock_list` 函数体**

将原来的函数（第 1938-1984 行）：

```python
@app.route('/api/stocks/list', methods=['GET'])
def get_stock_list():
    """获取股票列表（兼容 quant_api.py 格式）"""
    try:
        market = request.args.get('market')
        has_data = request.args.get('has_data', type=bool, default=False)

        conn = get_db()

        if has_data:
            query = """
                SELECT DISTINCT s.symbol, s.name, s.market
                FROM stocks s
                INNER JOIN daily_klines k ON s.symbol = k.symbol
            """
            params = []
            if market:
                query += " WHERE s.market = ?"
                params.append(market)
            query += " ORDER BY s.symbol"
        else:
            query = "SELECT symbol, name, market FROM stocks"
            params = []
            if market:
                query += " WHERE market = ?"
                params.append(market)
            query += " ORDER BY symbol"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2]
            })

        return jsonify({
            'count': len(stocks),
            'stocks': stocks
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

替换为：

```python
@app.route('/api/stocks/list', methods=['GET'])
def get_stock_list():
    """获取股票列表（兼容 quant_api.py 格式，支持分页）"""
    try:
        # 验证分页参数
        page, page_size = _validate_pagination_params(
            request.args.get('page', type=int, default=1),
            request.args.get('pageSize', type=int, default=10)
        )

        market = request.args.get('market')
        has_data = request.args.get('has_data', type=bool, default=False)

        conn = get_db()

        if has_data:
            data_query = """
                SELECT DISTINCT s.symbol, s.name, s.market
                FROM stocks s
                INNER JOIN daily_klines k ON s.symbol = k.symbol
            """
            count_query = """
                SELECT COUNT(DISTINCT s.symbol)
                FROM stocks s
                INNER JOIN daily_klines k ON s.symbol = k.symbol
            """
            filter_clause = ""
            filter_params = []
            if market:
                filter_clause = " WHERE s.market = ?"
                filter_params = [market]
            order_clause = " ORDER BY s.symbol"
        else:
            data_query = "SELECT symbol, name, market FROM stocks"
            count_query = "SELECT COUNT(*) FROM stocks"
            filter_clause = ""
            filter_params = []
            if market:
                filter_clause = " WHERE market = ?"
                filter_params = [market]
            order_clause = " ORDER BY symbol"

        # 获取总数
        total = conn.execute(
            count_query + filter_clause, filter_params
        ).fetchone()[0]

        # 构建并执行分页查询
        full_query = data_query + filter_clause + order_clause
        paginated_query, paginated_params = _paginate_query(
            full_query, filter_params, page, page_size
        )
        cursor = conn.execute(paginated_query, paginated_params)
        rows = cursor.fetchall()
        conn.close()

        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2]
            })

        return jsonify(_build_paginated_response(
            stocks, page, page_size, total, items_key='stocks'
        ))

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 2: 验证语法正确**

运行 Python 语法检查：

```bash
cd quant && python3 -c "import py_compile; py_compile.compile('api/server.py', doraise=True); print('OK')"
```

预期输出: `OK`

---

### Task 3: 重构 `list_trades()` 使用分页工具函数

**文件：**
- 修改: `quant/api/server.py` 第 4242-4324 行

- [ ] **Step 1: 替换 `list_trades` 函数中手动分页的部分**

将第 4246-4248 行的参数获取和第 4270-4275 行的 offset 计算逻辑替换为使用工具函数。

原来的第 4245-4248 行：
```python
        page = request.args.get('page', type=int, default=1)
        page_size = request.args.get('pageSize', type=int, default=20)
        symbol = request.args.get('symbol')
        direction = request.args.get('direction')  # buy/sell
```

替换为：
```python
        page, page_size = _validate_pagination_params(
            request.args.get('page', type=int, default=1),
            request.args.get('pageSize', type=int, default=20)
        )
        symbol = request.args.get('symbol')
        direction = request.args.get('direction')  # buy/sell
```

原来的第 4252-4280 行：
```python
        # 计算偏移量
        offset = (page - 1) * page_size

        # 构建查询
        conn = get_db()

        # 构建WHERE条件
        conditions = []
        params = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if direction:
            conditions.append("action = ?")
            params.append(direction)

        if keyword:
            conditions.append("(symbol LIKE ? OR notes LIKE ?)")
            params.append(f'%{keyword}%')
            params.append(f'%{keyword}%')

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM position_history {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        # 获取数据
        query = f"""
            SELECT id, symbol, action, shares, price, amount, timestamp, notes, realized_pnl
            FROM position_history
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([page_size, offset])
        cursor = conn.execute(query, params)
```

替换为：
```python
        # 构建查询
        conn = get_db()

        # 构建WHERE条件
        conditions = []
        params = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if direction:
            conditions.append("action = ?")
            params.append(direction)

        if keyword:
            conditions.append("(symbol LIKE ? OR notes LIKE ?)")
            params.append(f'%{keyword}%')
            params.append(f'%{keyword}%')

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM position_history {where_clause}"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]

        # 执行分页查询
        base_query = f"""
            SELECT id, symbol, action, shares, price, amount, timestamp, notes, realized_pnl
            FROM position_history
            {where_clause}
            ORDER BY timestamp DESC
        """
        paginated_query, paginated_params = _paginate_query(
            base_query, params, page, page_size
        )
        cursor = conn.execute(paginated_query, paginated_params)
```

然后将第 4310-4319 行的响应构建：
```python
        return jsonify({
            'success': True,
            'data': {
                'trades': trades,
                'total': total,
                'page': page,
                'pageSize': page_size,
                'totalPages': (total + page_size - 1) // page_size
            }
        })
```

替换为：
```python
        return jsonify(_build_paginated_response(
            trades, page, page_size, total, items_key='trades'
        ))
```

最后，在第 4321 行 `except Exception as e:` 之前加入对 `ValueError` 的捕获：
```python
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
```

- [ ] **Step 2: 验证语法正确**

运行 Python 语法检查：

```bash
cd quant && python3 -c "import py_compile; py_compile.compile('api/server.py', doraise=True); print('OK')"
```

预期输出: `OK`

---

### Task 4: 启动服务并手动验证

- [ ] **Step 1: 启动 Flask 服务**

```bash
cd quant && python3 api/server.py &
sleep 2
```

- [ ] **Step 2: 测试默认分页**

```bash
curl -s "http://localhost:5001/api/stocks/list" | python3 -m json.tool
```

预期: 返回 `success: true`，`data.stocks` 最多 10 条，`data.pagination` 包含 `page: 1, pageSize: 10, total, totalPages, hasNext, hasPrev`

- [ ] **Step 3: 测试指定页码和页大小**

```bash
curl -s "http://localhost:5001/api/stocks/list?page=2&pageSize=5" | python3 -m json.tool
```

预期: page=2, pageSize=5, stocks 最多 5 条

- [ ] **Step 4: 测试参数验证**

```bash
curl -s "http://localhost:5001/api/stocks/list?page=0" | python3 -m json.tool
```

预期: 400 错误 "Invalid page parameter: must be >= 1"

```bash
curl -s "http://localhost:5001/api/stocks/list?pageSize=101" | python3 -m json.tool
```

预期: 400 错误 "Invalid pageSize parameter: must be <= 100"

- [ ] **Step 5: 测试筛选 + 分页组合**

```bash
curl -s "http://localhost:5001/api/stocks/list?market=A&page=1&pageSize=10" | python3 -m json.tool
```

预期: 只返回 market=A 的股票，正确分页

- [ ] **Step 6: 测试 list_trades 端点仍正常工作**

```bash
curl -s "http://localhost:5001/api/trades/list?page=1&pageSize=10" | python3 -m json.tool
```

预期: 返回标准分页响应格式

- [ ] **Step 7: 停止服务**

```bash
kill %1 2>/dev/null
```

---

### Task 5: 提交

- [ ] **Step 1: 暂存并提交**

```bash
git add quant/api/server.py
git commit -m "$(cat <<'EOF'
feat(api): add pagination support to stocks list endpoint

Add four reusable pagination utility functions and apply them to
/api/stocks/list and /api/trades/list endpoints. Supports page and
pageSize query params with full pagination metadata in the response.
EOF
)"
```
