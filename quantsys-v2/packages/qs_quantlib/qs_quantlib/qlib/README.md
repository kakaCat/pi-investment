# Qlib RL Integration

## Overview

The Qlib RL module provides integration with Microsoft's Qlib (Quantitative Investment Library) reinforcement learning framework. It offers a unified interface for training and deploying RL-based quantitative trading strategies using Qlib's powerful data processing and model management capabilities.

## Supported Algorithms

The module supports multiple RL algorithms compatible with Qlib:

| Algorithm | Type | Best For | Action Space |
|-----------|------|----------|--------------|
| **PPO** (Proximal Policy Optimization) | On-policy | General purpose, stable | Discrete/Continuous |
| **DQN** (Deep Q-Network) | Off-policy | Discrete action spaces | Discrete only |
| **A2C** (Advantage Actor-Critic) | On-policy | Fast training | Discrete/Continuous |
| **SAC** (Soft Actor-Critic) | Off-policy | Continuous control | Continuous only |
| **TD3** (Twin Delayed DDPG) | Off-policy | Stable continuous control | Continuous only |

## Architecture

```
quantlib/qlib/
├── qlib_agent.py          # QlibRLAgent - Qlib RL wrapper
├── qlib_environment.py    # QlibTradingEnv - Trading environment
├── config.py              # Configuration and hyperparameters
└── __init__.py
```

## Installation

```bash
# Install Qlib and dependencies
pip install pyqlib
pip install torch>=1.9.0

# Optional: For GPU acceleration
pip install torch-cuda  # CUDA support
```

## Quick Start

### Basic Training Example

```python
from quantlib.qlib import QlibRLAgent, QlibTradingEnv
from quantlib.qlib.config import get_default_config
import pandas as pd
import numpy as np

# 1. Prepare data
df = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=252),
    'open': np.random.randn(252).cumsum() + 100,
    'high': np.random.randn(252).cumsum() + 101,
    'low': np.random.randn(252).cumsum() + 99,
    'close': np.random.randn(252).cumsum() + 100,
    'volume': np.random.randint(1000000, 10000000, 252)
})

# 2. Create environment
env = QlibTradingEnv(
    df=df,
    initial_capital=100000,
    transaction_cost=0.001,
    max_steps=None  # Use all data
)

# 3. Create agent
agent = QlibRLAgent(algorithm='ppo', env=env)

# 4. Get configuration
config = get_default_config('ppo')

# 5. Train agent
result = agent.train(env=env, config=config)
print(f"Training completed: {result}")

# 6. Save model
agent.save_model('./models/qlib_ppo_agent.pkl')

# 7. Test agent
obs, info = env.reset(seed=42)
done = False
total_reward = 0

while not done:
    action = agent.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward
    done = terminated or truncated
    print(env.render())

print(f"Total reward: {total_reward}")
env.close()
```

### Loading and Using a Trained Model

```python
from quantlib.qlib import QlibRLAgent, QlibTradingEnv

# Create environment
env = QlibTradingEnv(df=test_data, initial_capital=100000)

# Create agent and load model
agent = QlibRLAgent(algorithm='ppo', env=env)
agent.load_model('./models/qlib_ppo_agent.pkl')

# Use agent for trading
obs, info = env.reset()
done = False

while not done:
    action = agent.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    done = terminated or truncated
    
    # Get portfolio info
    print(f"Step: {info['step']}, Portfolio: ${info['portfolio_value']:.2f}")

env.close()
```

## Configuration Guide

### Default Configurations

Use `get_default_config()` to get algorithm-specific default settings:

```python
from quantlib.qlib.config import get_default_config

# Get default PPO config
config = get_default_config('ppo')

# Customize training parameters
config = get_default_config(
    'ppo',
    training={
        'total_timesteps': 100000,
        'eval_freq': 5000,
        'log_interval': 10
    }
)

# Customize environment parameters
config = get_default_config(
    'ppo',
    env={
        'initial_capital': 50000,
        'transaction_cost': 0.002,
        'max_steps': 1000
    }
)

# Customize algorithm hyperparameters
config = get_default_config(
    'ppo',
    learning_rate=1e-3,
    gamma=0.99,
    batch_size=128
)
```

### Algorithm-Specific Hyperparameters

#### PPO (Proximal Policy Optimization)

```python
config = get_default_config(
    'ppo',
    learning_rate=3e-4,      # Learning rate
    gamma=0.99,              # Discount factor
    batch_size=64,           # Minibatch size
    n_epochs=10,             # Optimization epochs
    clip_range=0.2           # PPO clip range
)
```

#### DQN (Deep Q-Network)

```python
config = get_default_config(
    'dqn',
    learning_rate=1e-4,      # Learning rate
    buffer_size=100000,      # Replay buffer size
    batch_size=32,           # Minibatch size
    gamma=0.99,              # Discount factor
    epsilon_start=1.0,       # Initial exploration rate
    epsilon_end=0.01,        # Final exploration rate
    epsilon_decay=0.995      # Exploration decay
)
```

#### A2C (Advantage Actor-Critic)

```python
config = get_default_config(
    'a2c',
    learning_rate=7e-4,      # Learning rate
    gamma=0.99,              # Discount factor
    n_steps=5                # Steps per update
)
```

#### SAC (Soft Actor-Critic)

```python
config = get_default_config(
    'sac',
    learning_rate=3e-4,      # Learning rate
    buffer_size=1000000,     # Replay buffer size
    batch_size=256,          # Minibatch size
    gamma=0.99,              # Discount factor
    tau=0.005                # Soft update coefficient
)
```

#### TD3 (Twin Delayed DDPG)

```python
config = get_default_config(
    'td3',
    learning_rate=1e-3,      # Learning rate
    buffer_size=1000000,     # Replay buffer size
    batch_size=100,          # Minibatch size
    gamma=0.99,              # Discount factor
    tau=0.005                # Soft update coefficient
)
```

## Training Workflow

### 1. Data Preparation with Qlib

```python
import pandas as pd
import qlib
from qlib.data import D

# Initialize Qlib
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data')

# Load data using Qlib
instruments = ['SH600000', 'SH600036']  # Stock codes
fields = ['$open', '$high', '$low', '$close', '$volume']
start_time = '2020-01-01'
end_time = '2023-12-31'

# Fetch data
df = D.features(instruments, fields, start_time, end_time)

# Convert to required format
df = df.reset_index()
df.columns = ['instrument', 'date', 'open', 'high', 'low', 'close', 'volume']

# Split into train/test
train_size = int(len(df) * 0.8)
train_df = df[:train_size]
test_df = df[train_size:]
```

### 2. Environment Setup

```python
from quantlib.qlib import QlibTradingEnv

# Create training environment
train_env = QlibTradingEnv(
    df=train_df,
    initial_capital=100000,
    transaction_cost=0.001,  # 0.1% transaction cost
    max_steps=None           # Use all data
)

# Create test environment
test_env = QlibTradingEnv(
    df=test_df,
    initial_capital=100000,
    transaction_cost=0.001,
    max_steps=None
)
```

### 3. Agent Creation and Training

```python
from quantlib.qlib import QlibRLAgent
from quantlib.qlib.config import get_default_config

# Create agent
agent = QlibRLAgent(algorithm='ppo', env=train_env)

# Configure training
config = get_default_config(
    'ppo',
    training={
        'total_timesteps': 100000,
        'eval_freq': 5000,
        'log_interval': 10
    }
)

# Train agent
result = agent.train(env=train_env, config=config)
print(f"Training completed: {result}")

# Save model
agent.save_model('./models/qlib_ppo_agent.pkl')
```

### 4. Model Evaluation

```python
# Load model
agent.load_model('./models/qlib_ppo_agent.pkl')

# Evaluate on test set
obs, info = test_env.reset(seed=42)
done = False
total_reward = 0
portfolio_values = []

while not done:
    action = agent.predict(obs)
    obs, reward, terminated, truncated, info = test_env.step(action)
    total_reward += reward
    portfolio_values.append(info['portfolio_value'])
    done = terminated or truncated

# Calculate metrics
final_value = portfolio_values[-1]
initial_value = test_env.initial_capital
total_return = (final_value - initial_value) / initial_value * 100

print(f"Total Return: {total_return:.2f}%")
print(f"Final Portfolio Value: ${final_value:.2f}")
```

### 5. Backtesting with Qlib

```python
import qlib
from qlib.backtest import backtest
from qlib.contrib.strategy import TopkDropoutStrategy

# Initialize Qlib
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data')

# Create strategy using trained agent
class RLStrategy(TopkDropoutStrategy):
    def __init__(self, agent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = agent
    
    def generate_trade_decision(self, execute_result=None):
        # Use RL agent to generate trading signals
        obs = self._get_observation()
        action = self.agent.predict(obs)
        
        # Convert action to trade decision
        # (implementation depends on your action space)
        return self._action_to_decision(action)

# Run backtest
strategy = RLStrategy(agent=agent)
report, positions = backtest(strategy, start_time='2023-01-01', end_time='2023-12-31')

print(report)
```

## QlibTradingEnv Documentation

### Overview

`QlibTradingEnv` is a Gymnasium-compatible trading environment designed for Qlib integration. It simulates realistic stock trading with transaction costs, portfolio management, and optional step limits.

### Action Space

**Discrete(3)**: Three possible actions
- `0` - Sell all holdings
- `1` - Hold (do nothing)
- `2` - Buy as many shares as possible with available balance

### Observation Space

**Box(8)**: Eight-dimensional continuous observation
- `[0]` - Open price
- `[1]` - High price
- `[2]` - Low price
- `[3]` - Close price
- `[4]` - Volume
- `[5]` - Cash balance
- `[6]` - Number of shares held
- `[7]` - Total portfolio value

### Reward

The reward is the change in portfolio value from the previous step:

```
reward = current_portfolio_value - previous_portfolio_value
```

Where:
```
portfolio_value = balance + holdings * current_price
```

### Episode Termination

An episode terminates when:
- **Terminated**: Data exhausted OR portfolio value <= 0 (bankruptcy)
- **Truncated**: max_steps reached (if configured)

### Constructor Parameters

```python
QlibTradingEnv(
    df: pd.DataFrame,                    # Price data with required columns
    initial_capital: float = 100000,     # Starting cash
    transaction_cost: float = 0.001,     # Transaction fee (0.001 = 0.1%)
    max_steps: Optional[int] = None      # Maximum steps per episode
)
```

### Example Usage

```python
from quantlib.qlib import QlibTradingEnv
import pandas as pd
import numpy as np

# Create sample data
df = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=100),
    'open': np.random.randn(100).cumsum() + 100,
    'high': np.random.randn(100).cumsum() + 101,
    'low': np.random.randn(100).cumsum() + 99,
    'close': np.random.randn(100).cumsum() + 100,
    'volume': np.random.randint(1000000, 10000000, 100)
})

# Create environment with step limit
env = QlibTradingEnv(
    df=df,
    initial_capital=100000,
    transaction_cost=0.001,
    max_steps=50  # Limit episode to 50 steps
)

# Reset environment
obs, info = env.reset(seed=42)
print(f"Initial observation: {obs}")

# Take actions
for _ in range(10):
    action = 2  # Buy
    obs, reward, terminated, truncated, info = env.step(action)
    
    print(env.render())
    print(f"Reward: {reward:.2f}")
    
    if terminated or truncated:
        break

# Clean up
env.close()
```

## API Reference

### QlibRLAgent

**Constructor:**
```python
QlibRLAgent(
    algorithm: str,              # 'ppo', 'dqn', 'a2c', 'sac', 'td3'
    env: Any,                    # Trading environment
    precision: int = 6,          # Decimal precision
    risk_free_rate: float = 0.0  # Risk-free rate
)
```

**Methods:**
- `train(env, config, callbacks=None) -> Dict[str, Any]` - Train the agent
- `predict(observation) -> np.ndarray` - Predict action
- `save_model(path: str)` - Save model to disk
- `load_model(path: str)` - Load model from disk

### QlibTradingEnv

**Constructor:**
```python
QlibTradingEnv(
    df: pd.DataFrame,
    initial_capital: float = 100000,
    transaction_cost: float = 0.001,
    max_steps: Optional[int] = None
)
```

**Methods:**
- `reset(seed=None, options=None) -> Tuple[np.ndarray, Dict]` - Reset environment
- `step(action) -> Tuple[np.ndarray, float, bool, bool, Dict]` - Execute action
- `render() -> str` - Render environment state
- `close()` - Clean up resources

### Configuration Functions

**get_default_config:**
```python
get_default_config(
    algorithm: str,                    # Algorithm name
    env: Dict[str, Any] | None = None, # Environment overrides
    training: Dict[str, Any] | None = None,  # Training overrides
    **kwargs: Any                      # Hyperparameter overrides
) -> Dict[str, Any]
```

## Integration with Qlib Ecosystem

### Using Qlib Data Handlers

```python
import qlib
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP

# Initialize Qlib
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data')

# Create data handler
handler = DataHandlerLP(
    instruments='csi300',
    start_time='2020-01-01',
    end_time='2023-12-31',
    fit_start_time='2020-01-01',
    fit_end_time='2021-12-31'
)

# Create dataset
dataset = DatasetH(handler=handler)

# Get data for RL training
train_data = dataset.prepare('train')
test_data = dataset.prepare('test')

# Convert to environment format
train_df = train_data.reset_index()
test_df = test_data.reset_index()
```

### Using Qlib Models with RL

```python
from qlib.contrib.model.pytorch_lstm import LSTMModel
from quantlib.qlib import QlibRLAgent

# Train Qlib model for feature extraction
qlib_model = LSTMModel()
qlib_model.fit(train_data)

# Use Qlib model features in RL agent
class RLAgentWithQlibFeatures(QlibRLAgent):
    def __init__(self, qlib_model, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.qlib_model = qlib_model
    
    def predict(self, observation):
        # Extract features using Qlib model
        features = self.qlib_model.predict(observation)
        
        # Use features for RL prediction
        action = super().predict(features)
        return action
```

## Troubleshooting

### Common Issues

**1. ImportError: qlib not found**
```bash
pip install pyqlib
```

**2. Qlib data not initialized**
```python
import qlib
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data')
```

**3. PyTorch CUDA issues**
```python
import torch
# Check CUDA availability
print(f"CUDA available: {torch.cuda.is_available()}")

# Force CPU if needed
device = torch.device('cpu')
```

**4. Data format issues**
- Ensure DataFrame has required columns: date, open, high, low, close, volume
- Check for NaN values and handle appropriately
- Verify date format is compatible

**5. Training instability**
- Reduce learning rate
- Increase batch size
- Adjust reward scaling
- Try different algorithms

## Performance Tips

1. **Use Qlib's data processing** - Leverage Qlib's efficient data handlers
2. **Feature engineering** - Combine Qlib features with RL
3. **Parallel training** - Use multiple environments for faster training
4. **Checkpointing** - Save models frequently during training
5. **Hyperparameter tuning** - Use Qlib's experiment management for systematic tuning

## Comparison: Qlib RL vs FinRL

| Feature | Qlib RL | FinRL |
|---------|---------|-------|
| **Framework** | Microsoft Qlib | Stable-Baselines3 |
| **Data Integration** | Native Qlib data handlers | Custom data loading |
| **Algorithms** | PPO, DQN, A2C, SAC, TD3 | PPO, A2C, DDPG, SAC, TD3 |
| **Backtesting** | Integrated Qlib backtest | Custom implementation |
| **Model Management** | Qlib experiment tracking | Manual tracking |
| **Best For** | Qlib ecosystem users | General RL applications |

## Related Modules

- **Base RL Module** (`quantlib/rl/`) - Abstract base classes
- **FinRL Integration** (`quantlib/finrl/`) - Alternative RL framework
- **BaseCalculator** (`quantlib/base_calculator.py`) - Parent calculator class

## References

- [Qlib Documentation](https://qlib.readthedocs.io/)
- [Qlib GitHub](https://github.com/microsoft/qlib)
- [Qlib Paper](https://arxiv.org/abs/2009.11189)

## Author

RL Migration Team

## Date

2026-05-25
