# 股票列表全局搜索功能设计

**日期**: 2026-05-20  
**状态**: 已批准  
**预计工作量**: 3小时

## 概述

为股票列表管理页面（StockList.tsx）添加后端全局搜索功能，解决当前只能搜索当前页20条数据的限制，实现对全部5458只股票的搜索能力。

## 当前问题

- **搜索范围受限**: 现有搜索仅过滤前端当前页的20条数据，无法搜索全部股票
- **用户体验差**: 用户需要翻页才能找到不在当前页的股票
- **功能不完整**: 对于5458只股票的数据集，前端过滤无法满足实际需求

## 设计目标

1. 实现后端全局搜索，支持搜索全部5458只股票
2. 保持实时搜索体验，输入即搜索（带防抖优化）
3. 搜索股票代码（symbol）和股票名称（name），支持模糊匹配
4. 查询响应时间 < 50ms，用户体验流畅

## 架构设计

### 系统架构

```
┌─────────────┐      HTTP GET      ┌─────────────┐      SQL Query     ┌─────────────┐
│   前端      │ ─────────────────> │  Flask API  │ ─────────────────> │  Database   │
│ StockList   │  /api/stocks/search│  server.py  │  LIKE '%keyword%'  │ SQLite/PG   │
│             │ <───────────────── │             │ <───────────────── │             │
└─────────────┘      JSON          └─────────────┘      Rows          └─────────────┘
```

### 数据流

1. 用户在搜索框输入关键词
2. 前端防抖300ms后发起API请求
3. 后端执行SQL LIKE查询，搜索symbol和name字段
4. 返回匹配的股票列表（分页）
5. 前端展示搜索结果

## API 设计

### 新增端点

**端点**: `GET /api/stocks/search`

**请求参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| q | string | 是 | - | 搜索关键词 |
| page | integer | 否 | 1 | 页码 |
| pageSize | integer | 否 | 20 | 每页数量，最大100 |

**请求示例**:
```
GET /api/stocks/search?q=茅台&page=1&pageSize=20
```

**响应格式**:
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
      "kline_days": 515,
      "earliest_date": "2024-04-01",
      "latest_date": "2026-05-20",
      "factor_days": 181,
      "factor_count": 31,
      "data_complete": true
    }
  ]
}
```

**错误响应**:
```json
{
  "error": "搜索失败",
  "message": "数据库连接错误"
}
```

### SQL 查询逻辑

**SQLite 版本**:
```sql
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
WHERE (s.symbol LIKE '%' || ? || '%' OR st.name LIKE '%' || ? || '%')
  AND s.factor_count >= 30
ORDER BY s.symbol
LIMIT ? OFFSET ?
```

**PostgreSQL 版本**:
```sql
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
WHERE (s.symbol ILIKE '%' || $1 || '%' OR st.name ILIKE '%' || $1 || '%')
  AND s.factor_count >= 30
ORDER BY s.symbol
LIMIT $2 OFFSET $3
```

**查询说明**:
- 使用 `stock_data_summary` 预计算表提升性能
- `LIKE '%keyword%'` 实现模糊匹配
- PostgreSQL 使用 `ILIKE` 实现大小写不敏感搜索
- 保持与现有 `/api/stocks/data-status` 端点相同的数据结构

## 前端设计

### 组件修改

**文件**: `quant-web/src/components/StockList.tsx`

### 状态管理

新增状态:
```typescript
const [searchQuery, setSearchQuery] = useState('');
const [isSearching, setIsSearching] = useState(false);
```

### 搜索逻辑

```typescript
// 防抖搜索函数
const debouncedSearch = useMemo(
  () => debounce((query: string) => {
    if (query.trim() === '') {
      // 空搜索，加载全部数据
      fetchStockDataStatus(1, pagination.pageSize);
    } else {
      // 执行搜索
      fetchSearchResults(query, 1, pagination.pageSize);
    }
  }, 300),
  [pagination.pageSize]
);

// 搜索API调用
const fetchSearchResults = async (query: string, page: number, pageSize: number) => {
  try {
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
        complete_stocks: result.total, // 搜索结果中的完整数量
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
    setIsSearching(false);
  }
};

// 搜索框onChange处理
const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const query = e.target.value;
  setSearchQuery(query);
  debouncedSearch(query);
};
```

### UI 修改

搜索框保持现有位置（Card的extra区域），修改为受控组件：

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

### 用户交互流程

1. **初始状态**: 显示全部股票（分页）
2. **用户输入**: 输入关键词，等待300ms防抖
3. **搜索中**: 显示loading图标，发起API请求
4. **显示结果**: 更新表格数据，显示匹配数量
5. **清空搜索**: 点击清空按钮，恢复显示全部股票

## 性能优化

### 数据库优化

1. **索引创建**:
```sql
CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks(name);
```

2. **使用预计算表**: `stock_data_summary` 表已包含聚合数据，避免实时计算

3. **LIMIT 限制**: 每次最多返回100条，减少数据传输量

### 前端优化

1. **防抖处理**: 300ms延迟，减少API请求频率
2. **请求取消**: 使用 AbortController 取消未完成的请求
3. **加载状态**: 显示loading图标，提升用户体验
4. **空搜索优化**: 搜索词为空时不发起搜索请求，直接加载全部数据

### 性能目标

- 数据库查询时间: < 50ms
- 防抖延迟: 300ms
- 总响应时间: < 400ms（用户感知流畅）

## 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 搜索词为空 | 显示全部股票（调用原有 `/api/stocks/data-status` 端点） |
| 无搜索结果 | 显示空状态："未找到匹配的股票" |
| 搜索请求失败 | 显示错误提示，保留上一次结果 |
| 快速连续输入 | 防抖处理，只发送最后一次请求 |
| 搜索词过短（1个字符） | 仍然搜索（可能返回较多结果） |
| 特殊字符 | URL编码处理，防止SQL注入 |
| 并发请求 | 取消上一次未完成的请求 |

## 实现步骤

### 后端实现（1.5小时）

1. 在 `quant/api/server.py` 中新增 `/api/stocks/search` 端点
2. 实现SQL查询逻辑，支持SQLite和PostgreSQL
3. 添加参数验证和错误处理
4. 测试API端点（使用curl或Postman）

### 前端实现（1小时）

1. 修改 `StockList.tsx`，添加搜索状态管理
2. 实现防抖搜索函数
3. 修改搜索框为受控组件
4. 添加loading状态显示
5. 处理空搜索和错误情况

### 测试验证（0.5小时）

1. **功能测试**:
   - 搜索股票代码（如：600519）
   - 搜索股票名称（如：茅台）
   - 搜索部分匹配（如：平安）
   - 清空搜索恢复全部数据

2. **性能测试**:
   - 测量查询响应时间
   - 验证防抖是否生效
   - 检查并发请求处理

3. **边界测试**:
   - 空搜索词
   - 无匹配结果
   - 特殊字符输入
   - 网络错误情况

## 数据库索引

如果性能不达标，创建以下索引：

```sql
-- SQLite
CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks(name);

-- PostgreSQL
CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks USING gin(name gin_trgm_ops);
```

PostgreSQL的GIN索引可以加速ILIKE查询，但需要启用pg_trgm扩展：
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## 未来扩展

本设计为基础搜索实现，未来可扩展：

1. **高级筛选**: 添加市场、数据状态、K线天数等筛选条件
2. **搜索历史**: 记录用户搜索历史，提供快速访问
3. **拼音搜索**: 支持拼音首字母搜索（如：gzmt → 贵州茅台）
4. **搜索建议**: 输入时显示自动补全建议
5. **全文搜索**: 使用全文搜索引擎（如Elasticsearch）提升性能

## 风险与注意事项

1. **SQL注入**: 使用参数化查询，避免SQL注入风险
2. **性能问题**: 如果数据量增长到10万+，考虑使用全文搜索引擎
3. **大小写敏感**: SQLite的LIKE默认大小写不敏感，PostgreSQL需使用ILIKE
4. **中文搜索**: 确保数据库字符集支持中文（UTF-8）
5. **索引维护**: 定期检查索引是否生效，必要时重建索引

## 成功标准

- ✅ 可以搜索全部5458只股票（不受分页限制）
- ✅ 支持股票代码和名称的模糊搜索
- ✅ 查询响应时间 < 50ms
- ✅ 实时搜索体验流畅（300ms防抖）
- ✅ 正确处理空搜索、无结果、错误等边界情况
- ✅ 通过功能、性能、边界测试
