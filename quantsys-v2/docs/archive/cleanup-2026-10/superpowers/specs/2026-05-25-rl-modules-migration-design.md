# RL Modules Migration Design

**Date**: 2026-05-25  
**Author**: Claude (Opus 4.7)  
**Status**: Draft

## Executive Summary

This document specifies the migration of reinforcement learning (RL) modules from FinceptTerminal to quantsys-v2. The migration includes Qlib RL and FinRL frameworks, implementing them according to quantsys-v2's architecture standards with complete refactoring.

**Scope**: Core RL modules (Qlib RL + FinRL agents/environments)  
**Approach**: Complete refactoring with parallel development tracks  
**Timeline**: 13-20 days (single developer)  
**Test Coverage**: Minimum (<30%, critical paths only)

## Background

### Current State

**quantsys-v2 has:**
- ✅ BaseCalculator framework for quantitative calculations
- ✅ Dual anti-corruption layer architecture
- ✅ Pipeline pattern for composable stages
- ✅ ML modules (LSTM, Transformer, feature engineering)
- ❌ No reinforcement learning capabilities

**FinceptTerminal has:**
- 🎯 Qlib RL module (PPO, DQN, A2C, SAC, TD3)
- 🎯 FinRL complete framework (10 modules)
- 🎯 14 Qlib advanced modules
- 🎯 RDAgent system (4 modules)

### Migration Goals

1. **Completeness**: Migrate all core RL modules that quantsys-v2 lacks
2. **Architecture Compliance**: Full refactoring to match quantsys-v2 standards
3. **Framework Separation**: Organize by framework (Qlib vs FinRL)
4. **Extensibility**: Design for future expansion
5. **Minimal Testing**: Focus on critical paths only

## Architecture Design

### Directory Structure

```
quantsys-v2/
├── quantlib/
│   ├── rl/                            # Common RL infrastructure (NEW)
│   │   ├── __init__.py
│   │   ├── base_agent.py              # BaseRLAgent base class
│   │   ├── base_environment.py        # BaseRLEnvironment base class
│   │   ├── metrics.py                 # RL performance metrics
│   │   └── utils.py                   # RL utility functions
│   │
│   ├── qlib/                          # Qlib framework integration (NEW)
│   │   ├── __init__.py
│   │   ├── rl.py                      # Qlib RL agents
│   │   ├── environments.py            # Qlib trading environments
│   │   └── config.py                  # Qlib configuration
│   │
│   ├── finrl/                         # FinRL framework integration (NEW)
│   │   ├── __init__.py
│   │   ├── agents.py                  # FinRL agents (A2C, PPO, DDPG, SAC, TD3)
│   │   ├── environments.py            # 8 trading environments
│   │   ├── config.py                  # FinRL configuration
│   │   └── callbacks.py               # Training callbacks
│   │
│   └── ml/                            # Existing ML modules (unchanged)
│       └── ...
│
├── tests/
│   ├── test_rl_base.py                # RL base classes tests
│   ├── test_qlib_rl.py                # Qlib RL tests
│   ├── test_finrl_agents.py           # FinRL agents tests
│   ├── test_finrl_environments.py     # FinRL environments tests
│   └── test_integration_rl.py         # End-to-end integration tests
│
└── requirements.txt                    # Updated dependencies
```

### Module Responsibilities

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `quantlib/rl/base_agent.py` | RL agent base class, inherits BaseCalculator | BaseCalculator |
| `quantlib/rl/base_environment.py` | RL environment base class, Gymnasium interface | gymnasium |
| `quantlib/finrl/agents.py` | FinRL agent implementations (5 algorithms) | BaseRLAgent, stable-baselines3 |
| `quantlib/finrl/environments.py` | FinRL environment implementations (8 types) | BaseRLEnvironment, finrl |
| `quantlib/qlib/rl.py` | Qlib RL implementations (5 algorithms) | BaseRLAgent, qlib |
| `quantlib/qlib/environments.py` | Qlib trading environments | BaseRLEnvironment, qlib |

## Component Design

### 1. BaseRLAgent Class

**Purpose**: Unified base class for all RL agents, inheriting BaseCalculator to maintain architecture consistency.

**Key Features**:
- Inherits validation, logging, and metadata from BaseCalculator
- Extends with RL-specific methods: train, predict, save_model, load_model
- Standardized result format using `_create_result_dict`
- Training history tracking
- Model persistence management

**Interface**:
```python
class BaseRLAgent(BaseCalculator):
    def __init__(self, algorithm: str, model_dir: str, **kwargs)
    
    @abstractmethod
    def train(self, env, total_timesteps: int, **kwargs) -> Dict[str, Any]
    
    @abstractmethod
    def predict(self, observation, deterministic: bool) -> np.ndarray
    
    @abstractmethod
    def save_model(self, path: Optional[str]) -> str
    
    @abstractmethod
    def load_model(self, path: str)
    
    def evaluate(self, env, n_episodes: int) -> Dict[str, Any]
```

**Why inherit BaseCalculator?**
- ✅ Maintains architecture consistency across all quantlib modules
- ✅ Reuses validation, logging, and metadata infrastructure
- ✅ Standardized result format for all operations
- ✅ Avoids code duplication
- ❌ Alternative (separate base class) would fragment the architecture

### 2. BaseRLEnvironment Class

**Purpose**: Unified base class for all trading environments, following Gymnasium standard.

**Key Features**:
- Implements Gymnasium `gym.Env` interface
- Common trading environment state (cash, holdings, portfolio value)
- Transaction cost handling
- Standardized reset/step interface

**Interface**:
```python
class BaseRLEnvironment(gym.Env, ABC):
    def __init__(self, df: pd.DataFrame, initial_amount: float, transaction_cost: float)
    
    @abstractmethod
    def reset(self, seed: Optional[int]) -> Tuple[np.ndarray, Dict]
    
    @abstractmethod
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]
    
    @abstractmethod
    def _get_observation(self) -> np.ndarray
    
    @abstractmethod
    def _calculate_reward(self) -> float
```

### 3. FinRL Agent Implementation

**Purpose**: Wrapper around Stable-Baselines3 algorithms, adapted to quantsys-v2 architecture.

**Supported Algorithms**:
- **PPO** (Proximal Policy Optimization) - Most stable, general purpose
- **DQN** (Deep Q-Network) - Discrete action spaces
- **A2C** (Advantage Actor-Critic) - Fast baseline
- **SAC** (Soft Actor-Critic) - Entropy-regularized, robust
- **TD3** (Twin Delayed DDPG) - Continuous actions, improved DDPG

**Key Features**:
- Algorithm registry with default hyperparameters
- TensorBoard logging support
- Training callbacks for progress tracking
- Model save/load with training history
- Evaluation metrics

**Implementation Strategy**:
```python
class FinRLAgent(BaseRLAgent):
    ALGORITHM_MAP = {'ppo': PPO, 'dqn': DQN, 'a2c': A2C, 'sac': SAC, 'td3': TD3}
    DEFAULT_PARAMS = {...}  # Per-algorithm hyperparameters
    
    def train(self, env, total_timesteps, callback, **kwargs):
        # Create SB3 model
        # Train with callbacks
        # Save model
        # Evaluate
        # Return standardized result dict
```

### 4. FinRL Environment Implementations

**Purpose**: 8 specialized trading environments for different strategies.

**Environment Types**:
1. **StockTradingEnv** - Standard stock trading (buy/sell/hold)
2. **StockTradingEnvCashpenalty** - Penalizes excess cash holdings
3. **StockTradingEnvStopLoss** - Built-in stop-loss and profit-taking
4. **StockTradingEnvNP** - High-performance NumPy version
5. **StockPortfolioEnv** - Portfolio weight allocation
6. **PortfolioOptimizationEnv** - Advanced portfolio optimization
7. **CryptoEnv** - Multi-cryptocurrency trading
8. **BitcoinEnv** - Single BTC trading

**State Space Design**:
```
[cash, holding_1, holding_2, ..., price_1, price_2, ..., indicator_1, indicator_2, ...]
```

**Action Space Design**:
- Continuous: [-hmax, hmax] per stock (buy/sell quantity)
- Portfolio: [0, 1] weights summing to 1

**Reward Function**:
- Portfolio return: `(value_t - value_{t-1}) / value_{t-1}`
- Optional: Sharpe ratio, risk-adjusted returns

### 5. Qlib RL Implementation

**Purpose**: Integration with Microsoft Qlib quantitative platform.

**Key Features**:
- Qlib data integration
- Qlib simulator and trainer
- Order execution simulation
- Reward function customization

**Implementation Strategy**:
```python
class QlibRLAgent(BaseRLAgent):
    def __init__(self, algorithm, qlib_config, **kwargs):
        # Initialize Qlib
        # Create simulator
        # Setup trainer
    
    def train(self, env, total_timesteps, **kwargs):
        # Create Qlib simulator
        # Train with Qlib trainer
        # Return standardized result
```

**Qlib Components**:
- `Simulator`: Market simulation with order execution
- `Trainer`: Training loop management
- `Interpreter`: Strategy interpretation
- `Reward`: Custom reward functions

### 6. Qlib Environment Implementation

**Purpose**: Trading environment using Qlib data and execution simulator.

**Key Features**:
- Qlib data format support
- Order execution simulation
- Portfolio rebalancing
- Target position actions

**Action Space**: Target portfolio weights [0, 1]

**State Space**: Prices + positions + Qlib factors

## Implementation Strategy

### Parallel Development Approach

**Phase 1: Foundation (3-5 days)**
- Create directory structure
- Implement `BaseRLAgent` (inheriting BaseCalculator)
- Implement `BaseRLEnvironment`
- Add dependencies to requirements.txt
- Setup basic tests

**Phase 2: Parallel Development (7-10 days)**

**Track 1 - FinRL (Developer A or Time Slot 1)**:
1. Implement `FinRLAgent` class
2. Implement `StockTradingEnv` (primary environment)
3. Implement remaining 7 environments
4. Implement callbacks and config
5. Write tests for agents and environments

**Track 2 - Qlib RL (Developer B or Time Slot 2)**:
1. Implement `QlibRLAgent` class
2. Implement `QlibTradingEnv`
3. Integrate Qlib simulator and trainer
4. Implement config
5. Write tests for Qlib RL

**Phase 3: Integration (3-5 days)**
- Merge Track 1 and Track 2
- Resolve conflicts
- End-to-end integration tests
- Documentation and examples
- Performance validation

### Dependency Management

**New Dependencies** (add to requirements.txt):

```
# ===== Reinforcement Learning =====
gymnasium>=0.29.0                    # OpenAI Gym standard
stable-baselines3>=2.0.0             # RL algorithms
sb3-contrib>=2.0.0                   # Additional algorithms

# ===== Qlib Framework =====
pyqlib>=0.9.0                        # Microsoft Qlib

# ===== FinRL Framework =====
finrl>=0.3.6                         # Financial RL library

# ===== ML Infrastructure =====
torch>=2.0.0                         # PyTorch (SB3 dependency)
tensorboard>=2.13.0                  # Training visualization

# ===== Online Learning =====
river>=0.18.0                        # Incremental learning

# ===== Optimization =====
cvxpy>=1.3.0                         # Convex optimization

# ===== Experiment Tracking =====
mlflow>=2.5.0                        # ML experiment management
```

## Testing Strategy

### Minimum Coverage (<30%)

Focus on **critical paths only**:

1. **Base Classes** (`test_rl_base.py`)
   - BaseRLAgent initialization
   - BaseRLEnvironment interface

2. **FinRL Agents** (`test_finrl_agents.py`)
   - Agent creation
   - **Training (critical path)**
   - **Prediction (critical path)**

3. **FinRL Environments** (`test_finrl_environments.py`)
   - Environment creation
   - Reset functionality
   - **Step execution (critical path)**

4. **Qlib RL** (`test_qlib_rl.py`)
   - Agent creation
   - **Training (critical path)** - if Qlib available

5. **Integration** (`test_integration_rl.py`)
   - **End-to-end: data → train → predict → evaluate**
   - **Model save/load**

### Test Data Strategy

- Generate synthetic market data for tests
- 100-200 days of OHLCV data
- 2-3 stocks for multi-asset tests
- Avoid external data dependencies

### Skip Strategy

- Skip Qlib tests if Qlib not installed (`@pytest.mark.skipif`)
- Skip GPU tests if CUDA not available
- Skip long-running tests in CI

## Configuration Design

### FinRL Configuration

```python
# quantlib/finrl/config.py

DEFAULT_INDICATORS = [
    'macd', 'rsi_30', 'cci_30', 'dx_30',
    'close_30_sma', 'close_60_sma'
]

MODEL_DIR = '.pi-invest/rl_models/finrl'
TENSORBOARD_DIR = '.pi-invest/logs/tensorboard'

TRAINING_CONFIG = {
    'initial_amount': 1_000_000,
    'transaction_cost': 0.001,
    'reward_scaling': 1e-4,
    'hmax': 100
}
```

### Qlib Configuration

```python
# quantlib/qlib/config.py

QLIB_DATA_PATH = '~/.qlib/qlib_data/cn_data'
QLIB_REGION = 'cn'
MODEL_DIR = '.pi-invest/rl_models/qlib'

TRAINING_CONFIG = {
    'initial_amount': 1_000_000,
    'transaction_cost': 0.001
}
```

## Data Flow

### Training Flow

```
Market Data (DataFrame)
    ↓
Environment Creation (StockTradingEnv)
    ↓
Agent Creation (FinRLAgent/QlibRLAgent)
    ↓
Training Loop
    ├─ Observation → Policy Network → Action
    ├─ Environment Step → Reward
    ├─ Update Network Parameters
    └─ Callback (Progress, Logging)
    ↓
Model Save (.zip file)
    ↓
Evaluation (n episodes)
    ↓
Result Dict (standardized format)
```

### Prediction Flow

```
Trained Model (.zip file)
    ↓
Agent Load Model
    ↓
Environment Reset → Initial Observation
    ↓
Loop:
    Observation → Agent.predict() → Action
    Action → Environment.step() → Next Observation, Reward
    ↓
Portfolio Value Tracking
```

## Error Handling

### Graceful Degradation

1. **Missing Dependencies**:
   - Check `QLIB_RL_AVAILABLE` flag
   - Raise informative ImportError with installation instructions
   - Skip tests if dependencies missing

2. **Training Failures**:
   - Catch exceptions during training
   - Save partial models if possible
   - Log error details
   - Return error in result dict

3. **Environment Errors**:
   - Validate data format before environment creation
   - Handle edge cases (insufficient cash, invalid actions)
   - Clip actions to valid ranges

### Validation

- Validate data format (required columns: date, tic, OHLCV)
- Validate hyperparameters (positive values, valid ranges)
- Validate model paths before loading
- Validate action dimensions match environment

## Performance Considerations

### Training Performance

- **GPU Acceleration**: Use PyTorch GPU if available
- **Vectorized Environments**: Use `DummyVecEnv` for parallel training
- **Batch Size**: Tune for GPU memory
- **Checkpoint Frequency**: Save every N timesteps

### Memory Management

- **Data Loading**: Load data in chunks if too large
- **Replay Buffer**: Limit buffer size (default 100k)
- **Model Storage**: Compress models (.zip format)

### Scalability

- **Multi-Stock**: Support up to 100 stocks per environment
- **Long Training**: Support 1M+ timesteps
- **Model Size**: Keep models under 100MB

## Migration Checklist

### Phase 1: Foundation
- [ ] Create `quantlib/rl/` directory
- [ ] Implement `BaseRLAgent` class
- [ ] Implement `BaseRLEnvironment` class
- [ ] Add dependencies to requirements.txt
- [ ] Write base class tests

### Phase 2: FinRL Track
- [ ] Create `quantlib/finrl/` directory
- [ ] Implement `FinRLAgent` class
- [ ] Implement `StockTradingEnv`
- [ ] Implement 7 additional environments
- [ ] Implement callbacks and config
- [ ] Write FinRL tests

### Phase 3: Qlib Track
- [ ] Create `quantlib/qlib/` directory
- [ ] Implement `QlibRLAgent` class
- [ ] Implement `QlibTradingEnv`
- [ ] Integrate Qlib simulator
- [ ] Implement config
- [ ] Write Qlib tests

### Phase 4: Integration
- [ ] Merge both tracks
- [ ] Resolve conflicts
- [ ] End-to-end integration test
- [ ] Documentation
- [ ] Performance validation

## Future Expansion

### Deferred Modules (Post-Migration)

1. **FinRL Additional Modules**:
   - `finrl_backtest.py` - Backtesting utilities
   - `finrl_trading.py` - Paper/live trading
   - `finrl_data.py` - Data fetching
   - `finrl_portfolio.py` - Portfolio management
   - `finrl_ensemble.py` - Ensemble strategies
   - `finrl_plot.py` - Visualization

2. **Qlib Advanced Modules**:
   - `qlib_online_learning.py` - Incremental learning
   - `qlib_high_frequency.py` - HFT strategies
   - `qlib_meta_learning.py` - Meta-learning
   - `qlib_advanced_models.py` - Advanced neural networks
   - `qlib_portfolio_opt.py` - Portfolio optimization
   - `qlib_backtest.py` - Advanced backtesting

3. **RDAgent System**:
   - Hypothesis generation
   - Knowledge base
   - Proposal system
   - Research automation

### Extension Points

- **Custom Environments**: Easy to add new environment types
- **Custom Algorithms**: Easy to add new RL algorithms
- **Custom Rewards**: Pluggable reward functions
- **Custom Callbacks**: Extensible callback system

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dependency conflicts | High | Test in isolated environment first |
| Qlib installation issues | Medium | Make Qlib optional, skip tests if missing |
| GPU memory issues | Medium | Provide CPU fallback, tune batch sizes |
| Training instability | Medium | Use stable algorithms (PPO), tune hyperparameters |
| Integration conflicts | High | Parallel tracks with clear interfaces |

### Schedule Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Underestimated complexity | High | Parallel development to save time |
| Debugging time | Medium | Minimal test coverage, focus on critical paths |
| Dependency installation | Low | Document installation steps clearly |

## Success Criteria

### Functional Requirements

- ✅ BaseRLAgent and BaseRLEnvironment implemented
- ✅ FinRL agents (5 algorithms) working
- ✅ FinRL environments (8 types) working
- ✅ Qlib RL agent working
- ✅ Qlib environment working
- ✅ End-to-end training and prediction working
- ✅ Model save/load working

### Non-Functional Requirements

- ✅ Code follows quantsys-v2 architecture standards
- ✅ All modules inherit from appropriate base classes
- ✅ Standardized result format using `_create_result_dict`
- ✅ Minimum test coverage (<30%) achieved
- ✅ Dependencies documented in requirements.txt
- ✅ Configuration files created

### Performance Requirements

- ✅ Training 10k timesteps completes in <5 minutes (CPU)
- ✅ Prediction latency <100ms per action
- ✅ Model size <100MB per algorithm
- ✅ Memory usage <4GB during training

## Conclusion

This design provides a complete specification for migrating RL modules from FinceptTerminal to quantsys-v2. The parallel development approach balances speed and quality, while the complete refactoring ensures long-term maintainability and architecture consistency.

**Key Design Decisions**:
1. **BaseRLAgent inherits BaseCalculator** - Maintains architecture consistency
2. **Framework separation** - Qlib and FinRL in separate directories
3. **Parallel development** - Two independent tracks for faster delivery
4. **Minimal testing** - Focus on critical paths only
5. **Complete refactoring** - No direct code copying, full adaptation

**Next Steps**:
1. Review and approve this design document
2. Create implementation plan with detailed tasks
3. Begin Phase 1 (Foundation) implementation
