# Reinforcement Learning Module

## Overview

The RL module provides base infrastructure for reinforcement learning in quantitative trading strategies. It defines abstract base classes that establish a consistent interface for RL agents and trading environments across the QuantSys V2 system.

## Architecture

The module consists of two core abstract base classes:

```
quantlib/rl/
├── base_agent.py          # BaseRLAgent - Abstract RL agent class
├── base_environment.py    # BaseRLEnvironment - Abstract trading environment
└── __init__.py
```

### BaseRLAgent

Abstract base class for all RL agents. Inherits from `BaseCalculator` to integrate with the QuantSys calculation pipeline.

**Key Features:**
- Unified interface for training, prediction, and model persistence
- Integration with BaseCalculator for pipeline compatibility
- Support for both discrete and continuous action spaces
- Configurable precision and risk-free rate

**Abstract Methods:**
- `train(env, episodes, **kwargs)` - Train the agent
- `predict(observation, **kwargs)` - Predict action for observation
- `save_model(filepath)` - Save trained model to disk
- `load_model(filepath)` - Load trained model from disk

**Concrete Methods:**
- `calculate(observation, **kwargs)` - BaseCalculator interface adapter
- `get_supported_methods()` - Returns list of supported methods

### BaseRLEnvironment

Abstract base class for trading environments. Follows the Gymnasium (OpenAI Gym) interface standard.

**Key Features:**
- Standard RL environment interface (reset, step, render, close)
- Support for seeding for reproducibility
- Flexible action and observation space definitions
- Separation of terminated vs truncated episode endings

**Abstract Methods:**
- `reset(seed, options)` - Reset environment to initial state
- `step(action)` - Execute one step in the environment
- `render()` - Render environment state
- `close()` - Clean up resources

**Concrete Methods:**
- `seed(seed)` - Set random seed for reproducibility
- `_get_observation()` - Helper to get current observation

## Usage Examples

### Creating a Custom RL Agent

```python
from quantlib.rl.base_agent import BaseRLAgent
import numpy as np

class MyRLAgent(BaseRLAgent):
    def __init__(self, action_space, observation_space):
        super().__init__(
            precision=6,
            risk_free_rate=0.03,
            action_space=action_space,
            observation_space=observation_space
        )
        self.model = None  # Initialize your model here
    
    def train(self, env, episodes=1000, **kwargs):
        """Train the agent"""
        total_reward = 0
        
        for episode in range(episodes):
            obs, info = env.reset()
            done = False
            episode_reward = 0
            
            while not done:
                action = self.predict(obs)
                obs, reward, terminated, truncated, info = env.step(action)
                episode_reward += reward
                done = terminated or truncated
            
            total_reward += episode_reward
        
        return {
            'episodes': episodes,
            'total_reward': total_reward,
            'avg_reward': total_reward / episodes
        }
    
    def predict(self, observation, **kwargs):
        """Predict action for observation"""
        # Your prediction logic here
        if self.action_space['type'] == 'discrete':
            return np.random.randint(0, self.action_space['n'])
        else:
            return np.random.randn(self.action_space['shape'][0])
    
    def save_model(self, filepath):
        """Save model to disk"""
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(self.model, f)
        return True
    
    def load_model(self, filepath):
        """Load model from disk"""
        import pickle
        with open(filepath, 'rb') as f:
            self.model = pickle.load(f)
        return True
```

### Creating a Custom Trading Environment

```python
from quantlib.rl.base_environment import BaseRLEnvironment
import numpy as np
import pandas as pd

class MyTradingEnv(BaseRLEnvironment):
    def __init__(self, df, initial_balance=100000):
        super().__init__()
        self.df = df
        self.initial_balance = initial_balance
        
        # Define action space: 0=sell, 1=hold, 2=buy
        self.action_space = {'type': 'discrete', 'n': 3}
        
        # Define observation space
        self.observation_space = {
            'type': 'box',
            'shape': (5,),  # [price, volume, balance, holdings, portfolio_value]
            'low': np.array([0, 0, 0, 0, 0], dtype=np.float32),
            'high': np.array([np.inf] * 5, dtype=np.float32)
        }
        
        self.current_step = 0
        self.balance = initial_balance
        self.holdings = 0
    
    def reset(self, seed=None, options=None):
        """Reset environment to initial state"""
        if seed is not None:
            self.seed(seed)
        
        self.current_step = 0
        self.balance = self.initial_balance
        self.holdings = 0
        
        observation = self._get_observation()
        self.state = observation
        
        return observation, {'step': 0}
    
    def step(self, action):
        """Execute one step"""
        current_price = self.df.iloc[self.current_step]['close']
        
        # Execute action
        if action == 2:  # Buy
            shares = int(self.balance / current_price)
            self.holdings += shares
            self.balance -= shares * current_price
        elif action == 0:  # Sell
            self.balance += self.holdings * current_price
            self.holdings = 0
        
        # Move to next step
        self.current_step += 1
        
        # Calculate reward
        portfolio_value = self.balance + self.holdings * current_price
        reward = portfolio_value - self.initial_balance
        
        # Check if done
        terminated = self.current_step >= len(self.df)
        truncated = False
        
        observation = self._get_observation()
        self.state = observation
        
        info = {
            'step': self.current_step,
            'portfolio_value': portfolio_value
        }
        
        return observation, reward, terminated, truncated, info
    
    def _get_observation(self):
        """Get current observation"""
        if self.current_step >= len(self.df):
            step = len(self.df) - 1
        else:
            step = self.current_step
        
        row = self.df.iloc[step]
        current_price = row['close']
        portfolio_value = self.balance + self.holdings * current_price
        
        return np.array([
            current_price,
            row['volume'],
            self.balance,
            self.holdings,
            portfolio_value
        ], dtype=np.float32)
    
    def render(self):
        """Render environment state"""
        return f"Step: {self.current_step}, Balance: ${self.balance:.2f}, Holdings: {self.holdings}"
    
    def close(self):
        """Clean up resources"""
        self.state = None
```

### Using the Custom Agent and Environment

```python
import pandas as pd
import numpy as np

# Create sample data
df = pd.DataFrame({
    'date': pd.date_range('2024-01-01', periods=100),
    'close': np.random.randn(100).cumsum() + 100,
    'volume': np.random.randint(1000000, 10000000, 100)
})

# Create environment
env = MyTradingEnv(df, initial_balance=100000)

# Create agent
action_space = {'type': 'discrete', 'n': 3}
observation_space = {'type': 'box', 'shape': (5,)}
agent = MyRLAgent(action_space, observation_space)

# Train agent
results = agent.train(env, episodes=100)
print(f"Training completed: {results}")

# Save model
agent.save_model('./models/my_agent.pkl')

# Test agent
obs, info = env.reset(seed=42)
done = False
total_reward = 0

while not done:
    action = agent.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward
    done = terminated or truncated

print(f"Test episode reward: {total_reward}")

# Clean up
env.close()
```

## Integration with BaseCalculator

BaseRLAgent inherits from BaseCalculator, allowing RL agents to be used in the QuantSys calculation pipeline:

```python
# Use agent as a calculator
result = agent.calculate(observation)
action = result['value']
method = result['method']  # 'predict'
timestamp = result['timestamp']

# Get supported methods
methods = agent.get_supported_methods()  # ['predict', 'train']
```

## API Reference

### BaseRLAgent

**Constructor:**
```python
BaseRLAgent(
    precision: int = 6,
    risk_free_rate: float = 0.0,
    action_space: Optional[Dict[str, Any]] = None,
    observation_space: Optional[Dict[str, Any]] = None
)
```

**Abstract Methods:**
- `train(env, episodes: int = 1000, **kwargs) -> Dict[str, Any]`
- `predict(observation, **kwargs) -> Union[int, np.ndarray]`
- `save_model(filepath: str) -> bool`
- `load_model(filepath: str) -> bool`

**Concrete Methods:**
- `calculate(observation, **kwargs) -> Dict[str, Any]`
- `get_supported_methods() -> list[str]`

### BaseRLEnvironment

**Constructor:**
```python
BaseRLEnvironment()
```

**Abstract Methods:**
- `reset(seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict[str, Any]]`
- `step(action: Any) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]`
- `render() -> Any`
- `close()`

**Concrete Methods:**
- `seed(seed: int)`
- `_get_observation() -> np.ndarray`

## Design Principles

1. **Gymnasium Compatibility**: Follows the Gymnasium (OpenAI Gym) interface standard for maximum compatibility with existing RL libraries.

2. **Separation of Concerns**: Clear separation between agent logic (BaseRLAgent) and environment logic (BaseRLEnvironment).

3. **Framework Agnostic**: Base classes don't depend on specific RL frameworks (TensorFlow, PyTorch, etc.), allowing flexibility in implementation.

4. **Pipeline Integration**: BaseRLAgent inherits from BaseCalculator, enabling seamless integration with the QuantSys calculation pipeline.

5. **Reproducibility**: Built-in seeding support for reproducible experiments.

## Related Modules

- **FinRL Integration** (`quantlib/finrl/`) - Stable-Baselines3 wrapper for financial RL
- **Qlib Integration** (`quantlib/qlib/`) - Qlib RL framework wrapper
- **BaseCalculator** (`quantlib/base_calculator.py`) - Parent class for all calculators

## Author

RL Migration Team

## Date

2026-05-25
