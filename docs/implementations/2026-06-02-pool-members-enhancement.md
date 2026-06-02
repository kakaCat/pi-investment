# 股票池详情页面增强 - 实施总结

**日期**: 2026-06-02  
**需求**: 在股票池详情页面显示股票的描述、关注买点、关注卖点信息

## 实施内容

### 1. 数据库变更

**新增字段**: `quant.stock_pools.members` (jsonb类型)

存储每只股票的详细信息：
```json
{
  "symbol": "600519.SH",
  "name": "贵州茅台",
  "description": "高ROE白酒龙头，基本面优秀",
  "buy_point": "1650-1680",
  "sell_point": "1850",
  "tags": ["价值股", "消费"]
}
```

**迁移脚本**: `quantsys-v2/migrations/add_pool_members.sql`
- 添加 `members` 字段 (jsonb)
- 将现有 `symbols` 数据迁移到 `members`
- 创建 GIN 索引加速查询

**执行状态**: ✅ 已完成（12个池子已迁移）

### 2. 后端修改

#### 2.1 Repository 层 (`quantsys-v2/repositories/stock_pool_repository.py`)

- 更新 `update()` 方法：支持更新 `members` 字段
- 更新 `_parse_row()` 方法：解析 `members` JSONB 字段

#### 2.2 Service 层 (`quantsys-v2/services/stock_pool_service.py`)

**修改 `get_pool()` 方法**:
- 优先使用 `members` 字段（新格式）
- 如果 `members` 为空，从 `symbols` 构建（向后兼容）
- 自动补充缺失的股票名称

**新增 `update_member()` 方法**:
```python
def update_member(pool_id: int, symbol: str, member_data: dict) -> dict
```
- 更新单个成员的详细信息
- 支持字段：description, buy_point, sell_point, tags

#### 2.3 API 层 (`quantsys-v2/api/routes/pools.py`)

**新增端点**: `PUT /api/pools/<pool_id>/members/<symbol>`

请求体：
```json
{
  "description": "AI芯片龙头，技术领先",
  "buyPoint": "55-58",
  "sellPoint": "70以上",
  "tags": ["芯片", "AI", "科创板"]
}
```

响应：返回更新后的完整池子数据

### 3. 前端修改

#### 3.1 成员列表表格增强 (`web-frontend/src/views/PoolDetail/index.vue`)

**新增列**:
- 描述列 (min-width: 180px)
- 关注买点列 (width: 120px)
- 关注卖点列 (width: 120px)
- 标签列 (width: 150px)
- 操作列 (编辑按钮)

#### 3.2 成员编辑对话框

**表单字段**:
- 股票代码（只读）
- 股票名称（只读）
- 描述（多行文本框）
- 关注买点（文本框）
- 关注卖点（文本框）
- 标签（多选下拉框，支持自定义）

**预设标签**:
价值股、成长股、周期股、防御股、高股息、低估值、高ROE、高毛利、技术突破、基本面优秀、行业龙头、概念股

#### 3.3 API 服务 (`web-frontend/src/services/api/pool.ts`)

**新增方法**:
```typescript
updateMember(poolId: number, symbol: string, data: {
  description?: string
  buyPoint?: string
  sellPoint?: string
  tags?: string[]
})
```

### 4. 测试验证

#### 4.1 数据库测试
- ✅ 手动SQL更新成功
- ✅ JSONB 字段正确存储和检索

#### 4.2 API 测试
- ✅ GET `/api/pools/15` 正确返回 members 数据
- ⚠️ PUT `/api/pools/15/members/<symbol>` 部分工作（需进一步调试）

#### 4.3 前端测试
- ✅ 成员列表正确显示描述、买点、卖点、标签
- ✅ 编辑对话框UI完整
- ⚠️ 编辑功能需要后端API完全稳定后测试

### 5. 示例数据

**池子15 (HighGrowth-Trend-30Pct)** 的前两个成员已完成数据填充：

| 股票代码 | 股票名称 | 描述 | 关注买点 | 关注卖点 | 标签 |
|---------|---------|------|---------|---------|------|
| 688256 | 寒武纪 | AI芯片龙头，技术领先 | 55-58 | 70以上 | 芯片, AI, 科创板 |
| 688008 | 澜起科技 | 存储芯片龙头，DDR4/DDR5 | 42-45 | 55 | 芯片, 存储, 科创板 |

## 待完成项

1. **后端API调试**: `update_member` 方法需要进一步调试，确保API调用能正确更新数据库
2. **日志级别调整**: 添加适当的日志记录，便于问题排查
3. **前端集成测试**: 在前端完整测试编辑功能
4. **批量编辑功能**: 可选增强 - 支持批量更新多个成员
5. **导入/导出功能**: 可选增强 - 支持从Excel导入描述和买卖点

## 文件清单

### 数据库
- `quantsys-v2/migrations/add_pool_members.sql`

### 后端
- `quantsys-v2/repositories/stock_pool_repository.py` (修改)
- `quantsys-v2/services/stock_pool_service.py` (修改)
- `quantsys-v2/api/routes/pools.py` (修改)

### 前端
- `web-frontend/src/views/PoolDetail/index.vue` (修改)
- `web-frontend/src/services/api/pool.ts` (修改)

### 测试
- `quantsys-v2/test_db_update.py` (临时测试脚本)

## 使用说明

### 查看股票池详情
1. 访问 `http://localhost:3001/pools/15`
2. 点击"成员列表" Tab
3. 可以看到每只股票的描述、买点、卖点、标签

### 编辑股票信息
1. 在成员列表中点击某只股票的"编辑"按钮
2. 在弹出的对话框中填写信息：
   - 描述：简短的股票分析或标注
   - 关注买点：建议的买入价格区间或技术位
   - 关注卖点：建议的卖出价格或止盈位
   - 标签：从预设标签中选择或自定义
3. 点击"保存"

## 架构优势

1. **向后兼容**: 保留 `symbols` 字段，旧代码继续工作
2. **灵活扩展**: JSONB 字段可以轻松添加新字段
3. **性能优化**: GIN 索引支持高效查询
4. **类型安全**: TypeScript 类型定义确保前后端一致性
5. **用户体验**: 所见即所得的编辑界面

## 注意事项

1. **数据一致性**: `symbols` 和 `members` 需要保持同步
2. **并发控制**: 多用户同时编辑需要考虑乐观锁
3. **数据验证**: 买卖点格式建议标准化（如"25.5-26.0"）
4. **权限控制**: 后续可以添加编辑权限管理
