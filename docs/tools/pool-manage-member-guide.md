# Agent 工具 - 股票池成员管理功能

**更新日期**: 2026-06-02  
**工具名称**: `pool_manage`

## 新增功能

### 1. 查看成员详细信息 (`get_member`)

**功能**: 查看股票池中单只股票的详细信息（描述、买点、卖点、标签）

**使用示例**:
```typescript
pool_manage({
  action: "get_member",
  pool_id: 15,
  symbol: "688256"
})
```

**返回示例**:
```
📋 成员详情: 688256 寒武纪
  描述: AI芯片龙头，技术领先
  关注买点: 55-58
  关注卖点: 70以上
  标签: 芯片, AI, 科创板
```

### 2. 更新成员信息 (`update_member`)

**功能**: 更新股票池中单只股票的描述、买点、卖点、标签

**使用示例**:
```typescript
pool_manage({
  action: "update_member",
  pool_id: 15,
  symbol: "688256",
  member_description: "AI芯片龙头，技术领先",
  buy_point: "55-58",
  sell_point: "70以上",
  tags: ["芯片", "AI", "科创板"]
})
```

**返回示例**:
```
✅ 成员信息已更新: 688256 寒武纪
  描述: AI芯片龙头，技术领先
  买点: 55-58 | 卖点: 70以上
  标签: 芯片, AI, 科创板
```

### 3. 查看池子详情增强 (`get`)

**功能**: 查看股票池详情时，自动显示每个成员的描述、买点、卖点、标签

**使用示例**:
```typescript
pool_manage({
  action: "get",
  pool_id: 15
})
```

**返回示例**:
```
📊 池子详情: HighGrowth-Trend-30Pct (static)
  成员 (8只):
    • 688256 寒武纪
      描述: AI芯片龙头，技术领先
      买点: 55-58 | 卖点: 70以上
      标签: 芯片, AI, 科创板

    • 688008 澜起科技
      描述: 存储芯片龙头，DDR4/DDR5
      买点: 42-45 | 卖点: 55
      标签: 芯片, 存储, 科创板

    • 688981 中芯国际
    • 688041 海光信息
    ...
```

## 参数说明

### 新增参数

| 参数 | 类型 | 说明 | 适用操作 |
|------|------|------|---------|
| `symbol` | string | 股票代码 | update_member, get_member |
| `member_description` | string | 股票描述 | update_member |
| `buy_point` | string | 关注买点 | update_member |
| `sell_point` | string | 关注卖点 | update_member |
| `tags` | string[] | 标签列表 | update_member |

### 数据格式建议

#### 描述 (member_description)
- 简洁明了，50字以内
- 可以包含：行业地位、业务特点、投资逻辑
- 示例：
  - "AI芯片龙头，技术领先"
  - "高ROE白酒龙头，基本面优秀"
  - "新能源汽车电池龙头，产能快速扩张"

#### 买点 (buy_point)
- 格式1：价格区间 "25.5-26.0"
- 格式2：技术位 "突破30日均线"
- 格式3：条件描述 "回调至布林带下轨"
- 示例：
  - "55-58"
  - "突破前高68"
  - "回调至60日均线"

#### 卖点 (sell_point)
- 格式1：目标价 "32.0"
- 格式2：止损价 "跌破支撑位28.5"
- 格式3：比例 "+20%"
- 示例：
  - "70以上"
  - "跌破50日均线"
  - "盈利15%止盈"

#### 标签 (tags)
- 推荐标签：
  - **类型**: 价值股、成长股、周期股、防御股
  - **特征**: 高股息、低估值、高ROE、高毛利
  - **行业**: 芯片、新能源、医药、消费、金融
  - **阶段**: 技术突破、基本面改善、业绩拐点
  - **风险**: 高波动、政策风险、竞争加剧

## 完整使用流程示例

### 场景：构建高成长科技股池子并添加投资备注

```typescript
// 1. 创建股票池
pool_manage({
  action: "create",
  name: "高成长科技股",
  pool_type: "static",
  symbols: ["688256", "688008", "688981"],
  description: "聚焦半导体和AI领域的高成长标的"
})

// 2. 添加第一只股票的详细信息
pool_manage({
  action: "update_member",
  pool_id: 15,
  symbol: "688256",
  member_description: "AI芯片龙头，寒武纪专注于AI芯片设计，技术领先",
  buy_point: "55-58",
  sell_point: "70以上",
  tags: ["芯片", "AI", "科创板", "高成长"]
})

// 3. 添加第二只股票的详细信息
pool_manage({
  action: "update_member",
  pool_id: 15,
  symbol: "688008",
  member_description: "存储芯片龙头，DDR4/DDR5市场份额领先",
  buy_point: "42-45",
  sell_point: "55",
  tags: ["芯片", "存储", "科创板"]
})

// 4. 查看整个池子的详细信息
pool_manage({
  action: "get",
  pool_id: 15
})

// 5. 查看单只股票的详细信息
pool_manage({
  action: "get_member",
  pool_id: 15,
  symbol: "688256"
})
```

## 与前端页面的集成

Agent 工具的数据与前端页面完全同步：

1. **通过 Agent 更新的数据**会立即在前端页面 `http://localhost:3001/pools/15` 显示
2. **通过前端页面编辑的数据**也可以通过 Agent 查看
3. 两者共享同一个后端 API 和数据库

## 常见用法

### 快速查看池子概况
```typescript
pool_manage({ action: "list" })
```

### 查看某个池子的详细成员信息
```typescript
pool_manage({ action: "get", pool_id: 15 })
```

### 批量更新多个成员（循环调用）
```typescript
// 为池子中的每只股票添加信息
const stocks = [
  { symbol: "688256", desc: "AI芯片龙头", buy: "55-58", sell: "70" },
  { symbol: "688008", desc: "存储芯片龙头", buy: "42-45", sell: "55" },
];

for (const stock of stocks) {
  pool_manage({
    action: "update_member",
    pool_id: 15,
    symbol: stock.symbol,
    member_description: stock.desc,
    buy_point: stock.buy,
    sell_point: stock.sell
  });
}
```

### 只更新部分字段
```typescript
// 只更新买点，不改其他字段
pool_manage({
  action: "update_member",
  pool_id: 15,
  symbol: "688256",
  buy_point: "60-62"  // 只传要更新的字段
})
```

## 技术实现

### 后端 API
- **端点**: `PUT /api/pools/<pool_id>/members/<symbol>`
- **实现**: `quantsys-v2/api/routes/pools.py`
- **服务**: `quantsys-v2/services/stock_pool_service.py`

### TypeScript 客户端
- **函数**: `updatePoolMember(poolId, symbol, data)`
- **文件**: `src/infrastructure/quant/quant-v2-client.ts`

### Agent 工具
- **工具**: `pool_manage`
- **文件**: `src/infrastructure/tools/pool/pool-manage-tool.ts`
- **新增操作**: `update_member`, `get_member`

## 注意事项

1. **symbol 必须存在**: 只能更新已在池子中的股票
2. **字段可选**: 所有字段都是可选的，只传要更新的字段即可
3. **标签数组**: tags 必须是字符串数组，不是逗号分隔的字符串
4. **数据同步**: 更新后立即生效，前端和 Agent 都能看到最新数据

## 相关文档

- 实施总结: `docs/implementations/2026-06-02-pool-members-enhancement.md`
- 前端页面: `web-frontend/src/views/PoolDetail/index.vue`
- API 文档: `docs/api/pools-api.md` (待创建)
