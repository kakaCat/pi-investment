# 互补命令合并可行性分析

**日期**: 2026-06-03  
**问题**: 5个功能互补的命令是否可以合并？

---

## 📋 5个互补命令的合并分析

### 1. screening.sector vs stock.screen

#### 当前状态
- **screening.sector** (quant_cli): 按行业筛选，参数简单
  ```typescript
  { sector: "白酒", max_pe: 30, limit: 20 }
  ```
- **stock.screen** (stock_cli): 多条件筛选，参数复杂
  ```typescript
  { min_roe: 15, max_pe: 30, min_market_cap: 1000000000, limit: 20 }
  ```

#### 合并方案
**✅ 可以合并** - stock.screen 添加 sector 参数

```typescript
// 合并后的 stock.screen
stock.screen({
  sector: "白酒",        // 新增：行业筛选
  min_roe: 15,
  max_pe: 30,
  limit: 20
})
```

**收益**: 减少1个命令，功能更统一  
**成本**: stock_cli 需要添加行业参数  
**风险**: 低

---

### 2. screening.quality vs stock.score

#### 当前状态
- **screening.quality** (quant_cli): 行业内批量筛选
  ```typescript
  { sector: "白酒", min_score: 65, max_pe: 30, limit: 10 }
  // 返回: [{ symbol: "600519", score: 85 }, ...]
  ```
- **stock.score** (stock_cli): 单股评分
  ```typescript
  { symbol: "600519" }
  // 返回: { symbol: "600519", score: 85, details: {...} }
  ```

#### 合并方案
**❌ 不建议合并** - 功能本质不同

**理由**:
1. **输入不同**: 一个是行业，一个是股票代码
2. **输出不同**: 一个返回列表，一个返回详情
3. **使用场景不同**: 筛选 vs 分析

**建议**: 保持独立

---

### 3. watchlist.check vs watchlist.list

#### 当前状态
- **watchlist.check** (quant_cli): 单股检查
  ```typescript
  { symbol: "600519" }
  // 返回: { exists: true }
  ```
- **watchlist.list** (watchlist_cli): 列出所有
  ```typescript
  { group_id: "default" }
  // 返回: [{ symbol: "600519", ... }, ...]
  ```

#### 合并方案
**❌ 不建议合并** - 功能完全不同

**理由**:
1. 一个是验证存在性（true/false）
2. 一个是获取完整列表
3. 性能差异大（check 快，list 慢）

**建议**: 保持独立

---

### 4. data.update_klines vs data_fetch_kline

#### 当前状态
- **data.update_klines** (quant_cli): 批量更新到数据库
  ```typescript
  { symbols: "600000,000001", days: 365 }
  // 动作: 从数据源拉取 → 写入数据库
  // 返回: { updated: 2, success: true }
  ```
- **data_fetch_kline** (data/): 单次查询返回
  ```typescript
  { symbol: "600519", period: 60 }
  // 动作: 从数据库读取 → 返回数据
  // 返回: [{ date: "2024-01-01", close: 1800, ... }, ...]
  ```

#### 合并方案
**❌ 不应该合并** - 读写分离原则

**理由**:
1. **职责不同**: 写（管理）vs 读（查询）
2. **权限不同**: update 需要写权限，fetch 只需读权限
3. **性能不同**: update 慢（网络请求），fetch 快（本地查询）
4. **使用频率不同**: update 低频（每日），fetch 高频（每秒）

**建议**: 强烈建议保持独立（架构最佳实践）

---

### 5. factor.* vs factor_calculate

#### 当前状态
- **factor.fama_french_3/5, factor.barra** (quant_cli): 学术级多因子
  ```typescript
  { symbols: ["600519", "000858"], start_date: "2023-01-01" }
  // 返回: FF三因子/五因子模型、Barra风格因子
  ```
- **factor_calculate** (factor/): 日常技术+基本面因子
  ```typescript
  { symbol: "600519", factors: ["rsi", "macd", "roe"] }
  // 返回: { rsi: 65, macd: {...}, roe: 15.2 }
  ```

#### 合并方案
**❌ 不应该合并** - 因子体系完全不同

**理由**:
1. **因子类型不同**:
   - 学术因子: 多因子模型（需要多只股票）
   - 日常因子: 单股指标
2. **算法复杂度不同**:
   - FF/Barra: 需要回归分析、协方差矩阵
   - RSI/MACD: 简单指标计算
3. **使用场景不同**:
   - 学术因子: 研究、因子投资策略
   - 日常因子: 日常选股、技术分析

**建议**: 保持独立（两个不同的领域）

---

## 📊 合并建议总结

| 命令对 | 可合并性 | 建议 | 理由 |
|--------|---------|------|------|
| screening.sector + stock.screen | ✅ 可以 | 合并 | stock.screen 添加 sector 参数即可 |
| screening.quality + stock.score | ❌ 不建议 | 保持独立 | 输入输出完全不同 |
| watchlist.check + watchlist.list | ❌ 不建议 | 保持独立 | 功能性质不同 |
| data.update_klines + data_fetch_kline | ❌ 不应该 | 保持独立 | 读写分离原则 |
| factor.* + factor_calculate | ❌ 不应该 | 保持独立 | 因子体系不同 |

---

## 💡 最终推荐方案

### 方案 A: 仅合并 screening.sector ⭐⭐⭐⭐ (推荐)

**行动**:
1. 在 stock_cli 的 stock.screen 命令中添加 `sector` 参数
2. 从 quant_cli 中移除 screening.sector
3. screening.quality 保留（功能不同）

**收益**:
- 减少 1 个命令
- 筛选功能更统一
- 工作量小（1-2 小时）

**代码示例**:
```typescript
// stock-cli-tool.ts 中修改 stock.screen
"stock.screen": {
  domain: "stock",
  action: "screen",
  description: "多条件选股（支持行业、PE、ROE、市值等筛选）。",
  params: {
    sector: { type: "string" },      // 新增
    min_roe: { type: "number" },
    max_pe: { type: "number" },
    // ... 其他参数
  },
  example: { sector: "白酒", max_pe: 30, limit: 20 },
}
```

---

### 方案 B: 保持现状 ⭐⭐⭐⭐⭐ (强烈推荐)

**理由**:
1. ✅ **合并收益小** - 只能合并1个命令
2. ✅ **其他4个不应合并** - 违反设计原则
3. ✅ **现状已优化** - 代码清晰，可读性高
4. ✅ **零风险** - 无需改动

**建议**: screening.sector 虽然可以合并，但因为：
- 它是 quant_cli 中少数简单命令之一
- 合并后 stock.screen 会变得更复杂
- 用户已经习惯使用 screening.sector

**权衡后建议保持现状。**

---

## 📈 详细对比

### 合并 screening.sector 的利弊

#### 优点
- ✅ 减少1个命令（42 → 41）
- ✅ 筛选功能统一到 stock_cli
- ✅ 减少用户学习成本

#### 缺点
- ⚠️ stock.screen 参数变多（5个 → 6个）
- ⚠️ 需要修改代码和文档
- ⚠️ 需要通知用户（breaking change）
- ⚠️ 现有使用 screening.sector 的代码需要迁移

#### ROI 分析
| 项目 | 投入 | 产出 |
|------|------|------|
| 开发 | 1小时 | 减少1个命令 |
| 测试 | 1小时 | 统一筛选接口 |
| 文档 | 0.5小时 | |
| 迁移 | 未知 | |
| **总计** | 2.5小时+ | 边际收益 |

**ROI**: ⭐⭐ 较低（收益小，投入中等）

---

## 🎯 最终建议

### **方案 B: 保持现状** ⭐⭐⭐⭐⭐

**理由**:
1. 5个互补命令中，只有1个可以合并
2. 合并的ROI较低（2.5小时+ vs 减少1个命令）
3. 其他4个不应该合并（违反设计原则）
4. 当前代码已经优化完成，清晰易读
5. screening.sector 作为简单命令，易于使用

**结论**: 
- ✅ **不合并任何命令**
- ✅ **保持当前的 42 个命令**
- ✅ **互补关系是良好的架构设计**

---

## 💭 架构思考

### 互补 ≠ 重复

**互补命令的价值**:
1. **降低复杂度** - screening.sector 参数简单，stock.screen 参数复杂
2. **职责清晰** - 读写分离、批量vs单个、管理vs查询
3. **用户友好** - 简单场景用简单命令，复杂场景用复杂命令

**类比**:
- `ls` vs `find` - 都是查找文件，但用途不同
- `cat` vs `less` - 都是查看文件，但场景不同
- `cp` vs `rsync` - 都是复制文件，但能力不同

**结论**: 互补是良好的设计，不应该强求合并。

---

**完成时间**: 2026-06-03  
**推荐方案**: 方案 B（保持现状）  
**理由**: ROI低，当前架构合理
