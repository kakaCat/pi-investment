# 混合路线量化策略 — 设计文档

- **日期**: 2026-05-26
- **版本**: v1.0
- **状态**: 设计完成，待实现

---

## 1. 目标与约束

| 维度 | 设定 |
|------|------|
| 市场 | A 股 + 港股 |
| 策略路径 | 行业轮动 + 多因子精选 + ML 置信过滤（三层混合） |
| 资金规模 | < 50 万 RMB |
| 调仓频率 | 周度信号检查，月度再平衡 |
| 风险偏好 | 稳健，追求超额 + 低回撤 |
| 基准 | 沪深300 × 50% + 恒生指数 × 50% |

---

## 2. 整体架构

```
全市场(4000+只)
    │
    ▼ 第一层：行业轮动（L2因子工厂 + quant_cli market.sectors/sector_flow）
3个强势行业(300-500只)
    │
    ▼ 第二层：多因子精选（L2 factor_calculate + financial.indicators）
每个行业 5只(15只候选)
    │
    ▼ 第三层：ML置信过滤（L3 model_predict，XGBoost + LightGBM）
最终持仓 6-12只
    │
    ▼ 等权配置 + 三层风控（L4 portfolio_rebalance）
每周信号检查 → 月度再平衡
    │
    ▼ 执行（L5 trade_algo_execute TWAP/VWAP）
    ▼ 监控（L6 monitor_alert + 飞书通知）
```

---

## 3. 第一层：行业轮动

### 3.1 A股（28个申万一级行业）

| 因子 | 权重 | 数据来源 |
|------|------|---------|
| 行业动量（4w/8w/12w多周期等权） | 40% | `quant_cli market.sectors` |
| 行业资金流向（周度累计标准化） | 35% | `quant_cli market.sector_flow` |
| 相对强弱（vs 沪深300，4周滚动） | 25% | `quant_cli market.index_history` |

- 综合得分 = 动量×0.4 + 资金流×0.35 + 相对强弱×0.25
- 取前 3 行业
- 防过拟合：行业连续 4 周排名第一 → 权重打 8 折

### 3.2 港股（12个恒生一级行业）

| 因子 | 权重 | 数据来源 |
|------|------|---------|
| 南向资金净流入 | 40% | `quant_cli hk.south_flow` |
| 行业动量（4w/8w/12w） | 35% | `quant_cli hk.market_overview` |
| 相对强弱（vs 恒生指数） | 25% | `quant_cli hk.market_overview` |

### 3.3 调仓规则

- 每周五 15:30 评分
- 行业排名变化 → 触发后续精选流程
- 行业排名不变 → 仅检查个股风控信号

---

## 4. 第二层：多因子精选

### 4.1 因子池（A股 — 4大类）

| 类别 | 权重 | 因子 |
|------|------|------|
| 价值 | 20% | PE分位数、PB分位数、股息率 |
| 质量 | 30% | ROE、毛利率、经营CF/净利润、负债率 |
| 动量 | 25% | 1月/3月/6月收益率、RSI-14 |
| 技术 | 25% | 成交量比、波动率（低波加分）、MACD |

### 4.2 IC动态权重

- 每季度跑 `quant_cli factor.analyze`（过去6个月数据）
- IC绝对值高 → 权重上调 ±5%
- IC < 0.02 → 剔除出池
- IC < 0 → 负向因子反转使用

### 4.3 计算流程

```
行业内股票池（排除 ST、次新股<60天、停牌股）
  → 逐只计算 4类因子值
  → 行业内 Z-score 标准化
  → 综合得分 = Σ(子因子×IC权重)
  → 每行业取前 5只
```

### 4.4 港股差异

| 类别 | 权重 | 说明 |
|------|------|------|
| 价值 | 25% | 与A股相同逻辑 |
| 动量 | 30% | 提升权重（财务因子可得性有限） |
| 质量 | 15% | 降权，仅用 `hk.hk_financials` 可得指标 |
| 技术 | 30% | `hk.technical` 提供完整技术指标 |

---

## 5. 第三层：ML置信过滤

### 5.1 角色定位

因子层选出 15 只候选，ML 逐只判定：buy → 通过，非 buy → 剔除。**只做否决，不做选股。**

### 5.2 模型配置

| 项 | A股 | 港股 |
|---|-----|------|
| 模型 | XGBoost(主) + LightGBM(备) | XGBoost(仅主模型) |
| 特征 | 62因子全量 | 技术因子+南向资金+基础财务 |
| 训练数据 | 过去360天日线 | 过去360天日线 |
| 预测目标 | 未来10交易日涨跌>3% | 未来10交易日涨跌>3% |
| 重训练频率 | 每30天 | 每30天 |
| 置信度阈值 | ≥ 0.65 | ≥ 0.65 |

### 5.3 双模型融合规则（A股）

| XGBoost | LightGBM | 判定 |
|---------|----------|------|
| buy | buy | buy ✓ (置信度取均值) |
| buy | hold | buy ✓ (仓位打8折) |
| hold | buy | buy ✓ (仓位打8折) |
| buy | sell | hold ✗ (冲突剔除) |
| hold/sell | hold/sell | hold/sell ✗ |

### 5.4 防过拟合

- 每30天重训练 → `model_train`
- 漂移监控 → `model_monitor`，漂移>0.3立即重训
- 模型通过率<40%（大面积否决）→ 暂停ML层，仅用因子层
- 两模型预测方向冲突 → 保守处理（剔除或降低仓位）

---

## 6. 第四层：组合构建与风控

### 6.1 资金分配

- A股:港股 = 70%:30%（港股设上限，控制汇率+流动性风险）
- 行业间等权，行业内个股等权
- 单票上限 15%

### 6.2 风控规则

| 层级 | 规则 | 动作 |
|------|------|------|
| **个股** | 止损 8% | 无条件卖出 |
| | 单日跌 > 5% | 减半仓 + `send_risk_warning` |
| | ROE连续两季<5% | 剔除出池 |
| **组合** | 最大回撤 > 12% | 仓位降至 50% |
| | 最大回撤 > 20% | 清仓，人工复盘 |
| | 周波动率 > 年化25% | 仓位降至 70% |
| **市场** | 沪深300 跌破60日均线 | A股仓位降至 50% |
| | 恒生跌破60日均线 | 港股仓位降至 50% |
| | `market.sentiment` 极端恐惧 | 仓位降至 30% |

### 6.3 分批建仓

新调入股票：
- 第1批（50%目标仓位）：周一 TWAP
- 第2批（50%目标仓位）：观察3天后周四补足

---

## 7. 第五层：执行引擎

### 7.1 执行方式

- 买入：TWAP（`trade_algo_execute`，30分钟窗口）
- 卖出：VWAP（`trade_algo_execute`，30分钟窗口）

### 7.2 调仓流程

```
1. 生成目标持仓表（股票+目标股数）
2. 对比当前持仓 → 计算买卖股数差
3. 先卖后买（释放资金）
4. 卖出：trade_manage_orders place（限价单，30分钟有效）
5. 买入：trade_algo_execute TWAP
6. 30分钟后 → trade_manage_orders check
7. 未成交部分 → 下个周期继续
```

---

## 8. 第六层：监控告警

### 8.1 盯盘节奏（工作日 9:30-15:00，每30分钟）

| 检查项 | 工具 | 动作 |
|--------|------|------|
| 个股止损触发 | `trade_manage_orders check` | 自动止损 |
| 个股单日跌>5% | `data_fetch_stock price` | `send_risk_warning` 飞书 |
| 组合回撤 | `portfolio_rebalance get_with_pnl` | `send_risk_warning` |
| 市场极端 | `quant_cli market.sentiment` | `send_risk_warning` |

### 8.2 每日收盘（15:30）

1. 更新持仓盈亏 → `portfolio_rebalance get_with_pnl`
2. 记录当日成交 → trades.json
3. 周五额外：检查 ML 漂移 → `model_monitor`

### 8.3 告警路由

- `monitor_alert trade_signal` → 飞书交易信号卡片
- `monitor_alert risk_warning` → 飞书风险警告
- `monitor_alert market_brief` → 每周一/五市场简报

---

## 9. 回测验证

### 9.1 三步验证

**步骤1：因子IC回测**

`quant_cli factor.analyze` — 回测周期3年，IC均值>0.03，IC_IR>0.3。

**步骤2：组合层回测**

`quant_cli backtest.run` — 回测周期2年，基准=沪深300×50%+恒生×50%。

| 指标 | 最低要求 |
|------|---------|
| 年化收益率 | > 基准 + 5% |
| 夏普比率 | > 1.0 |
| 最大回撤 | < 20% |
| 胜率 | > 55% |
| 月胜率 | > 60% |

**步骤3：样本外验证**

- 上线前3个月半仓运行
- 3个月后 `quant_cli trade.verify` 对比实盘 vs 回测
- 偏差 < 20% → 满仓；偏差 > 20% → 排查

---

## 10. 运转时间线

```
周一 09:30   执行上周五生成的调仓计划
周一-周五    每30分钟盯盘
周五 15:30   跑完整流水线 → 生成下周调仓计划
周五 17:00   推送市场简报到飞书
每月末       ML重训练 + 策略表现复盘
每季度       IC动态权重重算 + 全量回测验证
```

---

## 11. 工具调用清单

### 每周五流水线调用顺序

```
Phase 1 — 行业轮动：
  quant_cli market.sectors
  quant_cli market.sector_flow
  quant_cli market.index_history
  quant_cli hk.market_overview
  quant_cli hk.south_flow

Phase 2 — 因子精选（对每只候选股）：
  factor_calculate
  quant_cli financial.indicators
  quant_cli hk.technical（港股）
  quant_cli hk.hk_financials（港股）

Phase 3 — ML过滤：
  model_predict（逐只）

Phase 4 — 组合构建：
  portfolio_rebalance get
  → 计算目标 vs 当前 → portfolio_rebalance sell / add

Phase 5 — 执行（下周一）：
  trade_algo_execute TWAP/VWAP
  trade_manage_orders place/check

Phase 6 — 持续监控：
  monitor_alert
  send_risk_warning
  model_monitor（每月）
```

---

## 12. 风险提示

- 历史回测不代表未来表现
- 行业轮动可能在震荡市频繁切换，产生交易成本
- ML模型存在过拟合风险，需持续监控漂移
- 港股流动性差的个股可能无法按TWAP理想执行
- 极端市场（如股灾）所有风控阈值可能同时触发，需人工决策
