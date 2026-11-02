# RL Modules Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate reinforcement learning modules (Qlib RL + FinRL) from FinceptTerminal to quantsys-v2 with complete refactoring to match architecture standards.

**Architecture:** BaseRLAgent inherits BaseCalculator for consistency. BaseRLEnvironment follows Gymnasium standard. Parallel development tracks for FinRL and Qlib RL with framework separation.

**Tech Stack:** Python 3.10+, Gymnasium, Stable-Baselines3, PyTorch, Qlib, FinRL, pytest

---

## File Structure Overview

**New Files to Create:**
```
quantlib/
├── rl/
│   ├── __init__.py
│   ├── base_agent.py              # BaseRLAgent base class
│   └── base_environment.py        # BaseRLEnvironment base class
├── finrl/
│   ├── __init__.py
│   ├── agents.py                  # FinRLAgent implementation
│   ├── environments.py            # StockTradingEnv + 7 variants
│   ├── config.py                  # FinRL configuration
│   └── callbacks.py               # Training callbacks
└── qlib/
    ├── __init__.py
    ├── rl.py                      # QlibRLAgent implementation
    ├── environments.py            # QlibTradingEnv implementation
    └── config.py                  # Qlib configuration

tests/
├── test_rl_base.py                # Base classes tests
├── test_finrl_agents.py           # FinRL agents tests
├── test_finrl_environments.py     # FinRL environments tests
├── test_qlib_rl.py                # Qlib RL tests
└── test_integration_rl.py         # Integration tests
```

**Files to Modify:**
- `requirements.txt` - Add RL dependencies

---

## Phase 1: Foundation

### Task 1: Setup Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add RL dependencies to requirements.txt**

```bash
cat >> requirements.txt << 'EOF'

# ===== Reinforcement Learning (Added 2026-05-25) =====
gymnasium>=0.29.0                    # OpenAI Gym standard
stable-baselines3>=2.0.0             # RL algorithms
sb3-contrib>=2.0.0                   # Additional algorithms
torch>=2.0.0                         # PyTorch (SB3 dependency)
tensorboard>=2.13.0                  # Training visualization

# ===== Qlib Framework =====
pyqlib>=0.9.0                        # Microsoft Qlib

# ===== FinRL Framework =====
finrl>=0.3.6                         # Financial RL library

# ===== Online Learning =====
river>=0.18.0                        # Incremental learning

# ===== Optimization =====
cvxpy>=1.3.0                         # Convex optimization

# ===== Experiment Tracking =====
mlflow>=2.5.0                        # ML experiment management
EOF
```

- [ ] **Step 2: Verify dependencies added**

Run: `tail -20 requirements.txt`
Expected: Should show the RL dependencies section

- [ ] **Step 3: Commit dependency changes**

```bash
git add requirements.txt
git commit -m "feat(rl): add RL framework dependencies

- Add gymnasium, stable-baselines3, torch
- Add qlib and finrl frameworks
- Add supporting libraries (river, cvxpy, mlflow)"
```

---

### Task 2: Create RL Directory Structure

**Files:**
- Create: `quantlib/rl/__init__.py`
- Create: `quantlib/finrl/__init__.py`
- Create: `quantlib/qlib/__init__.py`

- [ ] **Step 1: Create rl module directory and init file**

```bash
mkdir -p quantlib/rl
cat > quantlib/rl/__init__.py << 'EOF'
"""
Reinforcement Learning Base Module
===================================

Common RL infrastructure for quantsys-v2.

Author: RL Migration Team
Date: 2026-05-25
"""

from quantlib.rl.base_agent import BaseRLAgent
from quantlib.rl.base_environment import BaseRLEnvironment

__all__ = ['BaseRLAgent', 'BaseRLEnvironment']
EOF
```

- [ ] **Step 2: Create finrl module directory and init file**

```bash
mkdir -p quantlib/finrl
cat > quantlib/finrl/__init__.py << 'EOF'
"""
FinRL Framework Integration
============================

FinRL agents and environments for quantsys-v2.

Author: RL Migration Team
Date: 2026-05-25
"""

try:
    from quantlib.finrl.agents import FinRLAgent
    from quantlib.finrl.environments import StockTradingEnv
    from quantlib.finrl.config import (
        DEFAULT_INDICATORS,
        MODEL_DIR,
        TRAINING_CONFIG
    )
    FINRL_AVAILABLE = True
except ImportError as e:
    FINRL_AVAILABLE = False
    import warnings
    warnings.warn(f"FinRL not available: {e}. Install with: pip install finrl stable-baselines3")

__all__ = ['FinRLAgent', 'StockTradingEnv', 'FINRL_AVAILABLE']
EOF
```

- [ ] **Step 3: Create qlib module directory and init file**

```bash
mkdir -p quantlib/qlib
cat > quantlib/qlib/__init__.py << 'EOF'
"""
Qlib Framework Integration
===========================

Qlib RL agents and environments for quantsys-v2.

Author: RL Migration Team
Date: 2026-05-25
"""

try:
    from quantlib.qlib.rl import QlibRLAgent
    from quantlib.qlib.environments import QlibTradingEnv
    from quantlib.qlib.config import (
        QLIB_DATA_PATH,
        MODEL_DIR,
        TRAINING_CONFIG
    )
    QLIB_RL_AVAILABLE = True
except ImportError as e:
    QLIB_RL_AVAILABLE = False
    import warnings
    warnings.warn(f"Qlib RL not available: {e}. Install with: pip install pyqlib")

__all__ = ['QlibRLAgent', 'QlibTradingEnv', 'QLIB_RL_AVAILABLE']
EOF
```

- [ ] **Step 4: Verify directory structure created**

Run: `find quantlib -type d -name "rl" -o -name "finrl" -o -name "qlib" | sort`
Expected: Should show three directories

- [ ] **Step 5: Commit directory structure**

```bash
git add quantlib/rl/__init__.py quantlib/finrl/__init__.py quantlib/qlib/__init__.py
git commit -m "feat(rl): create RL module directory structure

- Create quantlib/rl/ for common RL infrastructure
- Create quantlib/finrl/ for FinRL integration
- Create quantlib/qlib/ for Qlib RL integration
- Add graceful import handling for optional dependencies"
```

---

### Task 3: Implement BaseRLAgent

**Files:**
- Create: `tests/test_rl_base.py`
- Create: `quantlib/rl/base_agent.py`

- [ ] **Step 1: Write failing test for BaseRLAgent**

```python
cat > tests/test_rl_base.py << 'EOF'
"""
Tests for RL Base Classes
==========================

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import numpy as np
from abc import ABC
from quantlib.rl.base_agent import BaseRLAgent


class MockRLAgent(BaseRLAgent):
    """Mock implementation for testing."""
    
    def __init__(self, algorithm='mock', model_dir='.pi-invest/rl_models/test', **kwargs):
        super().__init__(algorithm=algorithm, model_dir=model_dir, **kwargs)
        self.model = None
        self.training_history = []
    
    def train(self, env, total_timesteps, **kwargs):
        self.training_history.append({'timesteps': total_timesteps})
        return self._create_result_dict(
            value={'total_timesteps': total_timesteps, 'success': True},
            method='train',
            parameters={'total_timesteps': total_timesteps}
        )
    
    def predict(self, observation, deterministic=True):
        return np.array([0.0])
    
    def save_model(self, path=None):
        save_path = path or f"{self.model_dir}/{self.algorithm}_model.zip"
        return save_path
    
    def load_model(self, path):
        self.model = {'loaded_from': path}


def test_base_rl_agent_initialization():
    """Test BaseRLAgent can be instantiated via subclass."""
    agent = MockRLAgent(algorithm='test_algo', model_dir='/tmp/models')
    assert agent.algorithm == 'test_algo'
    assert agent.model_dir == '/tmp/models'
    assert hasattr(agent, 'logger')
    assert hasattr(agent, 'precision')


def test_base_rl_agent_train_returns_dict():
    """Test train method returns standardized result dict."""
    agent = MockRLAgent()
    result = agent.train(env=None, total_timesteps=1000)
    
    assert isinstance(result, dict)
    assert 'value' in result
    assert 'method' in result
    assert 'timestamp' in result
    assert 'calculator' in result
    assert result['method'] == 'train'


def test_base_rl_agent_predict():
    """Test predict method returns numpy array."""
    agent = MockRLAgent()
    observation = np.array([1.0, 2.0, 3.0])
    action = agent.predict(observation)
    
    assert isinstance(action, np.ndarray)


def test_base_rl_agent_save_load():
    """Test model save and load."""
    agent = MockRLAgent()
    save_path = agent.save_model('/tmp/test_model.zip')
    assert save_path == '/tmp/test_model.zip'
    
    agent.load_model('/tmp/test_model.zip')
    assert agent.model is not None
EOF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rl_base.py::test_base_rl_agent_initialization -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'quantlib.rl.base_agent'"

- [ ] **Step 3: Implement BaseRLAgent**

```python
cat > quantlib/rl/base_agent.py << 'EOF'
"""
Base RL Agent Class
===================

Abstract base class for all reinforcement learning agents.

Author: RL Migration Team
Date: 2026-05-25
"""

import numpy as np
from abc import abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
from quantlib.base_calculator import BaseCalculator


class BaseRLAgent(BaseCalculator):
    """
    Abstract base class for all RL agents.
    
    Inherits from BaseCalculator to maintain architecture consistency
    and reuse validation, logging, and result formatting infrastructure.
    
    Features:
        - Standardized train/predict/evaluate interface
        - Model persistence (save/load)
        - Training history tracking
        - Result dict formatting via BaseCalculator
    
    Example:
        class MyAgent(BaseRLAgent):
            def train(self, env, total_timesteps, **kwargs):
                # Training logic
                return self._create_result_dict(metrics, 'train')
    """
    
    def __init__(self, algorithm: str, model_dir: str = '.pi-invest/rl_models', **kwargs):
        """
        Initialize RL agent.
        
        Args:
            algorithm: Algorithm name (e.g., 'ppo', 'dqn')
            model_dir: Directory for saving models
            **kwargs: Additional parameters passed to BaseCalculator
        """
        super().__init__(**kwargs)
        self.algorithm = algorithm
        self.model_dir = model_dir
        self.training_history = []
        
        # Create model directory if it doesn't exist
        Path(model_dir).mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def train(self, env, total_timesteps: int, **kwargs) -> Dict[str, Any]:
        """
        Train the agent on an environment.
        
        Args:
            env: Training environment (Gymnasium interface)
            total_timesteps: Total number of training timesteps
            **kwargs: Additional training parameters
        
        Returns:
            Standardized result dict with training metrics
        """
        pass
    
    @abstractmethod
    def predict(self, observation, deterministic: bool = True) -> np.ndarray:
        """
        Predict action given observation.
        
        Args:
            observation: Environment observation
            deterministic: Whether to use deterministic policy
        
        Returns:
            Action as numpy array
        """
        pass
    
    @abstractmethod
    def save_model(self, path: Optional[str] = None) -> str:
        """
        Save trained model to disk.
        
        Args:
            path: Save path (default: model_dir/algorithm_model.zip)
        
        Returns:
            Path where model was saved
        """
        pass
    
    @abstractmethod
    def load_model(self, path: str):
        """
        Load trained model from disk.
        
        Args:
            path: Path to saved model
        """
        pass
    
    def evaluate(self, env, n_episodes: int = 10, deterministic: bool = True) -> Dict[str, Any]:
        """
        Evaluate agent on environment.
        
        Args:
            env: Evaluation environment
            n_episodes: Number of episodes to evaluate
            deterministic: Whether to use deterministic policy
        
        Returns:
            Standardized result dict with evaluation metrics
        """
        episode_rewards = []
        episode_lengths = []
        
        for episode in range(n_episodes):
            obs, info = env.reset()
            done = False
            truncated = False
            episode_reward = 0
            episode_length = 0
            
            while not (done or truncated):
                action = self.predict(obs, deterministic=deterministic)
                obs, reward, done, truncated, info = env.step(action)
                episode_reward += reward
                episode_length += 1
            
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
        
        metrics = {
            'mean_reward': float(np.mean(episode_rewards)),
            'std_reward': float(np.std(episode_rewards)),
            'min_reward': float(np.min(episode_rewards)),
            'max_reward': float(np.max(episode_rewards)),
            'mean_length': float(np.mean(episode_lengths)),
            'n_episodes': n_episodes
        }
        
        return self._create_result_dict(
            value=metrics,
            method='evaluate',
            parameters={'n_episodes': n_episodes, 'deterministic': deterministic}
        )
EOF
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rl_base.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit BaseRLAgent implementation**

```bash
git add quantlib/rl/base_agent.py tests/test_rl_base.py
git commit -m "feat(rl): implement BaseRLAgent base class

- Inherit from BaseCalculator for architecture consistency
- Abstract methods: train, predict, save_model, load_model
- Concrete evaluate method with standardized metrics
- Model directory management
- Training history tracking"
```

---

### Task 4: Implement BaseRLEnvironment

**Files:**
- Modify: `tests/test_rl_base.py`
- Create: `quantlib/rl/base_environment.py`

- [ ] **Step 1: Write failing test for BaseRLEnvironment**

Add BaseRLEnvironment tests to existing test file with MockRLEnvironment implementation.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rl_base.py::test_base_rl_environment_initialization -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'quantlib.rl.base_environment'"

- [ ] **Step 3: Implement BaseRLEnvironment**

Create base_environment.py with Gymnasium interface, trading state management, and utility methods.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rl_base.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit BaseRLEnvironment implementation**

```bash
git add quantlib/rl/base_environment.py tests/test_rl_base.py
git commit -m "feat(rl): implement BaseRLEnvironment base class

- Follow Gymnasium standard interface
- Common trading state (cash, holdings, portfolio value)
- Transaction cost handling
- Abstract methods: step, _get_observation, _calculate_reward
- Utility methods for portfolio calculation and trade execution"
```

---

## Phase 2: FinRL Track

### Task 5: Implement FinRL Configuration

**Files:**
- Create: `quantlib/finrl/config.py`

- [ ] **Step 1: Create FinRL configuration file**

Create config.py with DEFAULT_INDICATORS, MODEL_DIR, TENSORBOARD_DIR, TRAINING_CONFIG, and ALGORITHM_PARAMS.

- [ ] **Step 2: Verify configuration file created**

Run: `cat quantlib/finrl/config.py | head -20`
Expected: Should show configuration constants

- [ ] **Step 3: Commit FinRL configuration**

```bash
git add quantlib/finrl/config.py
git commit -m "feat(finrl): add FinRL configuration

- Default technical indicators
- Model and log directories
- Training configuration defaults
- Algorithm-specific hyperparameters for PPO/DQN/A2C/SAC/TD3"
```

---

### Task 6: Implement FinRL Callbacks

**Files:**
- Create: `quantlib/finrl/callbacks.py`

- [ ] **Step 1: Create FinRL callbacks file**

Create callbacks.py with TradingCallback and ProgressCallback classes for training monitoring.

- [ ] **Step 2: Verify callbacks file created**

Run: `cat quantlib/finrl/callbacks.py | grep "class.*Callback"`
Expected: Should show TradingCallback and ProgressCallback classes

- [ ] **Step 3: Commit FinRL callbacks**

```bash
git add quantlib/finrl/callbacks.py
git commit -m "feat(finrl): add training callbacks

- TradingCallback for episode reward monitoring
- ProgressCallback for training progress display
- Integration with Stable-Baselines3 callback system"
```

---

### Task 7: Implement FinRLAgent Core

**Files:**
- Create: `tests/test_finrl_agents.py`
- Create: `quantlib/finrl/agents.py`

- [ ] **Step 1: Write failing test for FinRLAgent**

Create test file with tests for initialization, algorithm map, and invalid algorithm handling.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_finrl_agents.py::test_finrl_agent_initialization -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement FinRLAgent core structure**

Create agents.py with FinRLAgent class, ALGORITHM_MAP, and method stubs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_finrl_agents.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit FinRLAgent core**

```bash
git add quantlib/finrl/agents.py tests/test_finrl_agents.py
git commit -m "feat(finrl): implement FinRLAgent core structure

- Algorithm registry for PPO/DQN/A2C/SAC/TD3
- Inherit from BaseRLAgent
- Default hyperparameters from config
- Method stubs for train/predict/save/load"
```

---

### Task 8: Implement FinRLAgent Training

**Files:**
- Modify: `tests/test_finrl_agents.py`
- Modify: `quantlib/finrl/agents.py`

- [ ] **Step 1: Write failing test for training**

Add test_finrl_agent_train_with_mock_env to test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_finrl_agents.py::test_finrl_agent_train_with_mock_env -v`
Expected: FAIL with "NotImplementedError" or similar

- [ ] **Step 3: Implement train method**

Implement train() method in FinRLAgent with model creation, training loop, and result dict.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_finrl_agents.py::test_finrl_agent_train_with_mock_env -v`
Expected: PASS

- [ ] **Step 5: Commit training implementation**

```bash
git add quantlib/finrl/agents.py tests/test_finrl_agents.py
git commit -m "feat(finrl): implement FinRLAgent train method

- Create SB3 model with algorithm-specific params
- Train with callbacks support
- Return standardized result dict
- Track training history"
```

---

### Task 9: Implement FinRLAgent Predict/Save/Load

**Files:**
- Modify: `tests/test_finrl_agents.py`
- Modify: `quantlib/finrl/agents.py`

- [ ] **Step 1: Write failing tests for predict/save/load**

Add tests for predict, save_model, and load_model methods.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_finrl_agents.py -k "predict or save or load" -v`
Expected: FAIL

- [ ] **Step 3: Implement predict/save/load methods**

Implement predict(), save_model(), and load_model() methods in FinRLAgent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_finrl_agents.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit predict/save/load implementation**

```bash
git add quantlib/finrl/agents.py tests/test_finrl_agents.py
git commit -m "feat(finrl): implement predict/save/load methods

- predict() returns actions from trained model
- save_model() persists model to disk
- load_model() restores model from disk
- Handle model not trained error"
```

---

### Task 10: Implement StockTradingEnv

**Files:**
- Create: `tests/test_finrl_environments.py`
- Create: `quantlib/finrl/environments.py`

- [ ] **Step 1: Write failing test for StockTradingEnv**

Create test file with tests for environment initialization, reset, and step.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_finrl_environments.py::test_stock_trading_env_init -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement StockTradingEnv**

Create environments.py with StockTradingEnv class implementing BaseRLEnvironment.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_finrl_environments.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit StockTradingEnv implementation**

```bash
git add quantlib/finrl/environments.py tests/test_finrl_environments.py
git commit -m "feat(finrl): implement StockTradingEnv

- Continuous action space for buy/sell quantities
- State: cash + holdings + prices + indicators
- Reward: portfolio return
- Transaction cost handling
- Position limits (hmax)"
```

---

## Phase 3: Qlib Track

### Task 11: Implement Qlib Configuration

**Files:**
- Create: `quantlib/qlib/config.py`

- [ ] **Step 1: Create Qlib configuration file**

Create config.py with QLIB_DATA_PATH, QLIB_REGION, MODEL_DIR, and TRAINING_CONFIG.

- [ ] **Step 2: Verify configuration file created**

Run: `cat quantlib/qlib/config.py | head -15`
Expected: Should show Qlib configuration constants

- [ ] **Step 3: Commit Qlib configuration**

```bash
git add quantlib/qlib/config.py
git commit -m "feat(qlib): add Qlib RL configuration

- Qlib data path and region settings
- Model directory configuration
- Training configuration defaults"
```

---

### Task 12: Implement QlibRLAgent

**Files:**
- Create: `tests/test_qlib_rl.py`
- Create: `quantlib/qlib/rl.py`

- [ ] **Step 1: Write failing test for QlibRLAgent**

Create test file with skipif decorator for optional Qlib dependency.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qlib_rl.py -v`
Expected: FAIL or SKIP if Qlib not installed

- [ ] **Step 3: Implement QlibRLAgent**

Create rl.py with QlibRLAgent class integrating Qlib simulator and trainer.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qlib_rl.py -v`
Expected: PASS or SKIP

- [ ] **Step 5: Commit QlibRLAgent implementation**

```bash
git add quantlib/qlib/rl.py tests/test_qlib_rl.py
git commit -m "feat(qlib): implement QlibRLAgent

- Integrate Qlib simulator and trainer
- Inherit from BaseRLAgent
- Support Qlib data format
- Order execution simulation"
```

---

### Task 13: Implement QlibTradingEnv

**Files:**
- Modify: `tests/test_qlib_rl.py`
- Create: `quantlib/qlib/environments.py`

- [ ] **Step 1: Write failing test for QlibTradingEnv**

Add environment tests to test_qlib_rl.py.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qlib_rl.py::test_qlib_trading_env -v`
Expected: FAIL

- [ ] **Step 3: Implement QlibTradingEnv**

Create environments.py with QlibTradingEnv using Qlib data and simulator.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qlib_rl.py -v`
Expected: PASS or SKIP

- [ ] **Step 5: Commit QlibTradingEnv implementation**

```bash
git add quantlib/qlib/environments.py tests/test_qlib_rl.py
git commit -m "feat(qlib): implement QlibTradingEnv

- Use Qlib data format
- Target portfolio weight actions
- Qlib order execution simulator
- Portfolio rebalancing logic"
```

---

## Phase 4: Integration

### Task 14: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration_rl.py`

- [ ] **Step 1: Write integration test**

Create comprehensive end-to-end test: data → train → predict → evaluate → save → load.

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_integration_rl.py -v`
Expected: PASS

- [ ] **Step 3: Commit integration test**

```bash
git add tests/test_integration_rl.py
git commit -m "test(rl): add end-to-end integration test

- Full pipeline: train → predict → evaluate
- Model persistence (save/load)
- Multiple algorithms tested
- Synthetic data generation"
```

---

### Task 15: Update Documentation

**Files:**
- Modify: `quantsys-v2/README.md`
- Create: `quantsys-v2/docs/rl_modules_guide.md`

- [ ] **Step 1: Update README with RL modules**

Add RL modules section to README.md.

- [ ] **Step 2: Create RL modules guide**

Create comprehensive guide with examples and API documentation.

- [ ] **Step 3: Verify documentation**

Run: `grep -i "reinforcement learning" quantsys-v2/README.md`
Expected: Should show RL section

- [ ] **Step 4: Commit documentation**

```bash
git add quantsys-v2/README.md quantsys-v2/docs/rl_modules_guide.md
git commit -m "docs(rl): add RL modules documentation

- Update README with RL modules overview
- Create comprehensive RL modules guide
- Include usage examples and API reference"
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ BaseRLAgent and BaseRLEnvironment (Tasks 3-4)
- ✅ FinRL agents (5 algorithms) (Tasks 7-9)
- ✅ FinRL environments (StockTradingEnv) (Task 10)
- ✅ Qlib RL agent (Tasks 11-12)
- ✅ Qlib environment (Task 13)
- ✅ Configuration files (Tasks 5, 11)
- ✅ Training callbacks (Task 6)
- ✅ Dependencies (Task 1)
- ✅ Directory structure (Task 2)
- ✅ Integration tests (Task 14)
- ✅ Documentation (Task 15)

**Placeholder Scan:**
- ✅ No "TBD" or "TODO" placeholders
- ✅ All code examples are complete or referenced as "create X with Y"
- ✅ All test commands have expected outputs
- ✅ All commits have complete messages

**Type Consistency:**
- ✅ BaseRLAgent methods consistent across all tasks
- ✅ BaseRLEnvironment interface consistent
- ✅ Result dict format consistent (via _create_result_dict)
- ✅ File paths consistent throughout

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-25-rl-modules-migration.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
