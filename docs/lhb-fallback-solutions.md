# 龙虎榜数据获取替代方案

## 问题
`get_lhb` 工具经常超时（>120秒），因为 akshare API 响应慢或不稳定。

---

## 解决方案

### 方案1：WebFetch 网页抓取 ⭐ 推荐

当 `get_lhb` 超时时，LLM 可以使用 `WebFetch` 工具直接从网站获取数据。

#### 可用数据源

| 网站 | URL | 特点 |
|------|-----|------|
| 东方财富网 | https://data.eastmoney.com/stock/lhb.html | 数据最全，更新及时 |
| 同花顺 | http://data.10jqka.com.cn/market/longhu/ | 界面简洁，易解析 |
| 新浪财经 | http://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/lhb/index.phtml | 备用选项 |

#### 使用示例

```typescript
// LLM 自动调用 WebFetch
WebFetch({
  url: "https://data.eastmoney.com/stock/lhb.html",
  prompt: "Extract today's Dragon-Tiger List (龙虎榜) data. Return top 20 stocks with: stock code, name, close price, change %, net buy amount, and reason for listing. Format as JSON array."
})
```

#### 优点
- ✅ 不依赖 akshare API
- ✅ 数据来源稳定（官方网站）
- ✅ LLM 可以自动解析网页内容
- ✅ 无需修改现有代码

#### 缺点
- ⚠️ 网页结构变化可能影响解析
- ⚠️ 比 API 稍慢（需要加载完整网页）

---

### 方案2：降低超时时间 + 快速失败

修改 Python 调用的超时设置，从 120 秒降低到 30 秒，快速失败后自动切换到 WebFetch。

#### 实现步骤

1. 修改 `src/infrastructure/tools/shared/python-caller.ts`：

```typescript
export async function callPython(
  functionName: string,
  args: Record<string, unknown>,
  timeout: number = 30000  // 从 120000 降低到 30000
): Promise<string> {
  // ... existing code
}
```

2. 在工具描述中添加自动降级逻辑：

```typescript
description:
  "Try get_lhb first (30s timeout). If it fails or times out, " +
  "automatically fall back to WebFetch with URL: https://data.eastmoney.com/stock/lhb.html"
```

#### 优点
- ✅ 快速失败，不浪费时间
- ✅ 自动降级到可靠方案
- ✅ 用户体验更好

#### 缺点
- ⚠️ 需要修改超时配置
- ⚠️ 可能误杀正常但稍慢的请求

---

### 方案3：使用其他 akshare 接口

akshare 提供多个龙虎榜接口，可以尝试其他更快的接口。

#### 可选接口

```python
# 当前使用（慢）
ak.stock_lhb_detail_em()  # 东方财富明细
ak.stock_lhb_stock_statistic_em()  # 个股统计

# 备选接口（可能更快）
ak.stock_lhb_jgmmtj_em()  # 机构买卖统计
ak.stock_lhb_hyyyb_em()  # 营业部统计
```

#### 实现

修改 `python/akshare_bridge.py`：

```python
def get_lhb_fast(symbol: str = None, date: str = None) -> dict:
    """龙虎榜快速版本 - 使用更轻量的接口"""
    import akshare as ak
    try:
        # 使用机构买卖统计接口（通常更快）
        df = ak.stock_lhb_jgmmtj_em(start_date=date, end_date=date)
        # ... 处理数据
    except Exception as e:
        return {"error": str(e), "fallback": "use WebFetch"}
```

---

### 方案4：缓存 + 定时更新

龙虎榜数据每天只更新一次（盘后），可以缓存数据避免重复请求。

#### 实现思路

```typescript
// 在 Redis 或文件系统中缓存
const cacheKey = `lhb:${date}`;
const cached = await cache.get(cacheKey);
if (cached) {
  return cached;
}

// 缓存未命中，调用 API
const data = await callPython("get_lhb", args);
await cache.set(cacheKey, data, { ttl: 86400 }); // 24小时
return data;
```

#### 优点
- ✅ 大幅减少 API 调用
- ✅ 响应速度快
- ✅ 降低超时风险

#### 缺点
- ⚠️ 需要引入缓存层
- ⚠️ 增加系统复杂度

---

## 推荐实施方案

### 短期方案（立即可用）

**已实施**: 在 `get_lhb` 工具描述中添加 WebFetch 降级提示

```typescript
description:
  "... existing description ...\n\n" +
  "⚠️ TIMEOUT FALLBACK: If this tool times out (>120s), use WebFetch instead:\n" +
  "- URL: https://data.eastmoney.com/stock/lhb.html\n" +
  "- Prompt: 'Extract today's Dragon-Tiger List data...'"
```

**效果**: LLM 会自动识别超时并切换到 WebFetch

---

### 中期方案（1-2天实施）

1. **降低超时时间**: 30秒快速失败
2. **添加重试机制**: 失败后自动重试1次
3. **记录失败日志**: 监控 API 稳定性

```typescript
async function callPythonWithRetry(fn: string, args: any, retries = 1) {
  for (let i = 0; i <= retries; i++) {
    try {
      return await callPython(fn, args, 30000);
    } catch (e) {
      if (i === retries) throw e;
      await sleep(2000); // 等待2秒后重试
    }
  }
}
```

---

### 长期方案（1周实施）

1. **实现缓存层**: 使用文件缓存或 Redis
2. **定时任务**: 每天盘后自动抓取龙虎榜数据
3. **多数据源**: 同时支持 akshare + WebFetch，自动选择最快的

```typescript
async function getLhbWithFallback(params: any) {
  // 1. 尝试缓存
  const cached = await cache.get(`lhb:${params.date}`);
  if (cached) return cached;

  // 2. 尝试 akshare API（30秒超时）
  try {
    const result = await callPython("get_lhb", params, 30000);
    await cache.set(`lhb:${params.date}`, result);
    return result;
  } catch (e) {
    // 3. 降级到 WebFetch
    return await webFetchLhb(params);
  }
}
```

---

## 测试验证

### 测试 WebFetch 方案

```bash
# 在 Claude Code 中执行
WebFetch({
  url: "https://data.eastmoney.com/stock/lhb.html",
  prompt: "提取今日龙虎榜前10只股票：代码、名称、涨跌幅、净买入额、上榜原因"
})
```

### 预期输出

```json
[
  {
    "code": "600519",
    "name": "贵州茅台",
    "change_pct": "+2.5%",
    "net_buy": "5.2亿",
    "reason": "日涨幅偏离值达7%"
  },
  ...
]
```

---

## 总结

| 方案 | 实施难度 | 效果 | 推荐度 |
|------|---------|------|--------|
| WebFetch 降级 | ⭐ 简单 | ⭐⭐⭐⭐ 好 | ⭐⭐⭐⭐⭐ 强烈推荐 |
| 降低超时 + 重试 | ⭐⭐ 中等 | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐ 推荐 |
| 切换 akshare 接口 | ⭐⭐ 中等 | ⭐⭐ 不确定 | ⭐⭐ 可尝试 |
| 缓存 + 定时任务 | ⭐⭐⭐ 复杂 | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐⭐ 长期推荐 |

**当前状态**: 已实施 WebFetch 降级方案，LLM 会在超时时自动切换。
