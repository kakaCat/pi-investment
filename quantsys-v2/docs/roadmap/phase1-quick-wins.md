# Phase 1: 快速提升 (2-3个月)

**目标**: 从85分提升到90分 (+5分)  
**时间**: 2-3个月  
**重点**: 补齐核心功能短板

---

## 任务清单

### 1. 风险管理增强 (+3分)

#### 1.1 VaR/CVaR计算 (2周)

**目标**: 实现多种VaR计算方法

**技术方案**:
```python
# quant/risk/var_calculator.py

class VaRCalculator:
    """Value at Risk 计算器"""
    
    def historical_var(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """历史模拟法"""
        return np.percentile(returns, (1 - confidence) * 100)
    
    def parametric_var(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """参数法 (假设正态分布)"""
        mean = np.mean(returns)
        std = np.std(returns)
        z_score = norm.ppf(1 - confidence)
        return mean + z_score * std
    
    def monte_carlo_var(self, returns: np.ndarray, confidence: float = 0.95, 
                        n_simulations: int = 10000) -> float:
        """蒙特卡洛模拟法"""
        # 拟合分布参数
        mu, sigma = norm.fit(returns)
        # 模拟未来收益
        simulated = np.random.normal(mu, sigma, n_simulations)
        return np.percentile(simulated, (1 - confidence) * 100)
    
    def cvar(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """条件VaR (Expected Shortfall)"""
        var = self.historical_var(returns, confidence)
        return returns[returns <= var].mean()

class RiskMetrics:
    """风险指标计算"""
    
    def calculate_all(self, portfolio_returns: pd.Series) -> dict:
        calculator = VaRCalculator()
        
        return {
            'var_95': calculator.historical_var(portfolio_returns, 0.95),
            'var_99': calculator.historical_var(portfolio_returns, 0.99),
            'cvar_95': calculator.cvar(portfolio_returns, 0.95),
            'cvar_99': calculator.cvar(portfolio_returns, 0.99),
            'max_drawdown': self._max_drawdown(portfolio_returns),
            'sharpe_ratio': self._sharpe_ratio(portfolio_returns),
            'sortino_ratio': self._sortino_ratio(portfolio_returns),
        }
```

**集成到Pipeline**:
```python
# quant/stages/risk_stage.py 增强

class RiskStage(PipelineStage):
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # 现有风控检查
        risk_checks = self._run_risk_checks(data)
        
        # 新增: VaR/CVaR计算
        if 'portfolio_returns' in data:
            risk_metrics = RiskMetrics().calculate_all(data['portfolio_returns'])
            data['risk_metrics'] = risk_metrics
        
        return data
```

**测试用例**:
```python
# tests/test_var_calculator.py

def test_historical_var():
    returns = np.random.normal(0.001, 0.02, 1000)
    calculator = VaRCalculator()
    var_95 = calculator.historical_var(returns, 0.95)
    assert var_95 < 0  # VaR应该是负数
    assert -0.05 < var_95 < 0  # 合理范围

def test_cvar_worse_than_var():
    returns = np.random.normal(0.001, 0.02, 1000)
    calculator = VaRCalculator()
    var = calculator.historical_var(returns, 0.95)
    cvar = calculator.cvar(returns, 0.95)
    assert cvar < var  # CVaR应该比VaR更差
```

**验收标准**:
- [ ] 实现3种VaR计算方法
- [ ] 实现CVaR计算
- [ ] 单元测试覆盖率 > 90%
- [ ] 性能: 1000个样本 < 10ms

---

#### 1.2 实时风险监控Dashboard (2周)

**目标**: 可视化实时风险指标

**技术方案**:
```python
# api/endpoints/risk_monitor.py

from fastapi import APIRouter, WebSocket
from services.risk_monitor_service import RiskMonitorService

router = APIRouter()

@router.websocket("/ws/risk-monitor")
async def risk_monitor_websocket(websocket: WebSocket):
    await websocket.accept()
    service = RiskMonitorService()
    
    while True:
        # 每秒推送风险指标
        metrics = await service.get_realtime_metrics()
        await websocket.send_json(metrics)
        await asyncio.sleep(1)

@router.get("/risk/metrics")
async def get_risk_metrics():
    """获取当前风险指标"""
    service = RiskMonitorService()
    return service.get_current_metrics()

@router.get("/risk/alerts")
async def get_risk_alerts():
    """获取风险告警"""
    service = RiskMonitorService()
    return service.get_active_alerts()
```

**前端Dashboard** (使用React + ECharts):
```typescript
// dashboard/src/pages/RiskMonitor.tsx

const RiskMonitor: React.FC = () => {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/risk-monitor');
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMetrics(data);
    };
    
    return () => ws.close();
  }, []);
  
  return (
    <div className="risk-monitor">
      <MetricsCard title="VaR (95%)" value={metrics?.var_95} />
      <MetricsCard title="CVaR (95%)" value={metrics?.cvar_95} />
      <MetricsCard title="最大回撤" value={metrics?.max_drawdown} />
      <AlertPanel alerts={metrics?.alerts} />
      <PositionChart positions={metrics?.positions} />
    </div>
  );
};
```

**验收标准**:
- [ ] WebSocket实时推送 (1秒更新)
- [ ] 显示VaR/CVaR/最大回撤
- [ ] 风险告警面板
- [ ] 仓位分布图表

---

#### 1.3 风险归因分析 (1周)

**目标**: 分析风险来源

**技术方案**:
```python
# quant/risk/attribution.py

class RiskAttribution:
    """风险归因分析"""
    
    def factor_attribution(self, portfolio_returns: pd.Series, 
                          factor_returns: pd.DataFrame) -> pd.DataFrame:
        """因子归因"""
        # 多因子回归
        from sklearn.linear_model import LinearRegression
        
        model = LinearRegression()
        model.fit(factor_returns, portfolio_returns)
        
        # 计算每个因子的贡献
        factor_contributions = {}
        for i, factor_name in enumerate(factor_returns.columns):
            beta = model.coef_[i]
            factor_var = factor_returns[factor_name].var()
            contribution = beta * factor_var
            factor_contributions[factor_name] = contribution
        
        return pd.DataFrame(factor_contributions, index=['contribution'])
    
    def sector_attribution(self, holdings: List[Dict]) -> pd.DataFrame:
        """行业归因"""
        sector_risk = {}
        for holding in holdings:
            sector = holding['sector']
            position_value = holding['value']
            volatility = holding['volatility']
            risk = position_value * volatility
            
            if sector not in sector_risk:
                sector_risk[sector] = 0
            sector_risk[sector] += risk
        
        return pd.DataFrame(sector_risk, index=['risk'])
```

**验收标准**:
- [ ] 因子归因实现
- [ ] 行业归因实现
- [ ] 归因报告生成

---

#### 1.4 压力测试场景库 (1周)

**目标**: 模拟极端市场情况

**技术方案**:
```python
# quant/risk/stress_test_scenarios.py

class StressTestScenarios:
    """压力测试场景库"""
    
    SCENARIOS = {
        '2008_financial_crisis': {
            'name': '2008金融危机',
            'market_drop': -0.50,  # 市场下跌50%
            'volatility_spike': 3.0,  # 波动率上升3倍
            'correlation_increase': 0.9,  # 相关性上升到0.9
        },
        '2015_china_crash': {
            'name': '2015中国股灾',
            'market_drop': -0.45,
            'volatility_spike': 2.5,
            'correlation_increase': 0.85,
        },
        '2020_covid_crash': {
            'name': '2020新冠暴跌',
            'market_drop': -0.35,
            'volatility_spike': 2.0,
            'correlation_increase': 0.8,
        },
        'flash_crash': {
            'name': '闪电崩盘',
            'market_drop': -0.10,
            'volatility_spike': 5.0,
            'duration_minutes': 30,
        },
    }
    
    def run_scenario(self, portfolio: Portfolio, scenario_name: str) -> dict:
        """运行压力测试场景"""
        scenario = self.SCENARIOS[scenario_name]
        
        # 模拟市场冲击
        shocked_portfolio = self._apply_shock(portfolio, scenario)
        
        # 计算损失
        loss = shocked_portfolio.value - portfolio.value
        loss_pct = loss / portfolio.value
        
        return {
            'scenario': scenario['name'],
            'loss': loss,
            'loss_pct': loss_pct,
            'var_breach': loss < portfolio.var_95,
        }
```

**验收标准**:
- [ ] 4个历史场景实现
- [ ] 自定义场景支持
- [ ] 压力测试报告

---

### 2. 代码质量提升 (+2分)

#### 2.1 代码规范检查 (3天)

**配置文件**:
```ini
# .pylintrc
[MASTER]
max-line-length=100
disable=C0111,C0103

[MESSAGES CONTROL]
enable=all
disable=missing-docstring,invalid-name

# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py310']

[tool.isort]
profile = "black"
line_length = 100
```

**Pre-commit配置**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
```

**CI集成**:
```yaml
# .github/workflows/code-quality.yml
name: Code Quality

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install pylint flake8 black isort mypy
      - run: black --check .
      - run: flake8 .
      - run: pylint quant/
      - run: mypy quant/
```

**验收标准**:
- [ ] pylint评分 > 9.0
- [ ] flake8零错误
- [ ] black格式化通过
- [ ] mypy类型检查通过

---

#### 2.2 API文档生成 (2天)

**Sphinx配置**:
```python
# docs/conf.py
project = 'QuantSys-V2'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_rtd_theme',
]
html_theme = 'sphinx_rtd_theme'
```

**文档字符串规范**:
```python
def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.03) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率，默认3%
    
    Returns:
        夏普比率
    
    Raises:
        ValueError: 当收益率序列为空时
    
    Examples:
        >>> returns = pd.Series([0.01, 0.02, -0.01, 0.03])
        >>> calculate_sharpe_ratio(returns)
        1.23
    
    Note:
        使用年化收益率和年化波动率计算
    """
    if len(returns) == 0:
        raise ValueError("收益率序列不能为空")
    
    excess_returns = returns - risk_free_rate / 252
    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)
```

**验收标准**:
- [ ] 所有公共API有docstring
- [ ] Sphinx文档生成成功
- [ ] 文档托管到ReadTheDocs

---

#### 2.3 代码复杂度监控 (1天)

**工具集成**:
```bash
# 安装工具
pip install radon mccabe

# 检查圈复杂度
radon cc quant/ -a -nb

# 检查可维护性指数
radon mi quant/ -nb
```

**CI集成**:
```yaml
# .github/workflows/complexity.yml
- name: Check Complexity
  run: |
    radon cc quant/ -a -nb --total-average
    radon mi quant/ -nb --min B
```

**验收标准**:
- [ ] 平均圈复杂度 < 10
- [ ] 可维护性指数 > B
- [ ] 无F级函数

---

## 时间表

| 周次 | 任务 | 负责人 | 状态 |
|------|------|--------|------|
| W1 | VaR/CVaR实现 | - | 🔲 |
| W2 | VaR/CVaR测试 | - | 🔲 |
| W3 | 风险监控Dashboard | - | 🔲 |
| W4 | 风险监控测试 | - | 🔲 |
| W5 | 风险归因 + 压力测试 | - | 🔲 |
| W6 | 代码规范检查 | - | 🔲 |
| W7 | API文档生成 | - | 🔲 |
| W8 | 代码复杂度优化 | - | 🔲 |
| W9-10 | 集成测试 + Bug修复 | - | 🔲 |

---

## 验收标准

### 功能验收
- [ ] VaR/CVaR计算准确性验证
- [ ] 风险监控Dashboard可用
- [ ] 风险归因报告生成
- [ ] 压力测试场景运行

### 质量验收
- [ ] 单元测试覆盖率 > 85%
- [ ] pylint评分 > 9.0
- [ ] API文档完整度 100%
- [ ] 代码复杂度达标

### 性能验收
- [ ] VaR计算 < 10ms
- [ ] 风险监控延迟 < 1s
- [ ] Dashboard加载 < 2s

---

## 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| VaR计算性能不足 | 中 | 高 | 使用NumPy优化，考虑Numba加速 |
| Dashboard前端复杂 | 低 | 中 | 使用现成组件库 |
| 文档编写耗时 | 高 | 低 | 使用AI辅助生成 |

---

## 下一步

完成Phase 1后，进入[Phase 2: 核心能力提升](./phase2-core-capabilities.md)
