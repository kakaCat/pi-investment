# RFC 012: 股票评分系统重构 — 行业中性化 + 平滑化 + 标准化

**状态**: Draft
**作者**: agent-dh
**日期**: 2026-09-09
**优先级**: P0（影响选股质量）
**关联**: RFC 011（WatchEngine 分层通知）

---

## 1. 问题诊断

### 1.1 问题一：科技股天然低分（错过科技主线）

**现象**：
- 002463 沪电股份（PCB 龙头，AI 服务器核心标的）：评分 65，低于 80 阈值
- 600519 茅台（消费白马）：评分 58，也低于 80
- 大量科技股（PE>30）被排除在高分池外

**根因**：
- 基本面评分使用**绝对值阈值**：PE<15 加分，PE>30 扣分
- 科技股 PE 天然高于银行股（科技 PE=50 vs 银行 PE=5）
- 跨行业绝对比较导致科技股永远低分

**影响**：
- 错过 AI/科技主线机会
- 评分池偏向银行/地产等传统行业

### 1.2 问题二：技术面评分脆弱（分数突变）

**现象**：
- 伊利股份 600887：昨天 91 分 → 今天 69 分（价格只跌 1.2%）
- 技术面评分从 91 暴跌到 55（单日跌 36 分）

**根因**：
- MACD 金叉 +20 分，死叉 -15 分（**突变 35 分**）
- 金叉/死叉是**离散事件**，不是连续函数
- 单日价格波动就可能触发金叉/死叉切换

**影响**：
- 评分不稳定，同一天内可能剧烈波动
- 导致"昨天推荐今天不推荐"的用户困惑

---

## 2. 业界主流评分模型调研

### 2.1 Barra CNE6 模型（业界标准）

**来源**: [DolphinDB Barra 多因子风险模型实践](http://docs.dolphindb.com/zh/tutorials/barra_multi_factor_risk_model_0.html)

**核心思想**：
1. **行业中性化**：因子暴露 = 原始值 - 行业均值（残差化）
2. **市值中性化**：消除市值对因子的影响
3. **风格因子合成**：三级因子 → 二级因子 → 一级因子

**关键方法**：
- **WLS 回归**（加权最小二乘）：用个股流通市值平方根作为权重
- **截面回归**：每个交易日单独做回归，不做 pooled 回归
- **因子检验**：IC 值、t 值、FSC（因子稳定性系数）

### 2.2 因子合成方法（华泰金工）

**来源**: [华泰金工-因子合成方法实证分析](https://bigquant.com/wiki/doc/jsUTAPMovV)

**6 种合成方法**：

| 方法 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| **等权法** | 所有因子等权相加 | 最稳定 | 不考虑因子有效性差异 |
| **历史收益率加权** | 按历史因子收益率加权 | 收益高 | 权重不稳定 |
| **历史 IC 加权** | 按历史 RankIC 加权 | 考虑预测能力 | 权重不稳定 |
| **最大化 IC_IR** | 优化 IC/IC_std 比率 | 效果最好 | 需要协方差矩阵估计 |
| **最大化 IC** | 直接最大化 IC | 效果好 | 权重可能为负 |
| **PCA** | 主成分分析 | 降维 | 无经济学含义 |

**推荐**：最大化 IC_IR（T=12 个月窗口）

### 2.3 因子正交化（社区最佳实践）

**来源**: [factor-orthogonalize skill](https://github.com/quantskills/skill-factor-orthogonalize)

**核心规则**：
1. **逐日截面回归**：每个交易日单独回归
2. **残差才是新因子**：输出 `residual = signal - X @ beta`
3. **不能向收益正交**：严禁把 forward return 放进控制变量
4. **保真度必须报告**：正交前后 IC/Sharpe/turnover 对比

**7 步工作流**：
```
1. 校验信号契约：shape、date/symbol、NaN、截面 std
2. 明确控制变量：industry / log_mktcap / beta / volatility
3. 对齐同一时点可得数据：T 日信号只能用 T 日已知暴露
4. 截面预处理：winsorize → z-score → mask 不可交易股票
5. 逐日回归：signal_t = X_t @ beta_t + residual_t
6. 残差标准化：对 residual_t 做 z-score
7. 输出正交诊断报告
```

### 2.4 QuantConnect 基本面选股

**来源**: [QuantConnect Stock Selection Strategy](https://www.quantconnect.com/research/15370/stock-selection-strategy-based-on-fundamental-factors/)

**核心方法**：
1. **分位数排名**：将股票按因子值分为 5 组（P1~P5）
2. **等权复合评分**：多个因子等权相加
3. **因子有效性检验**：IC 值、分层回测、多空组合

**关键指标**：
- **IC 值** > 0.03 认为因子有效
- **Rank IC**（Spearman 秩相关）比 Pearson 更稳健
- **分层回测**：Top 组和 Bottom 组的绩效差异

---

## 3. 重构方案设计

### 3.1 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    原始因子层                             │
│  基本面因子  技术面因子  资金面因子  情绪面因子            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   预处理层（统一）                        │
│  1. 去极值（Winsorized / MAD）                          │
│  2. 标准化（Z-score）                                    │
│  3. 行业中性化（残差化）                                  │
│  4. 市值中性化（可选）                                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   因子合成层                              │
│  1. 行业内分位数排名（0-100）                             │
│  2. 平滑化（tanh/sigmoid）                               │
│  3. 等权/IC_IR 加权合成                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   最终评分输出                            │
│  总分（0-100）+ 分维度得分 + 行业内排名                   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 行业中性化（解决科技股低分）

**核心思想**：不使用绝对值，而是**行业内相对排名**。

```python
class IndustryNeutralScorer:
    """行业中性评分器"""
    
    def score_stock(self, symbol: str, factors: Dict) -> float:
        # 1. 获取同行业股票列表
        sector = self.get_sector(symbol)
        sector_stocks = self.get_sector_stocks(sector)
        
        # 2. 计算各指标在行业内的分位数（0-1）
        pe_pct = self.calc_percentile(
            factors['pe'],
            [s['pe'] for s in sector_stocks if s['pe'] > 0]
        )
        roe_pct = self.calc_percentile(
            factors['roe'],
            [s['roe'] for s in sector_stocks]
        )
        growth_pct = self.calc_percentile(
            factors['revenue_growth'],
            [s['revenue_growth'] for s in sector_stocks]
        )
        
        # 3. 行业内相对评分（0-100）
        # PE 越低越好（1 - pct）
        # ROE/增长率 越高越好（pct）
        fundamental_score = (
            (1 - pe_pct) * 40 +      # PE 分位数（反向）
            roe_pct * 30 +            # ROE 分位数（正向）
            growth_pct * 30           # 增长率分位数（正向）
        )
        
        return fundamental_score
    
    def calc_percentile(self, value: float, values: List[float]) -> float:
        """计算分位数（0-1）"""
        if not values:
            return 0.5
        sorted_values = sorted(values)
        rank = bisect.bisect_left(sorted_values, value)
        return rank / len(sorted_values)
```

**效果**：
- 科技股 PE=50，如果行业内排名靠前（如前 20%），得分 = (1-0.2) * 40 = 32 分
- 银行股 PE=5，如果行业内排名靠后（如后 20%），得分 = (1-0.8) * 40 = 8 分
- **科技股不再天然低分**

### 3.3 技术面评分平滑化（解决突变）

**核心思想**：用**连续函数**替代**离散事件**。

#### 3.3.1 MACD 平滑化

```python
def _score_macd_smooth(self, factors: Dict) -> float:
    """MACD 平滑评分（±10分，不再突变）
    
    原理：
    - 不再区分金叉/死叉（离散事件）
    - 用 tanh 函数平滑过渡（连续函数）
    - hist 越大分越高，hist 越小分越低
    
    参数：
    - hist = macd - signal（MACD 柱状图）
    - scale = 50（控制平滑程度）
    
    返回值：-10 到 +10 分
    """
    macd = factors.get('macd', 0)
    signal = factors.get('macd_signal', 0)
    hist = macd - signal
    
    # tanh 平滑：hist=0 时得 0 分，hist→+∞ 时得 +10 分
    score = 10 * np.tanh(hist * 50)
    
    return score
```

**对比**：

| 场景 | 原方案 | 新方案 |
|------|--------|--------|
| hist = 0.01（刚金叉） | +10 分（突变） | +0.5 分（平滑） |
| hist = 0.05（强金叉） | +15 分 | +2.4 分 |
| hist = -0.01（刚死叉） | -15 分（突变） | -0.5 分（平滑） |
| hist = -0.05（强死叉） | -20 分 | -2.4 分 |

**效果**：评分变化从 ±35 分突变 → ±10 分平滑过渡

#### 3.3.2 RSI 平滑化

```python
def _score_rsi_smooth(self, rsi: float) -> float:
    """RSI 平滑评分（±15分，连续过渡）
    
    原理：
    - RSI=50 为中性（0 分）
    - RSI<30 超卖（正分）
    - RSI>70 超买（负分）
    - 用 sigmoid 函数平滑过渡
    
    参数：
    - rsi: RSI 指标值（0-100）
    
    返回值：-15 到 +15 分
    """
    # 超卖区（RSI<30）：加分
    if rsi < 30:
        # sigmoid 平滑：RSI=0 时 +15 分，RSI=30 时 0 分
        score = 15 * (1 / (1 + np.exp((rsi - 15) / 5)))
    # 超买区（RSI>70）：扣分
    elif rsi > 70:
        # sigmoid 平滑：RSI=100 时 -15 分，RSI=70 时 0 分
        score = -15 * (1 / (1 + np.exp((85 - rsi) / 5)))
    # 中性区（30-70）：线性过渡
    else:
        score = 0
    
    return score
```

**效果**：RSI 评分从离散跳变 → 连续平滑过渡

### 3.4 Z-score 标准化（统一量纲）

**核心思想**：所有因子先做 Z-score 标准化，然后再加权。

```python
def zscore_normalize(self, values: List[float]) -> List[float]:
    """Z-score 标准化
    
    原理：
    - 减去均值，除以标准差
    - 输出均值=0，标准差=1 的分布
    - 不同量纲的因子可以直接加权
    
    参数：
    - values: 因子值列表
    
    返回值：标准化后的列表
    """
    mean = np.mean(values)
    std = np.std(values)
    if std == 0:
        return [0] * len(values)
    return [(v - mean) / std for v in values]
```

**应用场景**：
- 基本面因子：PE、PB、ROE、增长率（量纲不同）
- 技术面因子：RSI、MACD、ADX、成交量（量纲不同）
- 资金面因子：主力净流入、两融余额（量纲不同）

### 3.5 因子合成（加权方案）

**推荐方案**：**等权法 + 行业内分位数**

```python
def composite_score(self, symbol: str, factors: Dict) -> Dict:
    """复合评分（等权 + 行业内分位数）
    
    步骤：
    1. 各维度评分（0-100）
    2. 行业内分位数调整
    3. 等权合成总分
    """
    # 1. 各维度评分
    tech_score = self.technical_scorer.score(factors)
    fund_score = self.fundamental_scorer.score(factors)
    capital_score = self.capital_scorer.score(factors)
    
    # 2. 行业内分位数调整
    sector = self.get_sector(symbol)
    sector_scores = self.get_sector_scores(sector)
    
    tech_pct = self.calc_percentile(tech_score, sector_scores['tech'])
    fund_pct = self.calc_percentile(fund_score, sector_scores['fund'])
    capital_pct = self.calc_percentile(capital_score, sector_scores['capital'])
    
    # 3. 等权合成（各 1/3 权重）
    total_score = (tech_pct + fund_pct + capital_pct) / 3 * 100
    
    return {
        'total': total_score,
        'technical': tech_score,
        'fundamental': fund_score,
        'capital': capital_score,
        'sector_percentile': {
            'technical': tech_pct,
            'fundamental': fund_pct,
            'capital': capital_pct,
        }
    }
```

**为什么选等权法**：
- 最稳定（权重不变）
- 不需要历史数据训练
- 适合初期快速迭代

**后续可扩展**：
- Phase 2：历史 IC 加权
- Phase 3：最大化 IC_IR

---

## 4. 实施计划

### Phase 1：行业中性化（P0，本周完成）

**目标**：解决科技股低分问题

**任务**：
1. 新增 `IndustryNeutralScorer` 类
2. 实现 `calc_percentile()` 方法
3. 修改 `FundamentalScorer` 使用行业内分位数
4. 单元测试：验证科技股得分提升

**验收标准**：
- 002463 沪电股份评分从 65 提升到 75+
- 科技股平均分提升 10+ 分

### Phase 2：技术面平滑化（P0，本周完成）

**目标**：解决评分突变问题

**任务**：
1. 修改 `TechnicalScorer._score_macd()` 使用 tanh 平滑
2. 修改 `TechnicalScorer._score_rsi()` 使用 sigmoid 平滑
3. 单元测试：验证评分变化 <10 分

**验收标准**：
- 伊利股份单日评分变化 <10 分（原 36 分）
- MACD 金叉/死叉切换时评分平滑过渡

### Phase 3：Z-score 标准化（P1，下周完成）

**目标**：统一因子量纲

**任务**：
1. 新增 `zscore_normalize()` 工具函数
2. 修改所有 scorer 使用 Z-score 标准化
3. 因子检验：IC 值、t 值、FSC

**验收标准**：
- 所有因子均值≈0，标准差≈1
- 因子 IC 值 >0.03

### Phase 4：因子合成优化（P2，下下周完成）

**目标**：优化因子权重

**任务**：
1. 实现历史 IC 加权（可选）
2. 实现最大化 IC_IR（可选）
3. 回测验证

**验收标准**：
- 复合因子 IC_IR > 等权法
- 多空组合夏普比率提升

---

## 5. 风险评估

### 5.1 数据风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 行业分类不准确 | 中 | 高 | 使用申万/中信标准行业分类 |
| 历史数据不足 | 低 | 中 | 使用滚动窗口（12个月） |
| 极端行情 | 低 | 高 | Winsorized 去极值 |

### 5.2 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 平滑化导致信号滞后 | 中 | 中 | 调整 tanh/sigmoid 参数 |
| 行业中性化过度 | 低 | 中 | 保留部分行业敞口 |
| 计算性能下降 | 低 | 低 | 缓存行业分位数 |

---

## 6. 参考资料

1. [Barra CNE6 模型实践 - DolphinDB](http://docs.dolphindb.com/zh/tutorials/barra_multi_factor_risk_model_0.html)
2. [因子合成方法实证分析 - 华泰金工](https://bigquant.com/wiki/doc/jsUTAPMovV)
3. [Factor Orthogonalize - QuantSkills](https://github.com/quantskills/skill-factor-orthogonalize)
4. [QuantConnect 基本面选股策略](https://www.quantconnect.com/research/15370/stock-selection-strategy-based-on-fundamental-factors/)
5. [AQR Quality Factor](https://www.aqr.com/Insights/Research/White-Papers/Quality-Minus-Junk)
6. [Fama-French 五因子模型](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)

---

## 7. 附录

### 7.1 行业分类标准

**推荐**：申万一级行业分类（31 个行业）

**备选**：中信一级行业分类（29 个行业）

### 7.2 平滑函数对比

| 函数 | 公式 | 优点 | 缺点 |
|------|------|------|------|
| **tanh** | `(e^x - e^-x) / (e^x + e^-x)` | 输出 [-1, 1]，中心对称 | 两端饱和 |
| **sigmoid** | `1 / (1 + e^-x)` | 输出 [0, 1]，单调递增 | 不对称 |
| **线性** | `x` | 简单直观 | 无平滑效果 |

**推荐**：tanh（MACD）、sigmoid（RSI）

### 7.3 分位数计算方法

```python
def calc_percentile(value: float, values: List[float]) -> float:
    """计算分位数（0-1）
    
    方法：bisect 二分查找
    时间复杂度：O(log n)
    """
    import bisect
    sorted_values = sorted(values)
    rank = bisect.bisect_left(sorted_values, value)
    return rank / len(sorted_values)
```

---

**文档版本**: v1.0
**最后更新**: 2026-09-09
**审核状态**: 待审核
