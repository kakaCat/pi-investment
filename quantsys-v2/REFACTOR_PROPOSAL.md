# 🔧 V13/V14 重复代码重构方案

> 问题：V13 和 V14 存在大量重复代码，违反 DRY 原则
> 目标：统一架构，配置驱动，易于扩展到 V15/V16...

---

## 📊 当前问题分析

### 1️⃣ 重复的文件

| 文件类型 | V13 | V14 | 重复度 |
|---------|-----|-----|--------|
| API 路由 | `v13_trading.py` | `v14_trading.py` | ~90% |
| 定时任务 | `v13_trading_job.py` | `v14_trading_job.py` | ~85% |
| 策略包装 | `v13_strategy.py` | `v14_strategy.py` | ~80% |

### 2️⃣ 重复的逻辑

**相同部分**：
- ✅ 账户信息查询
- ✅ 持仓明细查询
- ✅ 手动调仓触发
- ✅ 每日检查流程
- ✅ 错误处理逻辑

**不同部分**：
- ⚠️ 账户名称（`default` vs `v14_simulation`）
- ⚠️ 模型路径（`v13_model.json` vs `v14_p0_model.json`）
- ⚠️ 策略参数（调仓周期、持仓数量等）

---

## 🎯 重构方案：配置驱动架构

### 核心思想

**一个核心交易引擎 + 多个配置文件 = 支持 N 个策略版本**

```
SimulationTrader（核心引擎）
    ↓
StrategyConfig（配置驱动）
    ├─ v13.yaml
    ├─ v14.yaml
    ├─ v15.yaml (未来)
    └─ v16.yaml (未来)
```

---

## 📋 重构步骤

### Step 1：统一配置格式

**创建**：`live_trading/configs/strategies/`

```yaml
# v13.yaml
strategy:
  name: "V13 XGBoost Multi-Factor"
  version: "1.0.0"
  account_name: "v13_simulation"
  
model:
  model_path: "live_trading/models/v13_model.json"
  factors_path: "live_trading/models/v13_valid_factors.json"
  
trading:
  rebalance_days: 5
  max_positions: 8
  max_position_pct: 0.85
  
risk:
  single_stock_stop_loss: -0.15
  portfolio_stop_loss: -0.20
  single_stock_weight: 0.15
  
schedule:
  hour: 15
  minute: 30
```

```yaml
# v14.yaml
strategy:
  name: "V14 XGBoost Multi-Factor P0"
  version: "2.0.0"
  account_name: "v14_simulation"
  
model:
  model_path: "live_trading/models/v14_p0_model.json"
  factors_path: "live_trading/models/v14_p0_valid_factors.json"
  
trading:
  rebalance_days: 7
  max_positions: 5
  max_position_pct: 0.90
  
risk:
  single_stock_stop_loss: -0.12
  portfolio_stop_loss: -0.20
  single_stock_weight: 0.18
  
schedule:
  hour: 15
  minute: 35
```

---

### Step 2：统一 API 路由

**重构前**：
```
adapters/inbound/api/routes/
├── v13_trading.py (200行，90%重复)
└── v14_trading.py (200行，90%重复)
```

**重构后**：
```
adapters/inbound/api/routes/
└── strategy_trading.py (100行，统一接口)
```

**新的统一 API**：

```python
# adapters/inbound/api/routes/strategy_trading.py
from flask import Blueprint, jsonify, request
from application.services.strategy_service import StrategyService

bp = Blueprint('strategy_trading', __name__, url_prefix='/api/strategy')

@bp.route('/<strategy_name>/account-info', methods=['GET'])
def get_account_info(strategy_name: str):
    """
    获取策略账户信息（统一接口）
    
    支持：
    - GET /api/strategy/v13/account-info
    - GET /api/strategy/v14/account-info
    - GET /api/strategy/v15/account-info (未来)
    """
    try:
        service = StrategyService()
        account = service.get_account_info(strategy_name)
        return jsonify({
            'success': True,
            'data': account
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<strategy_name>/positions', methods=['GET'])
def get_positions(strategy_name: str):
    """获取策略持仓（统一接口）"""
    service = StrategyService()
    positions = service.get_positions(strategy_name)
    return jsonify({'success': True, 'data': positions})


@bp.route('/<strategy_name>/rebalance', methods=['POST'])
def manual_rebalance(strategy_name: str):
    """手动调仓（统一接口）"""
    service = StrategyService()
    result = service.manual_rebalance(strategy_name)
    return jsonify({'success': True, 'data': result})


@bp.route('/<strategy_name>/daily-check', methods=['POST'])
def daily_check(strategy_name: str):
    """每日检查（统一接口）"""
    service = StrategyService()
    result = service.daily_check(strategy_name)
    return jsonify({'success': True, 'data': result})
```

**API 调用示例**：
```bash
# V13
curl http://localhost:5001/api/strategy/v13/account-info
curl -X POST http://localhost:5001/api/strategy/v13/rebalance

# V14
curl http://localhost:5001/api/strategy/v14/account-info
curl -X POST http://localhost:5001/api/strategy/v14/rebalance

# V15 (未来，无需修改代码)
curl http://localhost:5001/api/strategy/v15/account-info
```

---

### Step 3：统一定时任务

**重构前**：
```
infrastructure/jobs/
├── v13_trading_job.py (150行)
└── v14_trading_job.py (150行)
```

**重构后**：
```
infrastructure/jobs/
└── strategy_trading_job.py (80行，统一逻辑)
```

**新的统一定时任务**：

```python
# infrastructure/jobs/strategy_trading_job.py
import logging
from pathlib import Path
from application.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


def strategy_daily_check(strategy_name: str, **params):
    """
    策略每日检查（统一接口）
    
    Args:
        strategy_name: 策略名称（v13/v14/v15...）
        **params: 额外参数（可选覆盖配置）
    
    Example:
        strategy_daily_check('v13')
        strategy_daily_check('v14')
        strategy_daily_check('v15', enable_stop_loss=False)
    """
    logger.info(f"={'='*70}")
    logger.info(f"{strategy_name.upper()} 模拟交易每日检查开始")
    logger.info(f"{'='*70}")
    
    try:
        service = StrategyService()
        result = service.daily_check(strategy_name, **params)
        
        logger.info(f"\n执行结果:")
        logger.info(f"  策略: {strategy_name}")
        logger.info(f"  状态: {result['status']}")
        logger.info(f"  账户: {result['account_name']}")
        logger.info(f"  总资产: ¥{result['total_value']:,.2f}")
        logger.info(f"  持仓: {result['positions_count']}只")
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ {strategy_name.upper()} 每日检查完成")
        logger.info(f"{'='*70}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ {strategy_name.upper()} 每日检查失败: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'failed',
            'strategy': strategy_name,
            'error': str(e)
        }


# 便捷函数（向后兼容）
def v13_daily_check(**params):
    """V13每日检查（兼容旧调用）"""
    return strategy_daily_check('v13', **params)


def v14_daily_check(**params):
    """V14每日检查（兼容旧调用）"""
    return strategy_daily_check('v14', **params)
```

**调度器配置**：

```python
# scripts/init_scheduler.py（统一调度器）
from infrastructure.jobs.strategy_trading_job import strategy_daily_check
from application.services.strategy_service import StrategyService

# 自动发现所有策略并注册定时任务
service = StrategyService()
strategies = service.list_strategies()  # ['v13', 'v14', 'v15'...]

for strategy in strategies:
    config = service.get_config(strategy)
    
    scheduler.add_job(
        func=strategy_daily_check,
        args=[strategy],
        trigger='cron',
        hour=config['schedule']['hour'],
        minute=config['schedule']['minute'],
        id=f'{strategy}_daily_check'
    )
    
    print(f"✓ 已注册 {strategy} 定时任务: {config['schedule']['hour']}:{config['schedule']['minute']}")
```

---

### Step 4：统一策略服务

**新增**：`application/services/strategy_service.py`

```python
# application/services/strategy_service.py
import yaml
from pathlib import Path
from live_trading.simulation_trader import SimulationTrader
from adapters.outbound.repositories import SimulationORMRepository

class StrategyService:
    """策略服务（统一管理所有策略版本）"""
    
    def __init__(self):
        self.config_dir = Path('live_trading/configs/strategies')
        self.repo = SimulationORMRepository()
    
    def list_strategies(self) -> list:
        """列出所有可用策略"""
        configs = self.config_dir.glob('*.yaml')
        return [c.stem for c in configs]  # ['v13', 'v14', 'v15'...]
    
    def get_config(self, strategy_name: str) -> dict:
        """获取策略配置"""
        config_path = self.config_dir / f'{strategy_name}.yaml'
        if not config_path.exists():
            raise ValueError(f"策略配置不存在: {strategy_name}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_account_info(self, strategy_name: str) -> dict:
        """获取账户信息"""
        config = self.get_config(strategy_name)
        account_name = config['strategy']['account_name']
        
        # 查询数据库
        account = self.repo.get_account(account_name)
        positions = self.repo.get_all_positions(account_name)
        
        # 计算总资产
        position_value = sum(p.shares * p.current_price for p in positions)
        total_value = account.cash + position_value
        
        return {
            'strategy_name': strategy_name,
            'account_name': account_name,
            'total_value': total_value,
            'cash': account.cash,
            'position_value': position_value,
            'positions_count': len(positions),
            'cumulative_return': (total_value / 100000 - 1),
            'last_rebalance_date': account.last_rebalance_date,
            'config': config['strategy']
        }
    
    def get_positions(self, strategy_name: str) -> list:
        """获取持仓明细"""
        config = self.get_config(strategy_name)
        account_name = config['strategy']['account_name']
        positions = self.repo.get_all_positions(account_name)
        return [self._position_to_dict(p) for p in positions]
    
    def manual_rebalance(self, strategy_name: str) -> dict:
        """手动调仓"""
        config = self.get_config(strategy_name)
        
        trader = SimulationTrader()
        trader.account_name = config['strategy']['account_name']
        trader.model_path = config['model']['model_path']
        trader.factors_path = config['model']['factors_path']
        trader.load_model()
        
        result = trader.rebalance()
        
        return {
            'strategy': strategy_name,
            'status': 'success',
            'result': result
        }
    
    def daily_check(self, strategy_name: str, **params) -> dict:
        """每日检查"""
        config = self.get_config(strategy_name)
        
        trader = SimulationTrader()
        trader.account_name = config['strategy']['account_name']
        trader.model_path = config['model']['model_path']
        trader.factors_path = config['model']['factors_path']
        
        # 应用配置参数
        trader.rebalance_days = config['trading']['rebalance_days']
        trader.max_positions = config['trading']['max_positions']
        trader.stop_loss_pct = config['risk']['single_stock_stop_loss']
        
        trader.load_model()
        trader.run_daily_check()
        
        return {
            'strategy': strategy_name,
            'status': 'success',
            'account_name': trader.account_name,
            'total_value': trader._calculate_total_value_from_portfolio(),
            'cash': trader.cash,
            'positions_count': len(trader.portfolio)
        }
    
    def _position_to_dict(self, position) -> dict:
        """持仓对象转字典"""
        return {
            'symbol': position.symbol,
            'name': position.name,
            'shares': position.shares,
            'cost': position.cost,
            'current_price': position.current_price,
            'market_value': position.shares * position.current_price,
            'profit': (position.current_price - position.cost) * position.shares,
            'profit_pct': (position.current_price / position.cost - 1)
        }
```

---

## 📈 重构收益

### 代码减少

| 类型 | 重构前 | 重构后 | 减少 |
|------|--------|--------|------|
| API 路由 | 400行 (v13+v14) | 100行 | **-75%** |
| 定时任务 | 300行 (v13+v14) | 80行 | **-73%** |
| 策略包装 | 200行 (v13+v14) | 0行（配置化） | **-100%** |
| **总计** | **900行** | **180行** | **-80%** |

### 扩展性提升

**添加 V15 策略**：

**重构前**（需要修改 6 个文件）：
```
❌ 创建 v15_trading.py (200行)
❌ 创建 v15_trading_job.py (150行)
❌ 创建 v15_strategy.py (100行)
❌ 修改 server.py (注册路由)
❌ 创建 init_v15_scheduler.py
❌ 修改前端代码（新增v15页面）
```

**重构后**（仅需 1 个文件）：
```
✅ 创建 v15.yaml (30行)
✅ 自动注册API: /api/strategy/v15/*
✅ 自动注册定时任务
✅ 前端无需修改（统一接口）
```

---

## 🚀 实施计划

### Phase 1：创建统一服务层（1天）
- [ ] 创建 `StrategyService`
- [ ] 创建配置目录和 v13.yaml / v14.yaml
- [ ] 单元测试

### Phase 2：重构 API 层（1天）
- [ ] 创建统一路由 `strategy_trading.py`
- [ ] 保留 v13/v14 路由作为兼容层
- [ ] 集成测试

### Phase 3：重构定时任务（0.5天）
- [ ] 创建 `strategy_trading_job.py`
- [ ] 重构调度器初始化
- [ ] 向后兼容测试

### Phase 4：清理旧代码（0.5天）
- [ ] 标记 v13/v14 特定文件为 deprecated
- [ ] 更新文档
- [ ] 添加迁移指南

**总工作量**：3天

---

## ✅ 向后兼容

**保留旧 API**（渐进式迁移）：

```python
# adapters/inbound/api/routes/v13_trading.py (deprecated)
from .strategy_trading import bp as strategy_bp

# 兼容旧API
v13_bp = Blueprint('v13', __name__, url_prefix='/api/v13')

@v13_bp.route('/account-info', methods=['GET'])
def get_account_info():
    """旧接口（已废弃，请使用 /api/strategy/v13/account-info）"""
    return strategy_bp.get_account_info('v13')
```

---

## 📚 配置驱动的优势

### 1. 零代码添加新策略
```bash
# 添加 V15
cp live_trading/configs/strategies/v14.yaml v15.yaml
# 修改配置参数
# 完成！自动支持所有API和定时任务
```

### 2. 灵活的参数调整
```yaml
# 临时测试调仓周期从7天改为3天
trading:
  rebalance_days: 3  # 只改配置，无需改代码
```

### 3. A/B 测试
```yaml
# v14a.yaml（激进版）
risk:
  single_stock_stop_loss: -0.10
  
# v14b.yaml（保守版）
risk:
  single_stock_stop_loss: -0.15
```

### 4. 多环境配置
```
configs/strategies/
├── prod/
│   ├── v13.yaml
│   └── v14.yaml
├── test/
│   ├── v13.yaml (测试参数)
│   └── v14.yaml (测试参数)
└── dev/
    └── v15.yaml (开发中)
```

---

## 🎯 最终架构

```
┌────────────────────────────────────────────────┐
│           统一 API 接口                         │
│  /api/strategy/{v13|v14|v15}/account-info     │
│  /api/strategy/{v13|v14|v15}/rebalance        │
└───────────────┬────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│           StrategyService                      │
│  - list_strategies()                           │
│  - get_config(name)                            │
│  - get_account_info(name)                      │
│  - manual_rebalance(name)                      │
│  - daily_check(name)                           │
└───────────────┬────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│        配置文件（驱动层）                        │
│  configs/strategies/                           │
│  ├── v13.yaml                                  │
│  ├── v14.yaml                                  │
│  ├── v15.yaml                                  │
│  └── v16.yaml                                  │
└───────────────┬────────────────────────────────┘
                ↓
┌────────────────────────────────────────────────┐
│        SimulationTrader（核心引擎）            │
│  单一实例，配置驱动                             │
└────────────────────────────────────────────────┘
```

---

## 🎉 总结

**当前问题**：
- ❌ V13/V14 代码重复 80-90%
- ❌ 添加新版本需要修改 6+ 文件
- ❌ 维护成本高

**重构后**：
- ✅ 代码减少 80%
- ✅ 添加新版本只需 1 个配置文件
- ✅ 配置驱动，灵活可扩展
- ✅ 统一接口，易于测试
- ✅ 向后兼容，渐进式迁移

**下一步**：需要我立即开始实施这个重构方案吗？
