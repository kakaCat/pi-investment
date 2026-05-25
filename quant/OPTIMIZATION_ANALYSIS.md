# 量化系统优化分析报告

**对比项目：**
- **pi-investment/quant** (108个Python文件)
- **金策智算** (99个Python文件 + 完整的三省六部架构)

**分析日期：** 2026-05-18

---

## 📊 整体架构对比

### 金策智算的架构优势

#### 1. **三省六部架构** - 清晰的职责分离
```
三省（决策链路）:
├── 太子院 (CrownPrince)      - 数据前置校验与分发
├── 中书省 (ZhongshuSheng)    - 策略信号生成
├── 门下省 (MenxiaSheng)      - 风控审核（一票否决）
└── 尚书省 (ShangshuSheng)    - 执行调度与资金清算

六部（职能部门）:
├── 吏部 (LiBuPersonnel)      - 策略注册与生命周期管理
├── 户部 (HuBuRevenue)        - 现金、成本、净值核算
├── 礼部 (LiBuRites)          - 业绩报表与策略排行
├── 兵部 (BingBuWar)          - 撮合执行与交易管理
├── 刑部 (XingBuJustice)      - 违规记录与风险事件
└── 工部 (GongBuWorks)        - 行情清洗与指标计算
```

**优势：**
- 单一职责原则，每个模块功能明确
- 风控层独立，强制审核所有信号
- 易于扩展和维护

#### 2. **双模式系统** - 回测与实盘统一
```python
# 金策智算
BacktestCabinet (1094行)  # 回测引擎
LiveCabinet (1844行)      # 实盘监控
+ consistency 模块         # 一致性检查
```

**pi-investment现状：**
```python
# 仅有回测引擎
quantsys/backtest/engine.py (约400行)
# 缺少实盘监控和一致性检查
```

---

## 🎯 核心差异与优化建议

### 1. 风控系统 ⭐⭐⭐⭐⭐

#### 金策智算的门下省（MenxiaSheng）
```python
# 强制风控检查（一票否决）
def check_signal(self, signal, ...):
    # Rule 1: 单笔止损 <= 10%
    if sl_pct > max_stop_loss_pct:
        return False, "止损幅度超限"
    
    # Rule 2: 单股仓位 <= 10%
    if position_value / portfolio_value > max_pos_per_stock:
        return False, "单票仓位超限"
    
    # Rule 3: 总仓位 <= 50%
    if total_pos / portfolio_value > max_total_pos:
        return False, "总仓位超限"
    
    # Rule 4: 单日亏损 <= 5% (熔断)
    if daily_pnl / portfolio_value < -max_daily_loss_pct:
        return False, "触发熔断"
    
    # Rule 5: 连续3次亏损 -> 暂停开仓
    if consecutive_losses >= 3:
        return False, "连续亏损暂停"
```

#### pi-investment的PreTradeRiskCheck
```python
# 功能较完善，但缺少：
✅ 黑名单检查
✅ 单股仓位限制
✅ 行业集中度
✅ 回撤限制
✅ 交易次数限制
✅ 流动性检查

❌ 单日亏损熔断
❌ 连续亏损暂停
❌ 实时回撤监控
❌ 风险事件记录（刑部）
```

**优化建议：**
```python
# 新增模块: quantsys/risk/circuit_breaker.py
class CircuitBreaker:
    """熔断机制"""
    def __init__(self):
        self.daily_loss_limit = 0.05      # 5%
        self.consecutive_loss_limit = 3
        self.max_drawdown_limit = 0.20    # 20%
        self.is_halted = False
        
    def check_halt_conditions(self, portfolio, trades):
        # 1. 单日亏损检查
        if self._check_daily_loss(portfolio):
            self.halt("单日亏损触发熔断")
            
        # 2. 连续亏损检查
        if self._check_consecutive_losses(trades):
            self.halt("连续亏损暂停开仓")
            
        # 3. 最大回撤检查
        if self._check_max_drawdown(portfolio):
            self.halt("最大回撤触发熔断")

# 新增模块: quantsys/risk/risk_logger.py
class RiskEventLogger:
    """风险事件记录（类似刑部）"""
    def record_rejection(self, strategy_id, rule_id, reason, timestamp):
        """记录风控拒绝"""
        
    def record_circuit_break(self, strategy_id, reason, timestamp):
        """记录熔断事件"""
        
    def get_violation_history(self, strategy_id):
        """获取违规历史"""
```

---

### 2. 策略组合与信号融合 ⭐⭐⭐⭐⭐

#### 金策智算的组合策略
```python
# 支持三种组合模式
combination_config = {
    "enabled": True,
    "mode": "vote",  # or, and, vote
    "min_agree_count": 2,
    "weights": {"01": 1.5, "02": 1.0, "03": 0.8},
    "tie_policy": "skip"  # skip, buy, sell
}

# 投票机制
def _apply_signal_combination(self, signals, runnable_strategy_ids):
    if mode == "vote":
        buy_score = sum(weights[sid] for sid in buy_signals)
        sell_score = sum(weights[sid] for sid in sell_signals)
        
        if buy_score > sell_score:
            return buy_signals
        elif sell_score > buy_score:
            return sell_signals
        else:
            # 平局处理
            return [] if tie_policy == "skip" else ...
```

**pi-investment现状：**
- ❌ 不支持多策略组合
- ❌ 不支持信号投票
- ❌ 不支持策略权重

**优化建议：**
```python
# 新增模块: quantsys/strategies/combiner.py
class StrategyCombi ner:
    """策略组合器"""
    
    def __init__(self, mode='vote', weights=None):
        self.mode = mode  # 'or', 'and', 'vote'
        self.weights = weights or {}
        
    def combine_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        组合多个策略的信号
        
        Args:
            signals: 来自不同策略的信号列表
            
        Returns:
            组合后的信号
        """
        if self.mode == 'or':
            return signals  # 任一策略发出信号即执行
            
        elif self.mode == 'and':
            # 所有策略必须一致
            return self._and_combine(signals)
            
        elif self.mode == 'vote':
            # 加权投票
            return self._vote_combine(signals)
    
    def _vote_combine(self, signals):
        buy_score = 0
        sell_score = 0
        
        for signal in signals:
            weight = self.weights.get(signal.strategy_id, 1.0)
            if signal.action == 'buy':
                buy_score += weight
            elif signal.action == 'sell':
                sell_score += weight
        
        # 返回得分高的方向
        if buy_score > sell_score:
            return [s for s in signals if s.action == 'buy']
        elif sell_score > buy_score:
            return [s for s in signals if s.action == 'sell']
        else:
            return []  # 平局跳过
```

---

### 3. 回测基线与一致性检查 ⭐⭐⭐⭐

#### 金策智算的global_backtest_baseline
```json
{
  "global_backtest_baseline": {
    "enabled": true,
    "min_history_years": 5,
    "require_regime_coverage": true,  // 必须覆盖牛熊震荡
    "lock_backtest_data_source": false,
    "strategy_profile_mapping": [
      {
        "if": {"strategy_tags_any": ["中线", "波段"]},
        "then_profile": "cn_equity_mid_long"
      }
    ],
    "profiles": {
      "cn_equity_mid_long": {
        "adjustment_mode": "hfq",
        "settlement_rule": "T+1",
        "cost_model": {...}
      }
    }
  }
}
```

**功能：**
- 强制最小回测年限（避免过拟合）
- 要求覆盖不同市场周期
- 策略自动匹配配置文件
- 成本模型统一管理

#### 金策智算的consistency模块
```
src/consistency/
├── collectors/          # 数据收集
├── comparators/         # 回测vs实盘对比
│   └── backtest_live_comparator.py
├── replay/              # 回放分析
├── reporting/           # 一致性报告
└── storage/             # 存储
```

**pi-investment现状：**
- ❌ 无回测基线要求
- ❌ 无市场周期覆盖检查
- ❌ 无回测与实盘一致性检查

**优化建议：**
```python
# 新增模块: quantsys/backtest/baseline_validator.py
class BacktestBaselineValidator:
    """回测基线验证器"""
    
    def __init__(self):
        self.min_history_years = 5
        self.require_regime_coverage = True
        
    def validate(self, start_date, end_date, data):
        """
        验证回测是否满足基线要求
        
        Returns:
            (is_valid, warnings)
        """
        warnings = []
        
        # 1. 检查回测年限
        years = (end_date - start_date).days / 365
        if years < self.min_history_years:
            warnings.append(f"回测年限不足 {self.min_history_years}年")
        
        # 2. 检查市场周期覆盖
        if self.require_regime_coverage:
            regimes = self._detect_market_regimes(data)
            if not self._has_all_regimes(regimes):
                warnings.append("未覆盖所有市场周期（牛/熊/震荡）")
        
        # 3. 检查数据质量
        if self._has_data_gaps(data):
            warnings.append("数据存在缺失")
        
        return len(warnings) == 0, warnings
    
    def _detect_market_regimes(self, data):
        """检测市场周期"""
        # 基于指数走势判断牛熊震荡
        pass

# 新增模块: quantsys/backtest/consistency_checker.py
class ConsistencyChecker:
    """回测与实盘一致性检查"""
    
    def compare(self, backtest_results, live_results):
        """
        对比回测与实盘结果
        
        Returns:
            一致性报告
        """
        report = {
            'signal_consistency': self._check_signals(),
            'execution_deviation': self._check_execution(),
            'performance_drift': self._check_performance()
        }
        return report
```

---

### 4. 实盘监控与偏差检测 ⭐⭐⭐⭐⭐

#### 金策智算的live_monitoring配置
```json
{
  "live_monitoring": {
    "consistency_checks": {
      "signal_execution_delay_seconds_warn": 5,
      "signal_execution_delay_seconds_critical": 15,
      "expected_vs_actual_price_deviation_warn": 0.003,
      "expected_vs_actual_price_deviation_critical": 0.008
    },
    "risk_alerts": {
      "daily_drawdown_warn": 0.02,
      "daily_drawdown_critical": 0.03,
      "max_consecutive_losses_warn": 3,
      "max_consecutive_losses_critical": 5,
      "turnover_rate_warn": 0.5
    },
    "drift_detection": {
      "rolling_days": 20,
      "win_rate_drop_warn": 0.08,
      "profit_loss_ratio_drop_warn": 0.2
    },
    "actions": {
      "on_warn": ["reduce_position"],
      "on_critical": ["pause_strategy", "manual_review"]
    }
  }
}
```

**pi-investment现状：**
- ❌ 无实盘监控模块
- ❌ 无信号延迟检测
- ❌ 无价格偏差告警
- ❌ 无策略漂移检测

**优化建议：**
```python
# 新增模块: quantsys/live/monitor.py
class LiveMonitor:
    """实盘监控"""
    
    def __init__(self, config):
        self.config = config
        self.alerts = []
        
    def check_signal_delay(self, signal_time, execution_time):
        """检查信号执行延迟"""
        delay = (execution_time - signal_time).total_seconds()
        
        if delay > self.config['signal_execution_delay_seconds_critical']:
            self.alert('CRITICAL', f'信号延迟 {delay}秒')
        elif delay > self.config['signal_execution_delay_seconds_warn']:
            self.alert('WARN', f'信号延迟 {delay}秒')
    
    def check_price_deviation(self, expected_price, actual_price):
        """检查成交价偏差"""
        deviation = abs(actual_price - expected_price) / expected_price
        
        if deviation > self.config['expected_vs_actual_price_deviation_critical']:
            self.alert('CRITICAL', f'价格偏差 {deviation:.2%}')
    
    def detect_strategy_drift(self, recent_performance, baseline_performance):
        """检测策略漂移"""
        win_rate_drop = baseline_performance['win_rate'] - recent_performance['win_rate']
        
        if win_rate_drop > self.config['win_rate_drop_warn']:
            self.alert('WARN', f'胜率下降 {win_rate_drop:.2%}')
            self.execute_action('reduce_position')

# 新增模块: quantsys/live/drift_detector.py
class DriftDetector:
    """策略漂移检测"""
    
    def detect(self, rolling_window=20):
        """
        检测策略表现是否漂移
        
        对比最近N天与历史基线的差异
        """
        recent_metrics = self._calculate_recent_metrics(rolling_window)
        baseline_metrics = self._get_baseline_metrics()
        
        drift_score = self._calculate_drift_score(recent_metrics, baseline_metrics)
        
        if drift_score > self.threshold:
            return True, f"策略漂移分数: {drift_score}"
        
        return False, None
```

---

### 5. 策略管理与生命周期 ⭐⭐⭐⭐

#### 金策智算的吏部（LiBuPersonnel）
```python
class LiBuPersonnel:
    """吏部：策略注册与生命周期管理"""
    
    def register_strategy(self, strategy):
        """注册策略"""
        self.strategies[strategy.id] = {
            'instance': strategy,
            'status': 'active',
            'registered_at': datetime.now(),
            'performance': {}
        }
    
    def get_active_strategies(self):
        """获取活跃策略"""
        return [s for s in self.strategies.values() 
                if s['status'] == 'active']
    
    def suspend_strategy(self, strategy_id, reason):
        """暂停策略"""
        self.strategies[strategy_id]['status'] = 'suspended'
        self.strategies[strategy_id]['suspend_reason'] = reason
```

#### 金策智算的strategy_manager_repo.py (880行)
- 策略注册表
- 策略评分系统
- 策略排行榜
- 策略生命周期管理

**pi-investment现状：**
- ✅ 有基础策略基类
- ❌ 无策略注册机制
- ❌ 无策略评分系统
- ❌ 无策略生命周期管理

**优化建议：**
```python
# 新增模块: quantsys/strategies/registry.py
class StrategyRegistry:
    """策略注册表"""
    
    def __init__(self):
        self.strategies = {}
        self.performance_tracker = {}
        
    def register(self, strategy, metadata=None):
        """注册策略"""
        self.strategies[strategy.id] = {
            'instance': strategy,
            'metadata': metadata or {},
            'status': 'active',
            'registered_at': datetime.now(),
            'total_trades': 0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'rating': 'C'
        }
    
    def update_performance(self, strategy_id, metrics):
        """更新策略表现"""
        self.strategies[strategy_id].update(metrics)
        self.strategies[strategy_id]['rating'] = self._calculate_rating(metrics)
    
    def get_top_strategies(self, n=5):
        """获取Top N策略"""
        sorted_strategies = sorted(
            self.strategies.items(),
            key=lambda x: x[1]['sharpe_ratio'],
            reverse=True
        )
        return sorted_strategies[:n]
    
    def _calculate_rating(self, metrics):
        """计算策略评级 (S/A/B/C/D)"""
        score = (
            metrics['sharpe_ratio'] * 0.4 +
            metrics['win_rate'] * 0.3 +
            metrics['calmar_ratio'] * 0.3
        )
        
        if score >= 2.0: return 'S'
        elif score >= 1.5: return 'A'
        elif score >= 1.0: return 'B'
        elif score >= 0.5: return 'C'
        else: return 'D'
```

---

### 6. 数据层对比 ⭐⭐⭐

#### 金策智算的数据源支持
```python
# 支持多种数据源
data_provider:
  source: "tdx"  # akshare, tushare, mysql, postgres, duckdb, tdx
  enable_fallback: true
  
# 数据源切换
providers = {
    'akshare': AkshareProvider,
    'tushare': TushareProvider,
    'mysql': MysqlProvider,
    'postgres': PostgresProvider,
    'duckdb': DuckDbProvider,
    'tdx': TdxProvider  # 通达信
}
```

**特色功能：**
- TDX公式编译器（通达信公式转Python）
- 历史数据同步服务（113KB代码）
- 多数据源fallback机制

**pi-investment现状：**
```python
# quantsys/data/
├── fetchers/           # AkShare数据获取
│   ├── klines.py
│   ├── stock_list.py
│   └── technicals.py
├── db.py              # SQLite存储
└── pipeline.py        # 数据管道
```

**优势：**
- ✅ 有完整的数据获取层
- ✅ 有数据清洗模块
- ✅ 有数据存储

**可优化：**
- ❌ 不支持多数据源切换
- ❌ 不支持TDX
- ❌ 无数据源fallback

---

### 7. 策略进化系统 ⭐⭐⭐

#### 金策智算的evolution模块
```
src/evolution/
├── core/
│   ├── evolution_engine.py      # 进化引擎
│   ├── strategy_gene.py         # 策略基因
│   ├── orchestrator.py          # 编排器
│   └── concurrency_manager.py   # 并发管理
├── llm/
│   └── client_factory.py        # LLM客户端
├── memory/
│   ├── profile_update_store.py  # 配置存储
│   └── gene_run_store.py        # 运行记录
├── algorithms/                   # 进化算法
├── agents/                       # Agent系统
└── runner/                       # 运行器
```

**功能：**
- LLM驱动的策略生成
- 策略基因库管理
- 自动回测评估
- 策略进化迭代

**pi-investment现状：**
```python
# quantsys/ml/
├── models/              # 机器学习模型
├── training/            # 训练模块
└── prediction/          # 预测模块
```

**对比：**
- pi-investment: 传统ML方法（XGBoost, LightGBM）
- 金策智算: LLM + 进化算法

**建议：**
- 保持现有ML pipeline
- 可选：增加LLM辅助策略生成（类似你们的AI Agent）

---

## 📋 优化优先级总结

### P0 - 必须实现（保护资金安全）

1. **熔断机制** (2-3天)
   - 单日亏损熔断
   - 连续亏损暂停
   - 最大回撤熔断
   - 文件：`quantsys/risk/circuit_breaker.py`

2. **风险事件记录** (1天)
   - 记录所有风控拒绝
   - 记录熔断事件
   - 违规历史查询
   - 文件：`quantsys/risk/risk_logger.py`

### P1 - 高优先级（提升系统稳定性）

3. **实盘监控** (3-4天)
   - 信号延迟检测
   - 价格偏差告警
   - 策略漂移检测
   - 文件：`quantsys/live/monitor.py`, `quantsys/live/drift_detector.py`

4. **策略组合** (2-3天)
   - 多策略投票
   - 信号融合
   - 权重配置
   - 文件：`quantsys/strategies/combiner.py`

5. **回测基线验证** (1-2天)
   - 最小年限检查
   - 市场周期覆盖
   - 数据质量验证
   - 文件：`quantsys/backtest/baseline_validator.py`

### P2 - 中优先级（提升研发效率）

6. **策略注册表** (2天)
   - 策略生命周期管理
   - 策略评分系统
   - Top N策略排行
   - 文件：`quantsys/strategies/registry.py`

7. **一致性检查** (2-3天)
   - 回测vs实盘对比
   - 偏差分析
   - 一致性报告
   - 文件：`quantsys/backtest/consistency_checker.py`

### P3 - 低优先级（锦上添花）

8. **多数据源支持** (3-5天)
   - 数据源切换
   - Fallback机制
   - TDX支持（可选）

9. **策略进化** (2-3周)
   - LLM策略生成
   - 参数优化
   - 自动评估

---

## 🎯 快速行动计划

### 第1周：风控增强
```bash
# Day 1-2: 熔断机制
touch quantsys/risk/circuit_breaker.py
touch quantsys/risk/risk_logger.py

# Day 3-4: 集成到回测引擎
# 修改 quantsys/backtest/engine.py

# Day 5: 测试
```

### 第2周：实盘监控
```bash
# Day 1-3: 监控模块
mkdir quantsys/live
touch quantsys/live/__init__.py
touch quantsys/live/monitor.py
touch quantsys/live/drift_detector.py

# Day 4-5: 告警系统
touch quantsys/live/alerter.py
```

### 第3周：策略组合
```bash
# Day 1-2: 组合器
touch quantsys/strategies/combiner.py

# Day 3-4: 策略注册表
touch quantsys/strategies/registry.py

# Day 5: 集成测试
```

---

## 💡 关键差异总结

| 维度 | 金策智算 | pi-investment/quant | 优化建议 |
|------|----------|---------------------|----------|
| **架构** | 三省六部，职责清晰 | 模块化，较扁平 | 保持现有结构，增加风控层 |
| **风控** | 门下省一票否决 + 熔断 | PreTradeRiskCheck | ✅ 增加熔断机制 |
| **策略组合** | 支持投票/AND/OR | 不支持 | ✅ 实现策略组合器 |
| **实盘监控** | LiveCabinet + 一致性检查 | 无 | ✅ 实现实盘监控 |
| **回测基线** | 强制5年+周期覆盖 | 无限制 | ✅ 增加基线验证 |
| **策略管理** | 吏部 + 评分系统 | 基础策略类 | ✅ 实现注册表 |
| **数据层** | 7种数据源 + TDX | AkShare + SQLite | 可选：多数据源 |
| **策略进化** | LLM + 进化算法 | 传统ML | 可选：LLM辅助 |

---

## 📝 实施建议

1. **不要全盘照搬** - 金策智算的三省六部架构很好，但你们的模块化结构也有优势
2. **聚焦核心痛点** - 优先实现风控和实盘监控，这是最大的差距
3. **渐进式优化** - 按P0→P1→P2的顺序逐步实现
4. **保持测试覆盖** - 每个新模块都要有单元测试
5. **文档同步** - 更新README和架构文档

---

## 🔗 参考资料

- 金策智算项目：`/Users/mac/Documents/ai/jin-ce-zhi-suan/jin-ce-zhi-suan`
- pi-investment/quant：`/Users/mac/Documents/ai/pi-investment/quant`
- 对比分析日期：2026-05-18

---

**下一步：** 需要我帮你实现其中某个模块吗？建议从 `circuit_breaker.py` 开始。
