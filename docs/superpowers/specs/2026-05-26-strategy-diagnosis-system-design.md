# 量化策略诊断系统设计文档

**日期**: 2026-05-26  
**版本**: 1.0  
**状态**: 设计完成，待实现

## 一、概述

### 1.1 目标

在 quantsys-v2 的 BacktestCenter 页面中集成策略诊断功能，帮助用户快速判断策略有效性，识别无效因子，并生成可追溯的诊断报告。

**核心价值**：
- 快速判断策略是否有效（夏普比率 < 1.0 = 不如指数）
- 识别无效因子（IC < 0.03）
- 提供优化建议
- 生成可追溯的诊断报告

### 1.2 设计原则

- **先实现，再优化** - MVP 优先，快速验证价值
- **复用现有架构** - 基于 v2 现有的 Service/Repository/API 模式
- **按需触发** - 用户手动运行诊断，不自动执行
- **混合评级** - 固定阈值 + 基准对比
- **文件存储** - 报告保存为 Markdown 文件，数据库存摘要

## 二、架构设计

### 2.1 整体架构

```
前端 (BacktestCenter)
    ↓ HTTP
API (/api/diagnosis/*)
    ↓
DiagnosisService (新增)
    ├─ StrategyAnalyzer (策略分析器)
    ├─ FactorICAnalyzer (因子 IC 分析器)
    └─ ReportGenerator (报告生成器)
    ↓
Repositories (复用现有)
    ├─ BacktestRepository
    ├─ FactorRepository
    └─ KlineRepository
```

### 2.2 新增组件

**后端服务层**：
- `services/diagnosis_service.py` - 诊断服务主入口
- `services/strategy_analyzer.py` - 策略指标分析
- `services/factor_ic_analyzer.py` - 因子 IC 计算
- `services/report_generator.py` - 报告生成器

**API 路由**：
- `api/routes/diagnosis.py` - 诊断相关端点

**前端组件**：
- `web-frontend/src/views/BacktestCenter/DiagnosisTab.vue` - 诊断标签页
- `web-frontend/src/views/BacktestCenter/DiagnosisCards.vue` - 指标卡片组件
- `web-frontend/src/views/BacktestCenter/FactorICChart.vue` - 因子 IC 图表

**CLI 命令**：
- `python cli/main.py diagnosis run --backtest-id 123`
- `python cli/main.py diagnosis factor-ic --symbols 000001.SZ`

## 三、API 设计

### 3.1 POST /api/diagnosis/run

运行策略诊断。

**请求**：
```json
{
  "backtestId": "123",           // 回测记录 ID（可选）
  "symbol": "000001.SZ",         // 股票代码
  "startDate": "2024-01-01",
  "endDate": "2024-12-31",
  "strategyName": "ma_cross",
  "benchmark": "000300.SH"       // 基准指数（默认沪深300）
}
```

**响应**：
```json
{
  "diagnosisId": "diag_20260526_001",
  "timestamp": "2026-05-26T10:30:00",
  "strategy": {
    "name": "ma_cross",
    "symbol": "000001.SZ",
    "period": "2024-01-01 ~ 2024-12-31"
  },
  "metrics": {
    "annualReturn": 0.15,
    "sharpeRatio": 1.2,
    "maxDrawdown": -0.18,
    "winRate": 0.55,
    "totalTrades": 24
  },
  "benchmark": {
    "name": "沪深300",
    "annualReturn": 0.08,
    "sharpeRatio": 0.6,
    "maxDrawdown": -0.25
  },
  "ratings": {
    "overall": "B",
    "return": "good",
    "risk": "moderate",
    "stability": "good"
  },
  "diagnosis": {
    "conclusion": "策略表现中等，夏普比率 1.2 优于基准指数 0.6，但最大回撤偏高",
    "strengths": [
      "夏普比率优于基准",
      "胜率超过 50%"
    ],
    "weaknesses": [
      "最大回撤 18% 偏高，建议加强止损",
      "交易次数较少，可能错过机会"
    ],
    "suggestions": [
      "添加动态止损（基于 ATR）",
      "优化入场信号，提高交易频率"
    ]
  },
  "reportPath": "docs/superpowers/reports/2026-05-26-ma_cross-diagnosis.md"
}
```

### 3.2 GET /api/diagnosis/factor-ic

因子 IC 分析。

**请求参数**：
```
symbols: 000001.SZ,600519.SH  // 股票池（逗号分隔）
startDate: 2024-01-01
endDate: 2024-12-31
factors: rsi14,macd,ma20      // 可选，默认全部因子
```

**响应**：
```json
{
  "summary": {
    "totalFactors": 62,
    "effectiveFactors": 15,
    "avgIC": 0.045,
    "redundantPairs": 8
  },
  "factors": [
    {
      "name": "rsi14",
      "ic": 0.082,
      "icStd": 0.015,
      "coverage": 0.95,
      "rating": "excellent",
      "suggestion": "保留，预测能力强"
    }
  ],
  "redundancy": [
    {
      "factor1": "ma5",
      "factor2": "ma10",
      "correlation": 0.85,
      "suggestion": "高度相关，建议只保留一个"
    }
  ],
  "topFactors": ["rsi14", "volume_ratio", "macd"],
  "bottomFactors": ["ma5", "kdj_k", "cci"]
}
```

## 四、服务层设计

### 4.1 DiagnosisService

```python
class DiagnosisService:
    """策略诊断服务"""
    
    def run_diagnosis(self, params: dict) -> dict:
        """运行完整诊断"""
        # 1. 获取回测数据
        # 2. 获取基准数据
        # 3. 策略分析
        # 4. 生成诊断结论
        # 5. 生成报告文件
        pass
    
    def analyze_factor_ic(self, params: dict) -> dict:
        """因子 IC 分析"""
        pass
```

### 4.2 StrategyAnalyzer

```python
class StrategyAnalyzer:
    """策略指标分析器"""
    
    # 固定阈值标准
    THRESHOLDS = {
        'sharpe': {'excellent': 1.5, 'good': 1.0, 'poor': 0.5},
        'return': {'excellent': 0.15, 'good': 0.10, 'poor': 0.05},
        'drawdown': {'excellent': -0.15, 'good': -0.25, 'poor': -0.35}
    }
    
    def analyze(self, backtest_data: dict, benchmark_data: dict) -> dict:
        """分析策略表现"""
        # 1. 计算评级
        # 2. 对比基准
        # 3. 综合评级 A/B/C/D
        pass
```

### 4.3 FactorICAnalyzer

```python
class FactorICAnalyzer:
    """因子 IC 分析器"""
    
    def analyze(self, symbols: list, start_date: str, end_date: str, factors: list = None) -> dict:
        """计算因子 IC"""
        # 1. 获取因子数据
        # 2. 获取未来收益数据
        # 3. 计算 IC（相关系数）
        # 4. 计算因子相关性矩阵
        # 5. 识别冗余因子
        pass
    
    def calculate_ic(self, factor_values: list, forward_returns: list) -> float:
        """计算单个因子的 IC 值"""
        return np.corrcoef(factor_values, forward_returns)[0, 1]
```

### 4.4 ReportGenerator

```python
class ReportGenerator:
    """报告生成器"""
    
    def generate(self, analysis: dict, diagnosis: dict, params: dict) -> str:
        """生成 Markdown 报告"""
        # 1. 生成报告内容
        # 2. 保存到 docs/superpowers/reports/
        # 3. 返回文件路径
        pass
```

## 五、前端设计

### 5.1 BacktestCenter 改造

在现有回测结果页面添加"策略诊断"标签页：

```vue
<el-tabs v-model="activeTab">
  <el-tab-pane label="回测结果" name="result">
    <!-- 现有回测结果展示 -->
  </el-tab-pane>
  
  <el-tab-pane label="策略诊断" name="diagnosis">
    <DiagnosisTab :backtest-result="backtestResult" />
  </el-tab-pane>
</el-tabs>
```

### 5.2 DiagnosisTab 组件

**布局结构**：
```
┌─────────────────────────────────────────┐
│  [运行诊断] 按钮                         │
├─────────────────────────────────────────┤
│  关键指标卡片（4个）                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │年化  │ │夏普  │ │回撤  │ │评级  │  │
│  │15%   │ │1.2   │ │-18%  │ │ B    │  │
│  └──────┘ └──────┘ └──────┘ └──────┘  │
├─────────────────────────────────────────┤
│  诊断结论                                │
│  ✓ 优势：夏普比率优于基准                │
│  ✗ 劣势：最大回撤偏高                    │
│  💡 建议：添加动态止损                   │
├─────────────────────────────────────────┤
│  与基准对比图表                          │
│  [柱状图：策略 vs 沪深300]               │
└─────────────────────────────────────────┘
```

### 5.3 因子 IC 分析（可选，后期实现）

在 FactorAnalysis 页面添加 IC 分析功能。

## 六、评级标准

### 6.1 固定阈值

| 指标 | 优秀 | 良好 | 一般 | 差 |
|------|------|------|------|-----|
| 夏普比率 | > 1.5 | > 1.0 | > 0.5 | < 0.5 |
| 年化收益 | > 15% | > 10% | > 5% | < 5% |
| 最大回撤 | > -15% | > -25% | > -35% | < -35% |

### 6.2 相对基准

- 夏普比率 vs 基准：差值 > 0.3 为优秀
- 年化收益 vs 基准：超额收益 > 5% 为优秀
- 最大回撤 vs 基准：回撤更小为优秀

### 6.3 综合评级算法

```python
score = 0

# 稳定性（夏普比率）权重 40%
if sharpe > 1.5: score += 40
elif sharpe > 1.0: score += 25
else: score += 10

# 收益权重 30%
if return > 0.15: score += 30
elif return > 0.10: score += 20
else: score += 5

# 风险控制权重 20%
if drawdown > -0.15: score += 20
elif drawdown > -0.25: score += 10

# 相对基准加分 10%
if sharpe_vs_benchmark > 0.3: score += 10

# 评级映射
if score >= 80: rating = 'A'
elif score >= 60: rating = 'B'
elif score >= 40: rating = 'C'
else: rating = 'D'
```

## 七、报告格式

### 7.1 文件命名

`docs/superpowers/reports/YYYY-MM-DD-{strategy_name}-{symbol}-diagnosis.md`

示例：`2026-05-26-ma_cross-000001.SZ-diagnosis.md`

### 7.2 报告模板

```markdown
# 策略诊断报告

**诊断时间**: 2026-05-26 10:30:00  
**策略名称**: MA 双均线  
**股票代码**: 000001.SZ (平安银行)  
**回测周期**: 2024-01-01 ~ 2024-12-31  
**基准指数**: 沪深300 (000300.SH)

## 一、综合评级

**评级**: B

**结论**: 策略表现中等，夏普比率 1.2 优于基准指数 0.6，但最大回撤偏高。

## 二、关键指标

| 指标 | 策略 | 基准 | 评级 |
|------|------|------|------|
| 年化收益 | 15.0% | 8.0% | 良好 |
| 夏普比率 | 1.2 | 0.6 | 良好 |
| 最大回撤 | -18.0% | -25.0% | 一般 |
| 胜率 | 55.0% | - | 一般 |
| 交易次数 | 24 | - | - |

## 三、诊断分析

### 优势
- ✓ 夏普比率 1.2 优于基准 0.6，风险调整后收益较好
- ✓ 胜率 55% 超过 50%，策略有正向预期

### 劣势
- ✗ 最大回撤 -18% 偏高，建议加强止损
- ✗ 交易次数 24 次较少，可能错过部分机会

### 优化建议
1. **添加动态止损** - 基于 ATR 的跟踪止损，控制回撤
2. **优化入场信号** - 提高交易频率，捕捉更多机会
3. **加入市场状态识别** - 牛市/熊市使用不同参数

## 四、详细数据

### 月度收益
| 月份 | 收益率 |
|------|--------|
| 2024-01 | 2.5% |
| 2024-02 | -1.2% |
| ... | ... |

### 交易记录
| 日期 | 操作 | 价格 | 盈亏 |
|------|------|------|------|
| 2024-01-15 | 买入 | 10.50 | - |
| 2024-01-25 | 卖出 | 11.20 | +6.7% |
| ... | ... | ... | ... |

---

**报告生成时间**: 2026-05-26 10:30:00  
**系统版本**: quantsys-v2
```

## 八、实现计划

### 8.1 MVP 范围（第一阶段）

**后端**：
1. `DiagnosisService` - 基础诊断逻辑
2. `StrategyAnalyzer` - 策略评级
3. `ReportGenerator` - Markdown 报告生成
4. API 端点 `/api/diagnosis/run`

**前端**：
1. `DiagnosisTab.vue` - 诊断标签页
2. `DiagnosisCards.vue` - 指标卡片
3. 集成到 BacktestCenter

**功能**：
- 运行诊断按钮
- 显示关键指标（年化收益、夏普、回撤、评级）
- 显示诊断结论（优势、劣势、建议）
- 生成 Markdown 报告

### 8.2 后续优化（第二阶段）

1. 因子 IC 分析功能
2. 与基准对比图表
3. 历史诊断记录查询
4. CLI 命令支持
5. 定时自动诊断（scheduler）

## 九、技术细节

### 9.1 基准数据获取

```python
def _get_benchmark_data(self, benchmark_symbol: str, start_date: str, end_date: str) -> dict:
    """获取基准指数数据"""
    # 1. 从 kline_repository 获取指数 K 线
    klines = self.kline_repo.get_daily_klines(benchmark_symbol, start_date, end_date)
    
    # 2. 计算基准指标
    returns = calculate_returns(klines)
    sharpe = calculate_sharpe_ratio(returns)
    max_dd = calculate_max_drawdown(klines)
    
    return {
        'symbol': benchmark_symbol,
        'name': get_index_name(benchmark_symbol),
        'annualReturn': returns,
        'sharpeRatio': sharpe,
        'maxDrawdown': max_dd
    }
```

### 9.2 诊断结论生成逻辑

```python
def _generate_diagnosis(self, analysis: dict) -> dict:
    """生成诊断结论"""
    metrics = analysis['metrics']
    ratings = analysis['ratings']
    comparison = analysis['comparison']
    
    # 优势
    strengths = []
    if ratings['stability'] in ['excellent', 'good']:
        strengths.append(f"夏普比率 {metrics['sharpeRatio']:.2f} 优于基准 {comparison['benchmark_sharpe']:.2f}")
    if metrics['winRate'] > 0.5:
        strengths.append(f"胜率 {metrics['winRate']:.1%} 超过 50%")
    
    # 劣势
    weaknesses = []
    if abs(metrics['maxDrawdown']) > 0.25:
        weaknesses.append(f"最大回撤 {metrics['maxDrawdown']:.1%} 偏高，建议加强止损")
    if metrics['totalTrades'] < 20:
        weaknesses.append("交易次数较少，可能错过机会")
    
    # 建议
    suggestions = []
    if abs(metrics['maxDrawdown']) > 0.25:
        suggestions.append("添加动态止损（基于 ATR）")
    if metrics['totalTrades'] < 20:
        suggestions.append("优化入场信号，提高交易频率")
    if ratings['overall'] in ['C', 'D']:
        suggestions.append("考虑加入市场状态识别")
    
    # 结论
    conclusion = self._generate_conclusion(ratings, comparison)
    
    return {
        'conclusion': conclusion,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'suggestions': suggestions
    }
```

## 十、测试计划

### 10.1 单元测试

- `test_strategy_analyzer.py` - 测试评级算法
- `test_diagnosis_service.py` - 测试诊断流程
- `test_report_generator.py` - 测试报告生成

### 10.2 集成测试

- 端到端测试：前端点击 → API 调用 → 报告生成
- 测试用例：
  - 优秀策略（夏普 > 1.5）
  - 一般策略（夏普 1.0-1.5）
  - 差策略（夏普 < 1.0）

### 10.3 手动测试

1. 运行回测
2. 点击"运行诊断"
3. 查看诊断结果
4. 验证报告文件生成
5. 检查评级是否合理

## 十一、风险和限制

### 11.1 已知限制

1. **基准数据依赖** - 需要数据库中有指数 K 线数据
2. **单一市场** - 目前只支持 A 股，港股需要单独适配
3. **固定阈值** - 评级标准是固定的，未考虑市场环境变化
4. **简化计算** - 夏普比率使用简化公式，未考虑无风险利率

### 11.2 后续改进方向

1. 支持自定义阈值
2. 支持多市场（A 股、港股、美股）
3. 添加更多诊断维度（换手率、持仓时间分布等）
4. 机器学习预测策略衰退

## 十二、总结

本设计文档定义了量化策略诊断系统的完整架构和实现方案。核心价值是帮助用户快速判断策略有效性，识别问题，并提供优化建议。

**关键决策**：
- 改造 BacktestCenter 而非新建页面
- 混合评级（固定阈值 + 基准对比）
- 报告保存为 Markdown 文件
- MVP 优先，先实现核心功能

**下一步**：
1. 创建实现计划（writing-plans skill）
2. 实现后端服务层
3. 实现 API 端点
4. 实现前端组件
5. 测试和优化
