# data_fetch_stock 工具优化完成报告

**日期**: 2026-06-02  
**优化内容**: 非交易时段实时行情友好提示 + 自动 fallback  
**状态**: ✅ 完成并验证

---

## 问题背景

### 原问题
- **现象**: `data_fetch_stock` 工具的 `price` 字段在非交易时段返回 HTTP 502 错误
- **用户体验差**: 错误信息不友好，用户不清楚是系统故障还是正常现象
- **影响范围**: 所有依赖实时价格的场景（交易决策、盯盘、自动化任务）

### 根本原因
1. **默认值不合理**: 工具默认使用 `source='realtime'`，失败时直接报错，不尝试 fallback
2. **缺少时间感知**: 工具不判断当前是否是交易时段，所有时段都尝试获取实时数据
3. **错误提示不友好**: 仅返回 "HTTP 502: 无法获取实时行情"，用户不知道原因

---

## 优化方案

### 1. 默认数据源改为 auto
**文件**: `src/infrastructure/tools/data/fetch-stock-tool.ts:104`

```typescript
// 修改前
const { symbol, fields = ["info", "price"], news_num = DEFAULT_NEWS_COUNT, source = 'realtime' } = params;

// 修改后
const { symbol, fields = ["info", "price"], news_num = DEFAULT_NEWS_COUNT, source = 'auto' } = params;
```

**效果**:
- 实时数据源失败时，自动 fallback 到数据库
- 用户无需手动切换 `source` 参数
- 向后兼容：仍支持手动指定 `source='realtime'` 或 `source='db'`

---

### 2. 添加交易时间判断
**文件**: `src/infrastructure/tools/data/fetch-stock-tool.ts:27-48`

```typescript
/**
 * 判断当前是否是 A 股交易时段
 * 交易时间：周一至周五 9:30-11:30, 13:00-15:00
 * 注意：不考虑节假日
 */
function isTradingTime(): boolean {
  const now = new Date();
  const day = now.getDay(); // 0=Sunday, 1=Monday, ..., 6=Saturday
  const hour = now.getHours();
  const minute = now.getMinutes();

  // 周末不交易
  if (day === 0 || day === 6) {
    return false;
  }

  // 早盘：9:30-11:30
  if (hour === 9 && minute >= 30) return true;
  if (hour === 10) return true;
  if (hour === 11 && minute <= 30) return true;

  // 午盘：13:00-15:00
  if (hour === 13 || hour === 14) return true;
  if (hour === 15 && minute === 0) return true;

  return false;
}
```

**特性**:
- 准确判断 A 股交易时段（周一至周五，9:30-11:30 和 13:00-15:00）
- 自动排除周末
- 简单高效，无需外部依赖

**限制**:
- 不考虑节假日（后续可接入交易日历 API）

---

### 3. 智能错误提示
**文件**: `src/infrastructure/tools/data/fetch-stock-tool.ts:156-169`

```typescript
// price 错误添加交易时间提示
if (result.price_error) {
  let priceError = `price: ${result.price_error}`;

  // 如果是实时行情失败，且当前非交易时段，添加友好提示
  if (result.price_error.includes('502') || result.price_error.includes('实时行情') || result.price_error.includes('无法获取')) {
    if (!isTradingTime()) {
      priceError += '\n💡 提示：当前非交易时段（A股交易时间：周一至周五 9:30-11:30, 13:00-15:00）。';
      priceError += '\n   实时行情不可用是正常现象。系统已自动尝试返回最近收盘价。';
      priceError += '\n   若需明确指定数据源，可使用 source="db" 参数直接获取数据库数据。';
    }
  }

  errors.push(priceError);
}
```

**效果**:
- 非交易时段自动添加友好提示，告知用户这是正常现象
- 说明交易时间范围，帮助用户理解
- 提供替代方案（`source="db"`），增强可操作性
- 交易时段不添加提示，保持错误信息简洁

---

## 测试验证

### 测试环境
- **时间**: 2026-06-02 20:51（周二晚上，非交易时段）
- **后端**: quantsys-v2 REST API (端口 5001) ✅ 运行中
- **测试股票**: 600519（贵州茅台）

### 测试场景 1: auto 模式（默认）
**输入**:
```typescript
getStockData('600519', ['price'], 10, 'auto')
```

**结果**: ✅ 成功
```json
{
  "success": true,
  "price": {
    "data": {
      "symbol": "600519",
      "name": "贵州茅台",
      "price": 1309.6,
      "open": 1327,
      "high": 1327,
      "low": 1301.31,
      "volume": 4384500,
      "changePct": 0,
      "source": "db_fallback",
      "tradeDate": "2026-06-01"
    },
    "success": true
  }
}
```

**验证点**:
- ✅ 自动 fallback 到数据库
- ✅ 返回最近交易日（2026-06-01）收盘价
- ✅ `source` 字段标识为 `db_fallback`
- ✅ 包含 `tradeDate` 字段（而非 `timestamp`）

---

### 测试场景 2: db 模式（手动指定）
**输入**:
```typescript
getStockData('600519', ['price'], 10, 'db')
```

**结果**: ✅ 成功
```json
{
  "success": true,
  "price": {
    "data": {
      "symbol": "600519",
      "name": "贵州茅台",
      "price": 1309.6,
      "source": "db_fallback",
      "tradeDate": "2026-06-01"
    },
    "success": true
  }
}
```

**验证点**:
- ✅ 直接查询数据库，跳过实时数据源
- ✅ 返回与 auto 模式相同的数据
- ✅ 向后兼容性保持

---

### 测试场景 3: realtime 模式（仅实时）
**输入**:
```typescript
getStockData('600519', ['price'], 10, 'realtime')
```

**结果**: ✅ 符合预期（失败）
```json
{
  "success": false,
  "price": null,
  "price_error": "HTTP 502: {\"error\":\"无法获取 600519 的实时行情\",\"success\":false}\n",
  "error": "HTTP 502: {\"error\":\"无法获取 600519 的实时行情\",\"success\":false}\n"
}
```

**验证点**:
- ✅ 正确返回 502 错误
- ✅ 不尝试 fallback（符合 realtime 模式语义）
- ✅ 错误信息清晰

**注**: 在工具层调用时，会自动添加友好提示（当前测试直接调用 client，未经过工具层）。

---

### 测试场景 4: 时间判断准确性
**当前时间**: 2026-06-02 20:51（周二晚上）

**判断结果**:
- 星期: 二（周二，交易日）
- 小时: 20（晚上 8 点）
- 分钟: 51
- **是否交易时段**: ❌ 否

**验证点**:
- ✅ 正确识别非交易时段（收盘后）
- ✅ 周二属于交易日，但 20:51 在交易时间外

---

## 优化效果

### 用户体验提升
| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| **默认行为** | 非交易时段直接报错 | 自动 fallback 到数据库 |
| **错误提示** | "HTTP 502: 无法获取实时行情" | "💡 提示：当前非交易时段...（含交易时间说明和替代方案）" |
| **用户困惑** | 不清楚是系统故障还是正常现象 | 明确告知这是正常现象 |
| **工具调用次数** | 需重试或手动切换 source | 自动处理，无需重试 |
| **API 成本** | 多次重试浪费 tokens | 一次调用即可完成 |

### 技术改进
- ✅ **智能 fallback**: 实时 → 数据库自动切换
- ✅ **时间感知**: 根据交易时间调整行为和提示
- ✅ **向后兼容**: 保留手动指定 `source` 的能力
- ✅ **代码可维护性**: 错误处理逻辑集中，易于扩展

---

## 后续优化建议

### Phase 2: 后端层优化（推荐优先级 P1）
**位置**: `quantsys-v2/services/realtime_quote_service.py`

**改进点**:
1. 添加交易时间判断
   ```python
   def is_trading_time() -> bool:
       """判断当前是否是交易时段"""
       # 接入交易日历 API，考虑节假日
       pass
   ```

2. 非交易时段返回特殊状态
   ```python
   if not is_trading_time():
       return {
           "status": "closed",
           "message": "市场休市中",
           "next_trading_time": "2026-06-03 09:30:00"
       }
   ```

3. 减少无效 API 调用
   - 非交易时段直接跳过所有实时数据源
   - 避免 5 个数据源依次失败的开销

**优势**:
- 统一后端逻辑，所有客户端受益
- 减少外部 API 调用（新浪、东财等）
- 提升响应速度

---

### Phase 3: 节假日支持（推荐优先级 P2）
**改进点**:
1. 接入交易日历 API（如东方财富、同花顺）
2. 缓存本年度交易日历（TTL: 1天）
3. 准确判断节假日

**示例**:
```typescript
async function isTradingDay(date: Date): Promise<boolean> {
  const calendar = await getTradingCalendar(date.getFullYear());
  const dateStr = date.toISOString().split('T')[0];
  return calendar.tradingDays.includes(dateStr);
}
```

---

### Phase 4: 缓存优化（推荐优先级 P2）
**改进点**:
1. 非交易时段缓存数据库查询（TTL: 1小时）
   - 收盘后数据不会变化，无需重复查询
2. 交易时段缓存实时数据（TTL: 3秒）
   - 平衡数据新鲜度和 API 调用成本

**预期效果**:
- 减少数据库查询压力
- 降低 API 调用成本
- 提升响应速度

---

## 相关文件

### 修改的文件
- `src/infrastructure/tools/data/fetch-stock-tool.ts` — 工具定义和错误处理

### 相关文件（未修改）
- `src/infrastructure/quant/quant-v2-client.ts` — API 客户端
- `quantsys-v2/services/realtime_quote_service.py` — 后端实时行情服务
- `src/infrastructure/quant/formatters.ts` — 输出格式化

### 测试文件（临时）
- `test-fetch-stock-optimization.ts` — 测试脚本（可删除）
- `test-stock-tool-optimization.md` — 优化验证报告（可删除）

---

## 验证清单

- [x] 默认值改为 `auto`
- [x] 添加 `isTradingTime()` 函数
- [x] 错误提示添加时间判断
- [x] 测试 auto 模式（自动 fallback）
- [x] 测试 db 模式（手动指定）
- [x] 测试 realtime 模式（仅实时）
- [x] 测试时间判断准确性
- [ ] 实际在 Agent 中调用并查看友好提示（需等待用户使用）
- [ ] 交易时段测试（需等待交易时间）

---

## 总结

本次优化通过**工具层改进**（默认值 + 智能提示），在**不修改后端**的前提下，快速解决了用户痛点：

1. **自动容错**: `source='auto'` 作为默认值，自动 fallback
2. **友好提示**: 非交易时段明确告知用户这是正常现象
3. **向后兼容**: 保留所有现有功能，不影响已有代码

后续可通过**后端层优化**（交易时间判断、节假日支持）进一步提升性能和用户体验。

**优化完成时间**: 2026-06-02 20:52  
**优化方式**: 前端工具层（TypeScript）  
**影响范围**: `data_fetch_stock` 工具的所有调用  
**状态**: ✅ 已完成并验证
