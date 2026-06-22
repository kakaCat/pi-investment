# 财务数据工具改进：添加数据源信息

**日期**: 2026-06-08  
**改进**: 在 `data_fetch_financial` 工具返回中添加数据源信息  
**状态**: ✅ 已完成

## 问题背景

用户询问：`data_fetch_financial` 获取的数据是从哪个数据源返回的，是否告诉了 LLM？

**现状分析**：
- 后端 API 返回包含 `source`、`cached`、`timestamp` 字段
- TypeScript 客户端获取了这些字段但没有传递给格式化器
- 格式化输出中没有显示数据源信息
- **结论**: LLM 无法知道数据来自哪个数据源

## 改进方案

### 1. 扩展 `FinancialData` 类型定义

**文件**: `src/infrastructure/adapters/quant/types.ts`

```typescript
export interface FinancialData {
  success: boolean;
  symbol: string;
  name: string;
  report_date: string;
  source?: string;        // 数据源（如 eastmoney_direct, sina, akshare）
  cached?: boolean;       // 是否来自缓存
  timestamp?: string;     // 数据时间戳
  // ... 其他字段
}
```

### 2. 修改 `getFinancials` 函数

**文件**: `src/infrastructure/adapters/quant/quant-v2-client.ts`

```typescript
const financialData = response.data.data;
const dataSource = response.data.source;
const dataCached = response.data.cached;
const timestamp = response.data.timestamp;

const result: FinancialData = {
  success: true,
  symbol: symbol,
  name: '',
  report_date: '',
  source: dataSource,      // ✅ 添加数据源
  cached: dataCached,      // ✅ 添加缓存状态
  timestamp: timestamp,    // ✅ 添加时间戳
};
```

### 3. 增强 `formatFinancialData` 函数

**文件**: `src/infrastructure/adapters/quant/formatters.ts`

```typescript
export function formatFinancialData(data: FinancialData): string {
  const lines: string[] = [];

  // 数据源映射
  const sourceNames: Record<string, string> = {
    'eastmoney_direct': '东方财富',
    'sina': '新浪财经',
    'sina_web': '新浪财经网页版',
    'tencent': '腾讯财经',
    'akshare': 'AkShare',
    'database': '数据库',
  };

  // 显示数据源信息
  if (data.source) {
    const sourceName = sourceNames[data.source] || data.source;
    const cacheStatus = data.cached ? '（缓存）' : '（实时）';
    lines.push(`【财务数据】（数据源: ${sourceName}${cacheStatus}）`);
  } else {
    lines.push('【财务数据】');
  }

  lines.push(`股票代码: ${data.symbol}`);
  lines.push(`股票名称: ${data.name}`);
  lines.push(`报告期: ${data.report_date}`);
  lines.push('');
  
  // ... 其他格式化逻辑
}
```

## 改进效果

### 修改前
```
股票代码: 600519
股票名称: 贵州茅台
报告期: 2026-03-31

【利润表】
  营业收入: 547.03 亿元
  ...
```

### 修改后
```
【财务数据】（数据源: 东方财富（实时））
股票代码: 600519
股票名称: 贵州茅台
报告期: 2026-03-31

【利润表】
  营业收入: 547.03 亿元
  ...
```

## 支持的数据源

| 数据源 ID | 显示名称 | 说明 |
|-----------|---------|------|
| `eastmoney_direct` | 东方财富 | 东方财富直接 API |
| `sina` | 新浪财经 | 新浪财经 API |
| `sina_web` | 新浪财经网页版 | 新浪财经网页抓取 |
| `tencent` | 腾讯财经 | 腾讯财经 API |
| `akshare` | AkShare | AkShare 财经数据 |
| `database` | 数据库 | 本地数据库 fallback |

## 缓存状态标识

- **（实时）**: 数据直接从数据源获取，未使用缓存
- **（缓存）**: 数据来自缓存，未请求外部 API

## LLM 获得的信息

现在 LLM 可以通过工具返回的文本知道：

1. **数据源**: 数据来自哪个提供商（东方财富、新浪、AkShare 等）
2. **缓存状态**: 数据是实时获取还是来自缓存
3. **数据新鲜度**: 通过数据源和缓存状态判断数据可信度

## 应用场景

### 场景 1: 数据源透明度
```
用户: 查询贵州茅台的财务数据
LLM: 根据东方财富（实时）的数据，贵州茅台 2026Q1 营业收入 547.03 亿元...
```

### 场景 2: 数据源失败诊断
```
如果东方财富失败，自动 fallback 到新浪财经：
【财务数据】（数据源: 新浪财经（实时））
```

### 场景 3: 缓存命中提示
```
【财务数据】（数据源: 东方财富（缓存））
```
LLM 可以告知用户数据来自缓存，可能不是最新的。

## 相关工具

这个改进也适用于其他使用 `formatFinancialData` 的工具：
- ✅ `data_fetch_financial` - 主要受益工具
- ✅ 其他调用 `getFinancials()` 的内部函数

## 后续优化建议

1. **时间戳显示**: 考虑在输出中显示数据更新时间
   ```
   【财务数据】（数据源: 东方财富（实时），更新时间: 2026-06-08 11:20）
   ```

2. **数据源健康度**: 添加数据源成功率指标
   ```
   【财务数据】（数据源: 东方财富（实时，成功率 98.5%））
   ```

3. **多数据源对比**: 当多个数据源数据不一致时，提示 LLM
   ```
   ⚠️ 注意：东方财富和新浪财经的营业收入数据存在 2% 差异
   ```

4. **统一所有工具**: 将数据源信息添加到所有数据获取工具
   - `data_fetch_stock` (已实现)
   - `data_fetch_kline`
   - `data_fetch_dividend`
   - 等等

## 技术细节

### 类型安全
- TypeScript 类型定义确保 `source`、`cached`、`timestamp` 字段是可选的
- 向后兼容：如果后端不返回这些字段，工具仍然正常工作

### 错误处理
- 如果 `source` 为空，显示通用标题 `【财务数据】`
- 未知数据源直接显示原始 ID（如 `new_provider`）

### 性能影响
- ✅ 无性能影响：只是格式化输出增加了一行文本
- ✅ 不增加 API 调用：数据源信息已在原有响应中

## 测试验证

### 测试用例 1: 实时数据
```bash
curl "http://127.0.0.1:5001/api/v2/stock/600519/financials?statement_type=income&periods=1&source=fresh"
```
**预期输出**: `【财务数据】（数据源: 东方财富（实时））`

### 测试用例 2: 缓存数据
```bash
curl "http://127.0.0.1:5001/api/v2/stock/600519/financials?statement_type=income&periods=1&source=auto"
# 第二次请求会命中缓存
```
**预期输出**: `【财务数据】（数据源: 东方财富（缓存））`

### 测试用例 3: TypeScript 工具
```typescript
const result = await dataFetchFinancialTool.execute('test-1', {
  symbol: '600519',
  dataType: 'statements',
  reportType: 'income',
  periods: 1
});
```
**预期**: 返回文本包含数据源信息

## 总结

通过这次改进，LLM 现在可以清楚地知道财务数据来自哪个数据源（东方财富、新浪、AkShare 等）以及数据是实时获取还是来自缓存。这提高了 Agent 回答的透明度和可信度。

**改进前**: ❌ LLM 不知道数据来源  
**改进后**: ✅ LLM 明确知道数据源和缓存状态
