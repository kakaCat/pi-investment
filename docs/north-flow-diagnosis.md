# 北向资金工具诊断报告

**日期**: 2026-05-16  
**工具**: `get_north_flow`  
**状态**: ❌ 不可用（数据源失效）

---

## 问题描述

用户报告 `get_north_flow` 工具不好使。经系统化调试，确认为**数据源问题**，非代码 bug。

---

## 根本原因

### 1. 历史数据接口失效

**接口**: `akshare.stock_hsgt_hist_em(symbol="北向资金")`

**问题**:
- 最后有效数据: **2024-08-16**
- 从 **2024-08-19** 开始，所有关键字段返回 `NaN`:
  - `当日成交净买额`: NaN
  - `买入成交额`: NaN
  - `卖出成交额`: NaN
- 已持续 **638 天**（近 2 年）

**测试结果**:
```python
df = ak.stock_hsgt_hist_em(symbol='北向资金')
# 最近10条数据（2026-05-11 到 2026-05-15）全是 NaN
```

### 2. 实时数据接口无效

**接口**: `akshare.stock_hsgt_fund_flow_summary_em()`

**问题**:
- 北向资金的 `成交净买额` 和 `资金净流入` 字段全为 **0.0**
- 无法作为替代数据源

**测试结果**:
```python
df = ak.stock_hsgt_fund_flow_summary_em()
north = df[df['资金方向'] == '北向']
# 成交净买额: 0.0
# 资金净流入: 0.0
```

### 3. 分钟级数据接口无效

**接口**: `akshare.stock_hsgt_fund_min_em()`

**问题**:
- 所有时间点的数据都是 **0.0**
- 无法通过累加计算当日净流入

### 4. 其他接口均不可用

测试了以下接口，均失败:
- `stock_hsgt_stock_statistics_em`: 返回空数据
- `stock_hsgt_board_rank_em`: 报错 `'NoneType' object is not subscriptable`
- `stock_hsgt_individual_em`: 报错 `'NoneType' object is not subscriptable`

---

## 对比：南向资金正常

**接口**: `akshare.stock_hsgt_hist_em(symbol="南向资金")`

**状态**: ✅ 正常工作

**数据**:
- 最新数据: 2026-05-15
- 所有字段完整（`当日成交净买额`、`买入成交额`、`卖出成交额`）
- 无 NaN 值

**结论**: 同样的底层接口，南向资金数据正常，说明是**东方财富网北向资金数据源的特定问题**。

---

## 已实施的修复

### 1. Python 函数修复

**文件**: `python/akshare_bridge.py`

**改动**:
- 添加数据有效性检查
- 检查最新数据的时效性（超过 30 天视为过期）
- 返回明确的错误信息，包含:
  - 错误类型（数据过期/数据源失效）
  - 详细说明（最后有效日期、过期天数）
  - 空数据数组

**返回示例**:
```json
{
  "error": "北向资金数据过期",
  "detail": "最新数据停留在 2024-08-16（638 天前），数据源已失效",
  "last_valid_date": "2024-08-16",
  "data": []
}
```

### 2. TypeScript 工具描述更新

**文件**: `src/infrastructure/tools/invest/market-tools.ts`

**改动**:
- 在工具描述中添加 ⚠️ 警告
- 明确说明数据源问题和不可用状态
- 建议使用替代工具

### 3. 文档更新

**文件**: `CLAUDE.md`

**改动**:
- 添加"数据工具状态"章节
- 列出不可用工具及原因
- 提供替代方案

---

## 替代方案

由于北向资金数据不可用，建议使用以下工具分析市场情绪：

### 推荐替代工具（已验证可用 ✅）

1. **`get_market_overview`** - 市场概览 ✅
   - 上证/深证/创业板指数
   - 涨跌家数
   - 成交额
   - **状态**: 正常工作

2. **`get_sector_fund_flow`** - 行业资金流向 ✅
   - 各行业净流入/流出
   - 识别资金轮动方向
   - **状态**: 正常工作，返回 20 个行业数据

3. **`get_market_margin`** - 融资融券 ✅
   - 市场杠杆水平
   - 风险情绪指标
   - **状态**: 正常工作，返回 10 天历史数据

4. **`get_hk_south_flow`** - 南向资金（港股）✅
   - 内地资金流向港股趋势
   - 可作为资金流向的参考
   - **状态**: 正常工作，耗时约 26 秒

### 使用建议

**分析市场情绪时的组合策略**：

```
市场整体情绪 = get_market_overview() 
              + get_sector_fund_flow()  # 看资金流向哪些行业
              + get_market_margin()      # 看杠杆水平

资金流向参考 = get_hk_south_flow()     # 内地资金流向港股（间接反映风险偏好）
```

**注意**：虽然无法直接获取北向资金（外资流入A股），但通过上述工具组合，仍可全面评估市场情绪和资金动向。

---

## 技术细节

### 调试过程

遵循 `systematic-debugging` skill 的四阶段流程：

**Phase 1: Root Cause Investigation**
- 读取工具实现代码
- 测试 Python 函数直接调用
- 测试 AkShare 原始接口
- 对比南向资金接口

**Phase 2: Pattern Analysis**
- 分析 NaN 数据的起始时间
- 统计有效数据的范围
- 对比南北向数据差异

**Phase 3: Hypothesis and Testing**
- 假设：数据源问题（非代码问题）
- 测试：尝试所有可能的替代接口
- 验证：确认无可用替代方案

**Phase 4: Implementation**
- 修改函数返回明确错误
- 更新工具描述
- 更新文档

### 关键发现

1. **数据源层面的问题**，无法通过代码修复
2. **南向资金正常**，说明不是 AkShare 整体问题
3. **所有北向资金相关接口均失效**，无替代方案
4. **问题已持续近 2 年**，短期内不太可能恢复

---

## 建议

### 短期

1. ✅ 使用替代工具分析市场情绪
2. ✅ 在分析报告中说明北向资金数据不可用
3. ✅ 工具返回明确错误，避免误导用户

### 长期

1. 监控东方财富网接口恢复情况
2. 考虑寻找其他北向资金数据源（如 Tushare、Wind）
3. 如果接口恢复，移除错误检查逻辑

---

## 相关文件

- `python/akshare_bridge.py` - Python 数据层
- `src/infrastructure/tools/invest/market-tools.ts` - TypeScript 工具定义
- `CLAUDE.md` - 项目配置文档
- `docs/north-flow-diagnosis.md` - 本诊断报告
