---
name: add-holding
description: 录入或更新持仓信息（代码+数量+均价，加仓自动计算加权均价）
---

# 录入持仓 (Add Holding)

## 允许的工具
- manage_portfolio()
- get_stock_info()
- get_stock_price()
- get_financial_data()
- get_financial_statements()
- analyze_technical()
- get_valuation()
- get_pe_percentile()
- get_quality_score()
- clarify()

## 触发条件

用户想要录入、添加或更新持仓时使用此技能。

关键词：录入持仓、添加持仓、/add-holding、我买了、建仓、加仓

## 工作流程

1. **询问持仓信息** - 向用户逐步询问以下信息：
   - 股票代码（如 600519、00700）
   - 持仓数量（股数）
   - 持仓均价（买入成本价，元）
   - 市场类型：A股(A) 或 港股(HK)，默认 A
   - 股票名称（可选，如不填则留空）
   - 备注（可选，如"第一批建仓"）

2. **录入持仓** - 调用 `manage_portfolio(action="add", symbol=..., quantity=..., avg_cost=..., market=..., name=..., notes=...)`

3. **确认结果** - 展示录入结果，如果是加仓则显示新的加权均价和总持股数

4. **询问是否继续** - 问用户是否还有其他持仓需要录入

## 注意事项

- 如果该股票已有持仓，系统会自动计算**加权均价**（不是简单平均）
- 港股代码通常是5位数字，如 00700（腾讯），输入时可省略前导零
- 均价是指所有买入批次的加权平均成本价
- 录入后可用 `/portfolio` 命令查看完整持仓和盈亏

## 示例对话

```
用户: /add-holding
助手: 请告诉我持仓信息：
  - 股票代码？
用户: 600519
助手: 贵州茅台，持仓数量？
用户: 100
助手: 买入均价（元）？
用户: 1450
助手: 市场类型 A股/港股？(默认A)
用户: A
→ 调用 manage_portfolio(action="add", symbol="600519", quantity=100, avg_cost=1450, market="A", name="贵州茅台")
→ 返回: 600519 已录入持仓，100股，均价1450.00元
```
