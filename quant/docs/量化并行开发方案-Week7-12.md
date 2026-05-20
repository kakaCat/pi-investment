# 量化项目并行开发方案 - Week 7-12

## Week 7-8: ML模块开发 (并行)

### 🟢 研究员B: ML特征工程 + 模型训练

#### 1. 特征工程模块
```python
ml/features/
├── feature_engineering.py          # 特征工程
├── feature_selection.py            # 特征选择
└── feature_importance.py           # 特征重要性
```

**特征工程核心:**
```python
class FeatureEngineer:
    def create_features(self, data):
        """创建ML特征"""
        features = {}
        
        # 1. 价格特征
        features['return_1d'] = data['close'].pct_change(1)
        features['return_5d'] = data['close'].pct_change(5)
        features['return_20d'] = data['close'].pct_change(20)
        features['volatility_20d'] = data['close'].pct_change().rolling(20).std()
        
        # 2. 技术指标特征 (从因子库获取)
        features['rsi'] = calculate_rsi(data)
        features['macd'] = calculate_macd(data)
        features['bollinger_position'] = calculate_bollinger_position(data)
        
        # 3. 统计特征
        returns = data['close'].pct_change()
        features['skewness_20d'] = returns.rolling(20).skew()
        features['kurtosis_20d'] = returns.rolling(20).kurt()
        
        # 4. 时间特征
        features['day_of_week'] = data.index.dayofweek
        features['month'] = data.index.month
        
        # 5. 交叉特征
        features['rsi_ma_cross'] = features['rsi'] * features['ma5_ma20_ratio']
        
        return features
```

#### 2. 模型训练模块
```python
ml/training/
├── cross_validation.py             # 时间序列CV ⭐
├── hyperparameter_tuning.py        # 超参数优化
└── trainer.py                      # 训练框架
```

**时间序列交叉验证 (修复当前问题):**
```python
# ❌ 当前错误做法:
model.fit(X, y)
accuracy = model.score(X, y)  # 训练集=测试集，过拟合!

# ✅ 正确做法:
from sklearn.model_selection import TimeSeriesSplit

class TimeSeriesCV:
    def __init__(self, n_splits=5, test_size=30):
        self.n_splits = n_splits
        self.test_size = test_size
        
    def split(self, data):
        """时间序列交叉验证"""
        n = len(data)
        train_size = (n - self.test_size) // self.n_splits
        
        for i in range(self.n_splits):
            train_end = train_size * (i + 1)
            test_end = train_end + self.test_size
            
            train_idx = range(0, train_end)
            test_idx = range(train_end, min(test_end, n))
            
            yield train_idx, test_idx

# 使用
tscv = TimeSeriesCV(n_splits=5)
scores = []
for train_idx, test_idx in tscv.split(data):
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    
    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)
    scores.append(score)

print(f"CV Score: {np.mean(scores):.3f} ± {np.std(scores):.3f}")
```

#### 3. 超参数优化
```python
from optuna import create_study

class HyperparameterTuner:
    def tune_xgboost(self, X_train, y_train, X_val, y_val):
        """贝叶斯优化XGBoost超参数"""
        def objective(trial):
            params = {
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 7),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            }
            
            model = XGBClassifier(**params, random_state=42)
            model.fit(X_train, y_train)
            
            y_pred = model.predict_proba(X_val)[:, 1]
            return roc_auc_score(y_val, y_pred)
        
        study = create_study(direction='maximize')
        study.optimize(objective, n_trials=50)
        
        return study.best_params, study.best_value
```

#### 4. 模型集成
```python
ml/models/
├── xgboost_model.py
├── lightgbm_model.py
└── ensemble.py                     # Stacking集成
```

**Stacking集成:**
```python
class StackingEnsemble:
    def __init__(self):
        # 第一层: 基模型
        self.base_models = {
            'xgboost': XGBClassifier(),
            'lightgbm': LGBMClassifier(),
            'random_forest': RandomForestClassifier()
        }
        # 第二层: 元模型
        self.meta_model = LogisticRegression()
        
    def train(self, X_train, y_train, X_val, y_val):
        """Stacking训练"""
        # 训练基模型
        meta_features_train = []
        meta_features_val = []
        
        for name, model in self.base_models.items():
            model.fit(X_train, y_train)
            meta_features_train.append(model.predict_proba(X_train)[:, 1])
            meta_features_val.append(model.predict_proba(X_val)[:, 1])
        
        # 训练元模型
        meta_X_train = np.column_stack(meta_features_train)
        meta_X_val = np.column_stack(meta_features_val)
        
        self.meta_model.fit(meta_X_train, y_train)
        
        return self.meta_model.score(meta_X_val, y_val)
```

**交付物:**
- [ ] 特征工程pipeline (50+特征)
- [ ] 时间序列交叉验证
- [ ] 超参数优化 (Optuna)
- [ ] 模型集成 (Stacking)
- [ ] 模型评估报告 (准确率/AUC/精确率/召回率)

---

### 🔵 开发C (可选): 监控工具

```python
monitor/
├── dashboard.py                    # 监控面板
├── logger.py                       # 日志系统
└── visualizer.py                   # 可视化工具
```

**监控面板功能:**
- 策略运行状态
- 回测结果可视化
- 因子有效性监控
- 模型性能监控

---

## Week 9-10: 风控系统 (并行)

### 🟢 开发B: 风控基础设施

```python
risk/
├── pre_trade.py                    # 预交易风控
├── position.py                     # 仓位管理
├── stop_loss.py                    # 止损机制
└── monitor.py                      # 风险监控
```

#### 1. 预交易风控
```python
class PreTradeRiskCheck:
    def __init__(self, config):
        self.max_position_pct = config['max_position_pct']      # 单股最大仓位 10%
        self.max_sector_pct = config['max_sector_pct']          # 单行业最大仓位 30%
        self.max_drawdown = config['max_drawdown']              # 最大回撤限制 20%
        self.blacklist = config['blacklist']                    # 黑名单
        
    def check(self, order, portfolio):
        """预交易检查"""
        # 1. 黑名单检查
        if order.symbol in self.blacklist:
            return False, "股票在黑名单中"
            
        # 2. ST股票检查
        if self._is_st_stock(order.symbol):
            return False, "不允许交易ST股票"
            
        # 3. 仓位限制检查
        new_position_pct = self._calculate_position_pct(order, portfolio)
        if new_position_pct > self.max_position_pct:
            return False, f"超过单股仓位限制 {self.max_position_pct*100}%"
            
        # 4. 行业集中度检查
        sector = self._get_sector(order.symbol)
        sector_pct = self._calculate_sector_pct(sector, portfolio)
        if sector_pct > self.max_sector_pct:
            return False, f"超过行业集中度限制 {self.max_sector_pct*100}%"
            
        # 5. 回撤限制检查
        if portfolio.current_drawdown > self.max_drawdown:
            return False, f"触发最大回撤限制 {self.max_drawdown*100}%"
            
        return True, "通过风控检查"
```

#### 2. 仓位管理 (Kelly公式)
```python
class PositionManager:
    def calculate_position_size(self, signal, portfolio, risk_params):
        """
        使用Kelly公式计算仓位:
        Kelly% = (p * b - q) / b
        其中:
        p = 胜率
        q = 1 - p
        b = 盈亏比 (平均盈利/平均亏损)
        """
        win_rate = signal.confidence
        avg_win = signal.expected_return
        avg_loss = abs(signal.stop_loss)
        
        if avg_loss == 0:
            return 0
            
        profit_loss_ratio = avg_win / avg_loss
        kelly_pct = (win_rate * profit_loss_ratio - (1 - win_rate)) / profit_loss_ratio
        
        # Kelly公式通常过于激进，使用半Kelly或1/4 Kelly
        kelly_pct = max(0, min(kelly_pct * 0.5, risk_params['max_kelly']))
        
        # 波动率调整
        volatility = self._calculate_volatility(signal.symbol)
        vol_adjusted_pct = kelly_pct / (volatility / 0.02)  # 标准化到2%波动率
        
        # 计算股数
        position_value = portfolio.capital * vol_adjusted_pct
        shares = int(position_value / signal.price / 100) * 100  # 取整到手
        
        return shares
```

#### 3. 止损机制
```python
class StopLossManager:
    def __init__(self):
        self.rules = {
            'fixed_pct': -0.05,          # 固定5%止损
            'atr_multiple': 2,            # 2倍ATR止损
            'trailing_pct': 0.03,         # 3%移动止损
            'time_stop': 20               # 20天时间止损
        }
        
    def check_stop_loss(self, position, current_price, current_date):
        """检查是否触发止损"""
        # 1. 固定百分比止损
        pnl_pct = (current_price - position.cost) / position.cost
        if pnl_pct < self.rules['fixed_pct']:
            return True, "触发固定止损"
            
        # 2. ATR止损
        atr = self._get_atr(position.symbol)
        if current_price < position.cost - atr * self.rules['atr_multiple']:
            return True, "触发ATR止损"
            
        # 3. 移动止损
        if position.highest_price:
            trailing_stop = position.highest_price * (1 - self.rules['trailing_pct'])
            if current_price < trailing_stop:
                return True, "触发移动止损"
                
        # 4. 时间止损
        holding_days = (current_date - position.entry_date).days
        if holding_days > self.rules['time_stop'] and pnl_pct < 0:
            return True, "触发时间止损"
            
        return False, None
```

**交付物:**
- [ ] 预交易风控 (黑名单/仓位/行业集中度)
- [ ] 仓位管理 (Kelly公式)
- [ ] 止损机制 (固定/ATR/移动/时间)
- [ ] 单元测试覆盖率 > 80%

---

### 🟡 研究员A: 策略优化

#### 1. 参数优化
```python
from scipy.optimize import differential_evolution

class StrategyOptimizer:
    def optimize_parameters(self, strategy_class, param_bounds, data):
        """
        使用差分进化算法优化策略参数
        
        param_bounds = {
            'ma_fast': (3, 10),
            'ma_slow': (15, 30),
            'rsi_threshold': (20, 40)
        }
        """
        def objective(params):
            strategy = strategy_class(*params)
            result = backtest_engine.run(strategy, data)
            # 优化目标: 夏普比率
            return -result['sharpe_ratio']
        
        bounds = list(param_bounds.values())
        result = differential_evolution(objective, bounds)
        
        return dict(zip(param_bounds.keys(), result.x))
```

#### 2. 策略组合
```python
class StrategyPortfolio:
    def __init__(self, strategies, weights=None):
        self.strategies = strategies
        self.weights = weights or [1/len(strategies)] * len(strategies)
        
    def calculate_signals(self, data):
        """组合策略信号"""
        signals = []
        for strategy, weight in zip(self.strategies, self.weights):
            signal = strategy.calculate_signals(data)
            signals.append(signal * weight)
        
        # 加权平均
        combined_signal = sum(signals)
        return combined_signal
```

**交付物:**
- [ ] 策略参数优化
- [ ] 策略组合方案
- [ ] 优化后回测报告

---

## Week 11-12: 集成测试 + 文档

### 全员: 系统集成测试

#### 1. 端到端测试
```python
def test_end_to_end_pipeline():
    """测试完整流程"""
    # 1. 数据获取
    data = data_loader.load('000001', '2020-01-01', '2025-12-31')
    
    # 2. 因子计算
    factors = factor_calculator.calculate(data)
    
    # 3. 策略信号
    strategy = MACrossStrategy(fast=5, slow=20)
    signals = strategy.calculate_signals(factors)
    
    # 4. 风控检查
    portfolio = Portfolio(initial_capital=1000000)
    risk_check = PreTradeRiskCheck(config)
    
    for signal in signals:
        passed, msg = risk_check.check(signal, portfolio)
        if passed:
            order = generate_order(signal)
            portfolio.add_order(order)
    
    # 5. 回测
    result = backtest_engine.run(strategy, data)
    
    # 6. 验证结果
    assert result['total_return'] > 0
    assert result['sharpe_ratio'] > 1.0
    assert result['max_drawdown'] < 0.20
```

#### 2. 性能测试
```python
def test_performance():
    """测试系统性能"""
    # 测试1000只股票池
    symbols = get_all_symbols()[:1000]
    
    start_time = time.time()
    
    for symbol in symbols:
        data = data_loader.load(symbol)
        factors = factor_calculator.calculate(data)
    
    elapsed = time.time() - start_time
    
    # 要求: 1000只股票 < 60秒
    assert elapsed < 60, f"性能不达标: {elapsed}秒"
```

#### 3. 压力测试
```python
def test_stress():
    """压力测试: 10年历史数据"""
    result = backtest_engine.run(
        strategy=strategy,
        start_date='2015-01-01',
        end_date='2025-12-31',
        initial_capital=1000000
    )
    
    # 验证回测完成且结果合理
    assert result is not None
    assert len(result['trades']) > 0
    assert result['final_capital'] > 0
```

---

### 全员: 文档编写

```markdown
docs/
├── architecture.md                 # 系统架构
├── api_reference.md               # API文档
├── strategy_guide.md              # 策略开发指南
├── factor_library.md              # 因子库文档
├── backtest_guide.md              # 回测使用指南
├── ml_guide.md                    # ML模块使用指南
└── deployment.md                  # 部署指南
```

#### 文档内容要求:
1. **架构文档**: 系统架构图、模块依赖、数据流
2. **API文档**: 所有公开接口的参数、返回值、示例
3. **策略指南**: 如何开发新策略、策略模板、最佳实践
4. **因子文档**: 所有因子的定义、计算方法、有效性
5. **回测指南**: 如何运行回测、参数说明、结果解读
6. **ML指南**: 特征工程、模型训练、模型评估
7. **部署指南**: 环境配置、依赖安装、启动流程

---

## 🔧 技术栈统一

```python
# requirements.txt

# 核心依赖
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0

# 数据源
akshare>=1.12.0
tushare>=1.2.0

# 回测框架 (可选)
backtrader>=1.9.0
zipline-reloaded>=2.0.0

# 机器学习
xgboost>=2.0.0
lightgbm>=4.0.0
scikit-learn>=1.3.0
optuna>=3.0.0

# 可视化
matplotlib>=3.7.0
seaborn>=0.12.0
plotly>=5.0.0

# 数据库
sqlalchemy>=2.0.0
pymysql>=1.0.0

# 测试
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0

# 工具
tqdm>=4.65.0
loguru>=0.7.0
pyyaml>=6.0
```

---

## 📋 每日站会 (Daily Standup)

**时间:** 每天早上10:00，15分钟

**格式:**
```
每人回答3个问题:
1. 昨天完成了什么？
2. 今天计划做什么？
3. 遇到什么阻塞？

示例:
开发A: 
  - 昨天: 完成了回测引擎的滑点模型
  - 今天: 实现涨跌停处理逻辑
  - 阻塞: 需要确认停牌数据的获取方式

研究员A:
  - 昨天: 实现了15个技术因子
  - 今天: 继续实现基本面因子
  - 阻塞: 无

开发B:
  - 昨天: 优化了因子计算性能
  - 今天: 开始风控系统开发
  - 阻塞: 需要研究员A提供因子有效性数据

研究员B:
  - 昨天: 完成了特征工程pipeline
  - 今天: 开始模型训练和交叉验证
  - 阻塞: 需要更多历史数据
```

---

## 🚨 风险管理

### 技术风险:
1. **回测引擎复杂度高** 
   - 缓解: 考虑使用成熟框架 (backtrader/zipline)
   - 备选: 简化版本先上线，后续迭代

2. **因子计算性能瓶颈**
   - 缓解: 使用numba/cython加速
   - 备选: 分布式计算 (Dask)

3. **数据质量问题**
   - 缓解: 多数据源交叉验证
   - 备选: 人工审核关键数据

### 进度风险:
1. **回测引擎延期** (关键路径)
   - 缓解: Week 3开始每日检查进度
   - 备选: 调配研究员B协助开发

2. **因子实现工作量大**
   - 缓解: 先实现20个核心因子
   - 备选: 其他因子后续补充

3. **ML模块复杂**
   - 缓解: 先实现基础版本
   - 备选: 后续迭代优化

### 协作风险:
1. **接口不一致**
   - 缓解: Week 1-2 统一接口定义
   - 备选: 每周接口评审

2. **代码冲突**
   - 缓解: Git分支管理，每日合并
   - 备选: 代码Review机制

3. **测试覆盖不足**
   - 缓解: 强制要求核心模块测试覆盖率 > 80%
   - 备选: 每周测试报告

---

## ✅ 验收标准

### 数据层:
- [ ] 支持多数据源 (akshare + tushare)
- [ ] 复权处理正确 (前复权/后复权)
- [ ] 数据质量检查完善
- [ ] 单元测试覆盖率 > 80%

### 因子库:
- [ ] 至少50个因子 (20技术+10基本面+20其他)
- [ ] 因子计算性能 < 1秒/股票
- [ ] 因子有效性验证 (IC > 0.03)
- [ ] 单元测试覆盖率 > 80%

### 回测引擎:
- [ ] 事件驱动架构
- [ ] 滑点/佣金/涨跌停/停牌处理
- [ ] 回测10年数据 < 30秒
- [ ] 单元测试 + 集成测试

### 策略层:
- [ ] 至少3个经典策略
- [ ] 策略回测报告完整
- [ ] 策略参数优化

### ML模块:
- [ ] 时间序列交叉验证
- [ ] 超参数优化
- [ ] 模型集成
- [ ] 模型评估报告 (准确率 > 60%)

### 风控系统:
- [ ] 预交易风控
- [ ] 仓位管理 (Kelly公式)
- [ ] 止损机制 (4种)
- [ ] 单元测试覆盖率 > 80%

---

## 💡 关键建议

1. **回测引擎是关键路径** - 必须在Week 4前完成
2. **因子库可以渐进式开发** - 先20个核心因子
3. **策略验证要严格** - 避免过拟合，使用时间序列CV
4. **代码质量要保证** - 核心模块测试覆盖率 > 80%
5. **文档要同步** - 边开发边写文档
6. **每日合并代码** - 避免大规模冲突
7. **技术选型要务实** - 优先使用成熟框架

---

**准备好了吗？Let's build it! 🚀**
