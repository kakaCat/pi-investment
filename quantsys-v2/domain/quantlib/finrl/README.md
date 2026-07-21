# FinRL Integration

## Overview

The FinRL module provides integration with the FinRL (Financial Reinforcement Learning) framework, specifically wrapping Stable-Baselines3 algorithms for quantitative trading. It offers a unified interface for training and deploying state-of-the-art RL algorithms in financial markets.

## Supported Algorithms

The module supports five popular RL algorithms from Stable-Baselines3:

| Algorithm | Type | Best For | Action Space |
|-----------|------|----------|--------------|
| **PPO** (Proximal Policy Optimization) | On-policy | General purpose, stable training | Discrete/Continuous |
| **A2C** (Advantage Actor-Critic) | On-policy | Fast training, sample efficient | Discrete/Continuous |
| **DDPG** (Deep Deterministic Policy Gradient) | Off-policy | Continuous control | Continuous only |
| **SAC** (Soft Actor-Critic) | Off-policy | Robust, exploration | Continuous only |
| **TD3** (Twin Delayed DDPG) | Off-policy | Stable continuous control | Continuous only |

## Architecture

```
quantlib/finrl/
├── base_rl_agent.py       # BaseRLAgent (shared with Qlib)
├── finrl_agent.py         # FinRLAgent - SB3 wrapper
├── finrl_environment.py   # StockTradingEnv - Trading environment
├── config.py              # Configuration and hyperparameters
├── callbacks.py           # Training callbacks
└── __init__.py
```

## Installation

```bash
# Install FinRL dependencies
pip install stable-baselines3>=2.0.0
pip install gymnasium>=0.29.0

# Optional: For advanced features
pip install tensorboard  # For training visualization
```

## Quick Start

### Basic Training Example

```python
from quantlib.finrl import FinRLAgent, StockTradingEnv
from quantlib.finrl.config import get_default_config
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
env = StockTradingEnv(
    df=df,
    initial_balance=100000,
    transaction_cost=0.001
)

# 3. Create agent
agent = FinRLAgent(algorithm='ppo', env=env)

# 4. Get configuration
config = get_default_config('ppo', training={'total_timesteps': 50000})

# 5. Train agent
result = agent.train(env=env, config=config)
print(f"Training completed: {result}")

# 6. Save model
agent.save_model('./models/ppo_trading_agent')

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
from quantlib.finrl import FinRLAgent, StockTradingEnv

# Create environment
env = StockTradingEnv(df=test_data, initial_balance=100000)

# Create agent and load model
agent = FinRLAgent(algorithm='ppo', env=env)
agent.load_model('./models/ppo_trading_agent')

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
from quantlib.finrl.config import get_default_config

# Get default PPO config
config = get_default_config('ppo')

# Customize training parameters
config = get_default_config(
    'ppo',
    training={
        'total_timesteps': 100000,
        'eval_freq': 5000,
        'save_freq': 10000,
        'log_interval': 10
    }
)

# Customize environment parameters
config = get_default_config(
    'ppo',
    env={
        'initial_balance': 50000,
        'transaction_cost': 0.002,
        'reward_scaling': 1.0
    }
)

# Customize algorithm hyperparameters
config = get_default_config(
    'ppo',
    learning_rate=1e-3,
    batch_size=128,
    n_steps=2048,
    gamma=0.99
)
```

### Algorithm-Specific Hyperparameters

#### PPO (Proximal Policy Optimization)

```python
config = get_default_config(
    'ppo',
    learning_rate=3e-4,      # Learning rate
    n_steps=2048,            # Steps per update
    batch_size=64,           # Minibatch size
    n_epochs=10,             # Optimization epochs
    gamma=0.99,              # Discount factor
    gae_lambda=0.95,         # GAE lambda
    clip_range=0.2           # PPO clip range
)
```

#### A2C (Advantage Actor-Critic)

```python
config = get_default_config(
    'a2c',
    learning_rate=7e-4,      # Learning rate
    n_steps=5,               # Steps per update
    gamma=0.99,              # Discount factor
    gae_lambda=1.0           # GAE lambda
)
```

#### DDPG (Deep Deterministic Policy Gradient)

```python
config = get_default_config(
    'ddpg',
    learning_rate=1e-3,      # Learning rate
    buffer_size=1000000,     # Replay buffer size
    learning_starts=100,     # Steps before learning
    batch_size=100,          # Minibatch size
    tau=0.005,               # Soft update coefficient
    gamma=0.99               # Discount factor
)
```

#### SAC (Soft Actor-Critic)

```python
config = get_default_config(
    'sac',
    learning_rate=3e-4,      # Learning rate
    buffer_size=1000000,     # Replay buffer size
    learning_starts=100,     # Steps before learning
    batch_size=256,          # Minibatch size
    tau=0.005,               # Soft update coefficient
    gamma=0.99               # Discount factor
)
```

#### TD3 (Twin Delayed DDPG)

```python
config = get_default_config(
    'td3',
    learning_rate=1e-3,      # Learning rate
    buffer_size=1000000,     # Replay buffer size
    learning_starts=100,     # Steps before learning
    batch_size=100,          # Minibatch size
    tau=0.005,               # Soft update coefficient
    gamma=0.99               # Discount factor
)
```

### Configuration Validation

```python
from quantlib.finrl.config import validate_config

config = get_default_config('ppo')
is_valid, errors = validate_config(config)

if not is_valid:
    print("Configuration errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Configuration is valid")
```

## Training Workflow

### 1. Data Preparation

```python
import pandas as pd

# Load your stock data
df = pd.read_csv('stock_data.csv')

# Ensure required columns exist
required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
assert all(col in df.columns for col in required_columns)

# Split into train/test
train_size = int(len(df) * 0.8)
train_df = df[:train_size]
test_df = df[train_size:]
```

### 2. Environment Setup

```python
from quantlib.finrl import StockTradingEnv

# Create training environment
train_env = StockTradingEnv(
    df=train_df,
    initial_balance=100000,
    transaction_cost=0.001  # 0.1% transaction cost
)

# Create test environment
test_env = StockTradingEnv(
    df=test_df,
    initial_balance=100000,
    transaction_cost=0.001
)
```

### 3. Agent Creation and Training

```python
from quantlib.finrl import FinRLAgent
from quantlib.finrl.config import get_default_config
from quantlib.finrl.callbacks import create_callbacks

# Create agent
agent = FinRLAgent(algorithm='ppo', env=train_env)

# Configure training
config = get_default_config(
    'ppo',
    training={
        'total_timesteps': 100000,
        'eval_freq': 5000,
        'save_freq': 10000,
        'log_interval': 10
    }
)

# Create callbacks for logging and checkpointing
callbacks = create_callbacks(
    log_dir='./logs/ppo',
    save_path='./models/checkpoints',
    eval_env=test_env,
    eval_freq=5000
)

# Train agent
result = agent.train(env=train_env, config=config, callbacks=callbacks)
print(f"Training completed: {result}")
```

### 4. Model Evaluation

```python
# Load best model
agent.load_model('./models/checkpoints/best_model')

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
initial_value = test_env.initial_balance
total_return = (final_value - initial_value) / initial_value * 100

print(f"Total Return: {total_return:.2f}%")
print(f"Final Portfolio Value: ${final_value:.2f}")
```

### 5. Hyperparameter Tuning

```python
from quantlib.finrl import FinRLAgent
from quantlib.finrl.config import get_default_config

# Define hyperparameter search space
learning_rates = [1e-4, 3e-4, 1e-3]
batch_sizes = [32, 64, 128]

best_reward = -float('inf')
best_config = None

for lr in learning_rates:
    for bs in batch_sizes:
        print(f"Testing lr={lr}, batch_size={bs}")
        
        # Create config
        config = get_default_config(
            'ppo',
            learning_rate=lr,
            batch_size=bs,
            training={'total_timesteps': 50000}
        )
        
        # Train agent
        agent = FinRLAgent(algorithm='ppo', env=train_env)
        result = agent.train(env=train_env, config=config)
        
        # Evaluate
        obs, _ = test_env.reset()
        done = False
        total_reward = 0
        
        while not done:
            action = agent.predict(obs)
            obs, reward, terminated, truncated, _ = test_env.step(action)
            total_reward += reward
            done = terminated or truncated
        
        # Track best
        if total_reward > best_reward:
            best_reward = total_reward
            best_config = config
            agent.save_model('./models/best_tuned_model')

print(f"Best config: {best_config}")
print(f"Best reward: {best_reward}")
```

## StockTradingEnv Documentation

### Overview

`StockTradingEnv` is a Gymnasium-compatible trading environment that simulates realistic stock trading with transaction costs and portfolio management.

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
- **Terminated**: Data exhausted (reached end of price history) OR portfolio value <= 0 (bankruptcy)
- **Truncated**: Never (no time limit by default)

### Constructor Parameters

```python
StockTradingEnv(
    df: pd.DataFrame,              # Price data with required columns
    initial_balance: float = 100000,  # Starting cash
    transaction_cost: float = 0.001   # Transaction fee (0.001 = 0.1%)
)
```

### Example Usage

```python
from quantlib.finrl import StockTradingEnv
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

# Create environment
env = StockTradingEnv(
    df=df,
    initial_balance=100000,
    transaction_cost=0.001
)

# Reset environment
obs, info = env.reset(seed=42)
print(f"Initial observation: {obs}")

# Take actions
for _ in range(10):
    action = env.action_space['n'] - 1  # Buy
    obs, reward, terminated, truncated, info = env.step(action)
    
    print(env.render())
    print(f"Reward: {reward:.2f}")
    
    if terminated or truncated:
        break

# Clean up
env.close()
```

## API Reference

### FinRLAgent

**Constructor:**
```python
FinRLAgent(
    algorithm: str,              # 'ppo', 'a2c', 'ddpg', 'sac', 'td3'
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

**validate_config:**
```python
validate_config(
    config: Dict[str, Any]
) -> Tuple[bool, List[str]]  # (is_valid, error_messages)
```

## Troubleshooting

### Common Issues

**1. ImportError: stable-baselines3 not found**
```bash
pip install stable-baselines3>=2.0.0
```

**2. Gym vs Gymnasium compatibility**
- This module uses Gymnasium (the maintained fork of OpenAI Gym)
- If you have old Gym code, update to Gymnasium API

**3. CUDA/GPU issues**
```python
# Force CPU usage if GPU causes issues
import torch
torch.set_num_threads(1)
```

**4. Training instability**
- Reduce learning rate
- Increase batch size
- Adjust reward scaling
- Try different algorithms (PPO is most stable)

**5. Poor performance**
- Increase training timesteps
- Tune hyperparameters
- Check data quality
- Verify environment reward function

## Performance Tips

1. **Use PPO for general trading** - Most stable and reliable
2. **Use SAC for exploration** - Better at discovering new strategies
3. **Normalize observations** - Scale features to similar ranges
4. **Tune reward function** - Experiment with different reward formulations
5. **Use callbacks** - Monitor training progress and save checkpoints
6. **Vectorize environments** - Train on multiple environments in parallel (advanced)

## Related Modules

- **Base RL Module** (`quantlib/rl/`) - Abstract base classes
- **Qlib Integration** (`quantlib/qlib/`) - Alternative RL framework
- **BaseCalculator** (`quantlib/base_calculator.py`) - Parent calculator class

## References

- [Stable-Baselines3 Documentation](https://stable-baselines3.readthedocs.io/)
- [Gymnasium Documentation](https://gymnasium.farama.org/)
- [FinRL Paper](https://arxiv.org/abs/2011.09607)

## Author

RL Migration Team

## Date

2026-05-25
