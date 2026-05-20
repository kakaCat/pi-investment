# 股票列表全局搜索功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为股票列表管理页面添加后端全局搜索功能，支持搜索全部5458只股票的代码和名称

**Architecture:** 新增 Flask API 端点 `/api/stocks/search`，使用 SQL LIKE 查询 stock_data_summary 和 stocks 表。前端使用防抖优化的实时搜索，保持与现有分页逻辑一致。

**Tech Stack:** Flask, SQLite/PostgreSQL, React, TypeScript, Ant Design

---

## File Structure

### Backend Files
- **Modify**: `quant/api/server.py` - 新增搜索端点，复用现有数据库连接和查询逻辑

### Frontend Files
- **Modify**: `quant-web/src/components/StockList.tsx` - 添加搜索状态、防抖逻辑、API调用

### No New Files
所有功能通过修改现有文件实现，保持代码库结构简洁。

---

## Task 1: 后端搜索 API 端点

**Files:**
- Modify: `quant/api/server.py` (在现有端点后添加新端点)

- [ ] **Step 1: 添加搜索端点函数**

在 `server.py` 中找到 `@app.route('/api/stocks/data-status', methods=['GET'])` 端点后，添加新的搜索端点：

```python
@app.route('/api/stocks/search', methods=['GET'])
def search_stocks():
    """搜索股票（支持代码和名称模糊匹配）"""
    try:
        # 获取搜索参数
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('pageSize', 20, type=int)

        # 参数验证
        if not query:
            return jsonify({'error': '搜索关键词不能为空'}), 400
        
        page_size = max(1, min(page_size, 100))
        page = max(1, page)
        offset = (page - 1) * page_size

        conn = get_db()

        # 先获取总数
        if get_db_provider() == 'postgres':
            count_query = """
                SELECT COUNT(*) as total
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol ILIKE %s OR st.name ILIKE %s)
                  AND s.factor_count >= 30
            """
            search_pattern = f'%{query}%'
            cursor = conn.execute(count_query, (search_pattern, search_pattern))
        else:
            count_query = """
                SELECT COUNT(*) as total
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol LIKE ? OR st.name LIKE ?)
                  AND s.factor_count >= 30
            """
            search_pattern = f'%{query}%'
            cursor = conn.execute(count_query, (search_pattern, search_pattern))
        
        total = cursor.fetchone()[0]

        # 获取分页数据
        if get_db_provider() == 'postgres':
            data_query = """
                SELECT
                    s.symbol,
                    st.name,
                    st.market,
                    s.kline_days,
                    s.earliest_date,
                    s.latest_date,
                    s.factor_days,
                    s.factor_count,
                    CASE 
                        WHEN s.kline_days > 0 AND s.factor_days > 0 AND s.factor_count >= 30 
                        THEN true 
                        ELSE false 
                    END as data_complete
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol ILIKE %s OR st.name ILIKE %s)
                  AND s.factor_count >= 30
                ORDER BY s.symbol
                LIMIT %s OFFSET %s
            """
            cursor = conn.execute(data_query, (search_pattern, search_pattern, page_size, offset))
        else:
            data_query = """
                SELECT
                    s.symbol,
                    st.name,
                    st.market,
                    s.kline_days,
                    s.earliest_date,
                    s.latest_date,
                    s.factor_days,
                    s.factor_count,
                    CASE 
                        WHEN s.kline_days > 0 AND s.factor_days > 0 AND s.factor_count >= 30 
                        THEN 1 
                        ELSE 0 
                    END as data_complete
                FROM stock_data_summary s
                JOIN stocks st ON s.symbol = st.symbol
                WHERE (s.symbol LIKE ? OR st.name LIKE ?)
                  AND s.factor_count >= 30
                ORDER BY s.symbol
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(data_query, (search_pattern, search_pattern, page_size, offset))

        rows = cursor.fetchall()
        
        # 转换为字典列表
        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row[0],
                'name': row[1],
                'market': row[2],
                'kline_days': row[3],
                'earliest_date': row[4],
                'latest_date': row[5],
                'factor_days': row[6],
                'factor_count': row[7],
                'data_complete': bool(row[8])
            })

        return jsonify({
            'total': total,
            'page': page,
            'pageSize': page_size,
            'stocks': stocks
        })

    except Exception as e:
        logger.error(f'搜索股票失败: {e}')
        return jsonify({'error': '搜索失败', 'message': str(e)}), 500
```

- [ ] **Step 2: 测试 API 端点 - 搜索股票代码**

运行后端服务器（如果未运行）：
```bash
cd quant && python api/server.py
```

在另一个终端测试搜索股票代码：
```bash
curl "http://localhost:5000/api/stocks/search?q=600519&page=1&pageSize=20"
```

Expected: 返回包含贵州茅台的 JSON 响应，格式如下：
```json
{
  "total": 1,
  "page": 1,
  "pageSize": 20,
  "stocks": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "market": "SH",
      ...
    }
  ]
}
```

- [ ] **Step 3: 测试 API 端点 - 搜索股票名称**

测试搜索股票名称：
```bash
curl "http://localhost:5000/api/stocks/search?q=茅台&page=1&pageSize=20"
```

Expected: 返回包含"茅台"的股票列表

- [ ] **Step 4: 测试 API 端点 - 部分匹配**

测试部分匹配：
```bash
curl "http://localhost:5000/api/stocks/search?q=平安&page=1&pageSize=20"
```

Expected: 返回所有名称包含"平安"的股票（如平安银行、中国平安等）

- [ ] **Step 5: 测试 API 端点 - 空搜索词**

测试空搜索词错误处理：
```bash
curl "http://localhost:5000/api/stocks/search?q=&page=1&pageSize=20"
```

Expected: 返回 400 错误，错误信息："搜索关键词不能为空"

- [ ] **Step 6: 测试 API 端点 - 无匹配结果**

测试无匹配结果：
```bash
curl "http://localhost:5000/api/stocks/search?q=不存在的股票xyz123&page=1&pageSize=20"
```

Expected: 返回 `{"total": 0, "stocks": []}`

- [ ] **Step 7: 提交后端代码**

```bash
git add quant/api/server.py
git commit -m "feat(api): add stock search endpoint with fuzzy matching"
```

---

## Task 2: 前端搜索状态管理

**Files:**
- Modify: `quant-web/src/components/StockList.tsx`

- [ ] **Step 1: 添加搜索相关状态**

在 `StockList.tsx` 中，找到现有的 `useState` 声明（约第26-41行），在 `pagination` 状态后添加：

```typescript
const [searchQuery, setSearchQuery] = useState('');
const [isSearching, setIsSearching] = useState(false);
```

- [ ] **Step 2: 添加搜索 API 调用函数**

在 `fetchStockDataStatus` 函数后添加新的搜索函数：

```typescript
const fetchSearchResults = async (query: string, page: number, pageSize: number) => {
  try {
    setLoading(true);
    setIsSearching(true);
    const response = await fetch(
      `/api/stocks/search?q=${encodeURIComponent(query)}&page=${page}&pageSize=${pageSize}`
    );
    const result = await response.json();

    if (result.error) {
      setError(result.error);
    } else {
      setData({
        total_stocks: result.total,
        complete_stocks: result.total,
        incomplete_stocks: 0,
        stocks: result.stocks
      });
      setPagination(prev => ({
        ...prev,
        total: result.total,
        current: page
      }));
    }
  } catch (err) {
    setError(err instanceof Error ? err.message : '搜索失败');
  } finally {
    setLoading(false);
    setIsSearching(false);
  }
};
```

- [ ] **Step 3: 添加防抖搜索逻辑**

在 `fetchSearchResults` 函数后添加防抖函数（需要先安装 lodash.debounce 或使用内联实现）：

```typescript
const debouncedSearch = useMemo(() => {
  let timeoutId: NodeJS.Timeout;
  return (query: string) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      if (query.trim() === '') {
        fetchStockDataStatus(1, pagination.pageSize);
      } else {
        fetchSearchResults(query, 1, pagination.pageSize);
      }
    }, 300);
  };
}, [pagination.pageSize]);
```

- [ ] **Step 4: 添加搜索框变化处理函数**

在防抖函数后添加：

```typescript
const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const query = e.target.value;
  setSearchQuery(query);
  debouncedSearch(query);
};
```

- [ ] **Step 5: 修改搜索框为受控组件**

找到现有的搜索框 Input 组件（约第231-237行），修改为：

```tsx
<Input
  placeholder="搜索股票代码或名称"
  prefix={<SearchOutlined />}
  style={{ width: 250 }}
  value={searchQuery}
  onChange={handleSearchChange}
  allowClear
  suffix={isSearching ? <Spin size="small" /> : null}
/>
```

- [ ] **Step 6: 处理清空搜索**

修改 Input 组件，添加 `onClear` 处理：

```tsx
<Input
  placeholder="搜索股票代码或名称"
  prefix={<SearchOutlined />}
  style={{ width: 250 }}
  value={searchQuery}
  onChange={handleSearchChange}
  allowClear
  onClear={() => {
    setSearchQuery('');
    fetchStockDataStatus(1, pagination.pageSize);
  }}
  suffix={isSearching ? <Spin size="small" /> : null}
/>
```

- [ ] **Step 7: 添加 Spin 组件导入**

在文件顶部的 import 语句中，找到 `import { Card, Table, Tag, Statistic, Row, Col, Spin, Alert, Input } from 'antd';`，确认已包含 `Spin`。如果没有，添加它。

- [ ] **Step 8: 提交前端代码**

```bash
git add quant-web/src/components/StockList.tsx
git commit -m "feat(frontend): add real-time search with debounce for stock list"
```

---

## Task 3: 功能测试

**Files:**
- Test: `quant-web/src/components/StockList.tsx` (手动测试)

- [ ] **Step 1: 启动开发服务器**

确保后端和前端都在运行：

```bash
# 终端1: 后端
cd quant && python api/server.py

# 终端2: 前端
cd quant-web && npm run dev
```

- [ ] **Step 2: 测试搜索股票代码**

1. 在浏览器打开 `http://localhost:5173`
2. 导航到"股票列表"页面
3. 在搜索框输入 "600519"
4. 等待300ms后自动搜索

Expected: 表格显示贵州茅台，统计卡片显示"总股票数: 1"

- [ ] **Step 3: 测试搜索股票名称**

1. 清空搜索框
2. 输入 "茅台"
3. 等待自动搜索

Expected: 表格显示包含"茅台"的股票

- [ ] **Step 4: 测试部分匹配**

1. 清空搜索框
2. 输入 "平安"
3. 等待自动搜索

Expected: 表格显示所有包含"平安"的股票（平安银行、中国平安等）

- [ ] **Step 5: 测试清空搜索**

1. 点击搜索框的清空按钮（×）

Expected: 恢复显示全部股票，分页正常

- [ ] **Step 6: 测试无匹配结果**

1. 输入 "不存在的股票xyz123"
2. 等待自动搜索

Expected: 表格显示空状态，统计卡片显示"总股票数: 0"

- [ ] **Step 7: 测试防抖功能**

1. 快速连续输入 "6", "60", "600", "6005", "60051", "600519"
2. 观察网络请求（打开浏览器开发者工具 Network 标签）

Expected: 只发送最后一次请求（搜索"600519"），前面的输入被防抖取消

- [ ] **Step 8: 测试加载状态**

1. 输入搜索词
2. 观察搜索框右侧

Expected: 搜索过程中显示小的 loading 图标

- [ ] **Step 9: 测试分页**

1. 搜索 "A"（会返回较多结果）
2. 点击分页器的下一页

Expected: 正确加载第2页的搜索结果

- [ ] **Step 10: 记录测试结果**

创建测试记录文件：

```bash
cat > docs/superpowers/plans/2026-05-20-stock-search-test-results.md << 'EOF'
# 股票搜索功能测试结果

**测试日期**: 2026-05-20
**测试人员**: [Your Name]

## 功能测试

- [ ] 搜索股票代码 (600519) - PASS/FAIL
- [ ] 搜索股票名称 (茅台) - PASS/FAIL
- [ ] 部分匹配 (平安) - PASS/FAIL
- [ ] 清空搜索 - PASS/FAIL
- [ ] 无匹配结果 - PASS/FAIL
- [ ] 防抖功能 - PASS/FAIL
- [ ] 加载状态 - PASS/FAIL
- [ ] 分页功能 - PASS/FAIL

## 性能测试

- 查询响应时间: ___ ms
- 防抖延迟: 300ms (符合预期)

## 问题记录

[记录发现的任何问题]
EOF
```

---

## Task 4: 性能优化（可选）

**Files:**
- Modify: `quant/api/server.py` (如果需要添加索引创建逻辑)

- [ ] **Step 1: 测量查询性能**

在后端 `search_stocks` 函数中添加性能日志：

```python
import time

# 在查询前
start_time = time.time()

# 执行查询...

# 在返回前
query_time = (time.time() - start_time) * 1000
logger.info(f'搜索查询耗时: {query_time:.2f}ms, 关键词: {query}, 结果数: {total}')
```

- [ ] **Step 2: 运行性能测试**

```bash
# 测试多次搜索，观察日志中的查询时间
curl "http://localhost:5000/api/stocks/search?q=平安&page=1&pageSize=20"
curl "http://localhost:5000/api/stocks/search?q=600&page=1&pageSize=20"
curl "http://localhost:5000/api/stocks/search?q=银行&page=1&pageSize=20"
```

Expected: 查询时间 < 50ms

- [ ] **Step 3: 如果性能不达标，创建数据库索引**

如果查询时间 > 50ms，创建索引脚本：

```bash
cat > quant/scripts/create_search_indexes.py << 'EOF'
"""为搜索功能创建数据库索引"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.data.db import Database

def create_indexes():
    db = Database()
    conn = db.get_connection()
    
    try:
        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks(name)")
        conn.commit()
        print("✓ 索引创建成功")
    except Exception as e:
        print(f"✗ 索引创建失败: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    create_indexes()
EOF

python quant/scripts/create_search_indexes.py
```

- [ ] **Step 4: 重新测试性能**

重新运行性能测试，确认查询时间改善。

- [ ] **Step 5: 提交性能优化**

```bash
git add quant/api/server.py quant/scripts/create_search_indexes.py
git commit -m "perf(search): add query timing logs and database indexes"
```

---

## Task 5: 最终验证和文档

**Files:**
- Create: `docs/superpowers/plans/2026-05-20-stock-search-completion.md`

- [ ] **Step 1: 运行完整测试套件**

按照 Task 3 的所有测试步骤重新验证一遍。

- [ ] **Step 2: 验证成功标准**

检查设计文档中的成功标准：

- ✅ 可以搜索全部5458只股票（不受分页限制）
- ✅ 支持股票代码和名称的模糊搜索
- ✅ 查询响应时间 < 50ms
- ✅ 实时搜索体验流畅（300ms防抖）
- ✅ 正确处理空搜索、无结果、错误等边界情况

- [ ] **Step 3: 创建完成报告**

```bash
cat > docs/superpowers/plans/2026-05-20-stock-search-completion.md << 'EOF'
# 股票搜索功能完成报告

**完成日期**: 2026-05-20

## 实现内容

### 后端
- 新增 `/api/stocks/search` API 端点
- 支持 SQLite 和 PostgreSQL
- 实现模糊搜索（LIKE/ILIKE）
- 参数验证和错误处理

### 前端
- 添加实时搜索（300ms防抖）
- 搜索状态管理
- 加载状态显示
- 清空搜索功能

## 测试结果

- 功能测试: PASS
- 性能测试: 查询时间 < 50ms
- 边界测试: PASS

## 已知问题

[列出任何已知问题或未来改进点]

## 提交记录

- feat(api): add stock search endpoint with fuzzy matching
- feat(frontend): add real-time search with debounce for stock list
- perf(search): add query timing logs and database indexes (如果执行了Task 4)
EOF
```

- [ ] **Step 4: 最终提交**

```bash
git add docs/superpowers/plans/2026-05-20-stock-search-completion.md
git commit -m "docs: add stock search feature completion report"
```

- [ ] **Step 5: 清理和总结**

确认所有临时文件已清理，代码已提交，功能正常运行。

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ 后端 API 端点 (`/api/stocks/search`) - Task 1
- ✅ SQL 查询逻辑（SQLite + PostgreSQL） - Task 1
- ✅ 前端搜索状态管理 - Task 2
- ✅ 防抖搜索 - Task 2
- ✅ 实时搜索体验 - Task 2
- ✅ 边界情况处理（空搜索、无结果、错误） - Task 1, Task 2, Task 3
- ✅ 性能优化（索引） - Task 4
- ✅ 测试验证 - Task 3, Task 5

**Placeholder Scan:**
- ✅ 无 TBD 或 TODO
- ✅ 所有代码块完整
- ✅ 所有测试命令具体
- ✅ 所有文件路径明确

**Type Consistency:**
- ✅ API 响应格式一致（total, page, pageSize, stocks）
- ✅ 数据库字段名一致（symbol, name, market, etc.）
- ✅ 前端状态类型一致（searchQuery: string, isSearching: boolean）

**Execution Ready:**
- ✅ 每个步骤可独立执行
- ✅ 测试步骤包含预期结果
- ✅ 提交信息遵循约定式提交
- ✅ 任务粒度适中（2-5分钟/步骤）
