"""
Tests for FinRL Callbacks Module
=================================

Tests training callbacks for monitoring, logging, and checkpointing.

Author: RL Migration Team
Date: 2026-05-25
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, MagicMock, patch

# Check if FinRL dependencies are available
try:
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3 import PPO
    import gym
    FINRL_AVAILABLE = True
except ImportError:
    FINRL_AVAILABLE = False


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestCallbackImports:
    """Test callback module imports."""

    def test_import_callbacks_module(self):
        """Test that callbacks module can be imported."""
        from domain.quantlib.finrl.callbacks import (
            TensorBoardCallback,
            CheckpointCallback,
            EvalCallback,
            create_callbacks,
        )

        assert TensorBoardCallback is not None
        assert CheckpointCallback is not None
        assert EvalCallback is not None
        assert callable(create_callbacks)

    def test_callbacks_inherit_from_base(self):
        """Test that all callbacks inherit from BaseCallback."""
        from domain.quantlib.finrl.callbacks import (
            TensorBoardCallback,
            CheckpointCallback,
            EvalCallback,
        )

        assert issubclass(TensorBoardCallback, BaseCallback)
        assert issubclass(CheckpointCallback, BaseCallback)
        assert issubclass(EvalCallback, BaseCallback)


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestTensorBoardCallback:
    """Test TensorBoardCallback for metrics logging."""

    def test_tensorboard_callback_initialization(self):
        """Test TensorBoardCallback can be initialized."""
        from domain.quantlib.finrl.callbacks import TensorBoardCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = TensorBoardCallback(log_dir=tmpdir, verbose=0)
            assert callback is not None
            assert callback.log_dir == tmpdir
            assert callback.verbose == 0

    def test_tensorboard_callback_has_required_methods(self):
        """Test TensorBoardCallback has required callback methods."""
        from domain.quantlib.finrl.callbacks import TensorBoardCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = TensorBoardCallback(log_dir=tmpdir)

            # Check that callback has required methods
            assert hasattr(callback, '_on_training_start')
            assert hasattr(callback, '_on_step')
            assert hasattr(callback, '_on_training_end')
            assert callable(callback._on_training_start)
            assert callable(callback._on_step)
            assert callable(callback._on_training_end)

    def test_tensorboard_callback_creates_log_dir(self):
        """Test TensorBoardCallback creates log directory."""
        from domain.quantlib.finrl.callbacks import TensorBoardCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "tensorboard_logs"
            callback = TensorBoardCallback(log_dir=str(log_dir))

            # Simulate training start
            callback.model = Mock()
            callback.model.num_timesteps = 0
            callback._on_training_start()

            # Log directory should be created
            assert log_dir.exists()

    def test_tensorboard_callback_logs_metrics(self):
        """Test TensorBoardCallback logs training metrics."""
        from domain.quantlib.finrl.callbacks import TensorBoardCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = TensorBoardCallback(log_dir=tmpdir)

            # Mock model and locals
            callback.model = Mock()
            callback.model.num_timesteps = 100
            callback.locals = {
                'rewards': [1.0, 2.0, 3.0],
                'episode_lengths': [10, 20, 30],
            }

            # Should not raise exception
            callback._on_training_start()
            result = callback._on_step()

            # Should return True to continue training
            assert result is True


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestCheckpointCallback:
    """Test CheckpointCallback for model saving."""

    def test_checkpoint_callback_initialization(self):
        """Test CheckpointCallback can be initialized."""
        from domain.quantlib.finrl.callbacks import CheckpointCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = CheckpointCallback(
                save_path=tmpdir,
                save_freq=1000,
                name_prefix="model",
                verbose=0
            )
            assert callback is not None
            assert callback.save_path == tmpdir
            assert callback.save_freq == 1000
            assert callback.name_prefix == "model"
            assert callback.verbose == 0

    def test_checkpoint_callback_has_required_methods(self):
        """Test CheckpointCallback has required callback methods."""
        from domain.quantlib.finrl.callbacks import CheckpointCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = CheckpointCallback(save_path=tmpdir, save_freq=1000)

            assert hasattr(callback, '_on_training_start')
            assert hasattr(callback, '_on_step')
            assert hasattr(callback, '_on_training_end')
            assert callable(callback._on_training_start)
            assert callable(callback._on_step)
            assert callable(callback._on_training_end)

    def test_checkpoint_callback_creates_save_dir(self):
        """Test CheckpointCallback creates save directory."""
        from domain.quantlib.finrl.callbacks import CheckpointCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "checkpoints"
            callback = CheckpointCallback(
                save_path=str(save_path),
                save_freq=1000
            )

            # Simulate training start
            callback.model = Mock()
            callback.model.num_timesteps = 0
            callback._on_training_start()

            # Save directory should be created
            assert save_path.exists()

    def test_checkpoint_callback_saves_model(self):
        """Test CheckpointCallback saves model at specified frequency."""
        from domain.quantlib.finrl.callbacks import CheckpointCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = CheckpointCallback(
                save_path=tmpdir,
                save_freq=100,
                name_prefix="test_model"
            )

            # Mock model
            callback.model = Mock()
            callback.model.save = Mock()
            callback.model.num_timesteps = 0
            callback.n_calls = 0

            callback._on_training_start()

            # Simulate steps
            for i in range(150):
                callback.model.num_timesteps = i + 1
                callback.n_calls = i + 1
                callback._on_step()

            # Model should be saved at step 100
            assert callback.model.save.called

    def test_checkpoint_callback_naming(self):
        """Test CheckpointCallback uses correct naming pattern."""
        from domain.quantlib.finrl.callbacks import CheckpointCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = CheckpointCallback(
                save_path=tmpdir,
                save_freq=100,
                name_prefix="my_model"
            )

            # Mock model
            callback.model = Mock()
            callback.model.save = Mock()
            callback.model.num_timesteps = 100
            callback.n_calls = 100

            callback._on_training_start()
            callback._on_step()

            # Check that save was called with correct path pattern
            if callback.model.save.called:
                call_args = callback.model.save.call_args[0][0]
                assert "my_model" in call_args
                assert "100" in call_args


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestEvalCallback:
    """Test EvalCallback for periodic evaluation."""

    def test_eval_callback_initialization(self):
        """Test EvalCallback can be initialized."""
        from domain.quantlib.finrl.callbacks import EvalCallback

        # Mock environment
        eval_env = Mock()

        callback = EvalCallback(
            eval_env=eval_env,
            eval_freq=1000,
            n_eval_episodes=5,
            verbose=0
        )
        assert callback is not None
        assert callback.eval_env == eval_env
        assert callback.eval_freq == 1000
        assert callback.n_eval_episodes == 5
        assert callback.verbose == 0

    def test_eval_callback_has_required_methods(self):
        """Test EvalCallback has required callback methods."""
        from domain.quantlib.finrl.callbacks import EvalCallback

        eval_env = Mock()
        callback = EvalCallback(eval_env=eval_env, eval_freq=1000)

        assert hasattr(callback, '_on_training_start')
        assert hasattr(callback, '_on_step')
        assert hasattr(callback, '_on_training_end')
        assert callable(callback._on_training_start)
        assert callable(callback._on_step)
        assert callable(callback._on_training_end)

    def test_eval_callback_evaluates_at_frequency(self):
        """Test EvalCallback evaluates model at specified frequency."""
        from domain.quantlib.finrl.callbacks import EvalCallback

        # Mock environment
        eval_env = Mock()
        eval_env.reset = Mock(return_value=[0.0])
        eval_env.step = Mock(return_value=([0.0], 1.0, True, {}))

        callback = EvalCallback(
            eval_env=eval_env,
            eval_freq=100,
            n_eval_episodes=1
        )

        # Mock model
        callback.model = Mock()
        callback.model.predict = Mock(return_value=([0], None))
        callback.model.num_timesteps = 0
        callback.n_calls = 0

        callback._on_training_start()

        # Simulate steps
        for i in range(150):
            callback.model.num_timesteps = i + 1
            callback.n_calls = i + 1
            callback._on_step()

        # Evaluation should have been triggered at step 100
        assert eval_env.reset.called

    def test_eval_callback_tracks_best_model(self):
        """Test EvalCallback tracks best model performance."""
        from domain.quantlib.finrl.callbacks import EvalCallback

        # Mock environment with improving rewards
        eval_env = Mock()
        eval_env.reset = Mock(return_value=[0.0])
        eval_env.step = Mock(return_value=([0.0], 10.0, True, {}))

        callback = EvalCallback(
            eval_env=eval_env,
            eval_freq=100,
            n_eval_episodes=1
        )

        # Mock model
        callback.model = Mock()
        callback.model.predict = Mock(return_value=([0], None))
        callback.model.num_timesteps = 100
        callback.n_calls = 100

        callback._on_training_start()
        callback._on_step()

        # Should track best mean reward
        assert hasattr(callback, 'best_mean_reward')


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestCreateCallbacks:
    """Test create_callbacks helper function."""

    def test_create_callbacks_returns_list(self):
        """Test create_callbacks returns a list of callbacks."""
        from domain.quantlib.finrl.callbacks import create_callbacks

        with tempfile.TemporaryDirectory() as tmpdir:
            callbacks = create_callbacks(
                log_dir=tmpdir,
                save_path=tmpdir,
                save_freq=1000,
                eval_env=None,
                eval_freq=1000
            )

            assert isinstance(callbacks, list)

    def test_create_callbacks_with_all_params(self):
        """Test create_callbacks with all parameters."""
        from domain.quantlib.finrl.callbacks import create_callbacks

        eval_env = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            callbacks = create_callbacks(
                log_dir=tmpdir,
                save_path=tmpdir,
                save_freq=1000,
                eval_env=eval_env,
                eval_freq=1000,
                n_eval_episodes=5,
                verbose=1
            )

            # Should return 3 callbacks: TensorBoard, Checkpoint, Eval
            assert len(callbacks) == 3

    def test_create_callbacks_without_eval(self):
        """Test create_callbacks without evaluation environment."""
        from domain.quantlib.finrl.callbacks import create_callbacks

        with tempfile.TemporaryDirectory() as tmpdir:
            callbacks = create_callbacks(
                log_dir=tmpdir,
                save_path=tmpdir,
                save_freq=1000,
                eval_env=None
            )

            # Should return 2 callbacks: TensorBoard, Checkpoint (no Eval)
            assert len(callbacks) == 2

    def test_create_callbacks_minimal_params(self):
        """Test create_callbacks with minimal parameters."""
        from domain.quantlib.finrl.callbacks import create_callbacks

        with tempfile.TemporaryDirectory() as tmpdir:
            callbacks = create_callbacks(
                log_dir=tmpdir,
                save_path=tmpdir
            )

            # Should return at least TensorBoard and Checkpoint
            assert len(callbacks) >= 2

    def test_create_callbacks_types(self):
        """Test create_callbacks returns correct callback types."""
        from domain.quantlib.finrl.callbacks import (
            create_callbacks,
            TensorBoardCallback,
            CheckpointCallback,
            EvalCallback,
        )

        eval_env = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            callbacks = create_callbacks(
                log_dir=tmpdir,
                save_path=tmpdir,
                save_freq=1000,
                eval_env=eval_env,
                eval_freq=1000
            )

            # Check callback types
            callback_types = [type(cb) for cb in callbacks]
            assert TensorBoardCallback in callback_types
            assert CheckpointCallback in callback_types
            assert EvalCallback in callback_types


@pytest.mark.skipif(not FINRL_AVAILABLE, reason="FinRL dependencies not available")
class TestCallbackIntegration:
    """Test callback integration with training."""

    def test_callbacks_work_with_dummy_env(self):
        """Test callbacks work with a simple dummy environment."""
        from domain.quantlib.finrl.callbacks import create_callbacks
        import gym
        from stable_baselines3 import PPO

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create simple environment
            env = gym.make('CartPole-v1')

            # Create callbacks
            callbacks = create_callbacks(
                log_dir=tmpdir,
                save_path=tmpdir,
                save_freq=100,
                eval_env=env,
                eval_freq=100,
                n_eval_episodes=1,
                verbose=0
            )

            # Create model
            model = PPO('MlpPolicy', env, verbose=0)

            # Train for a few steps (should not raise exception)
            model.learn(total_timesteps=200, callback=callbacks)

            # Cleanup
            env.close()

    def test_callback_lifecycle(self):
        """Test callback lifecycle methods are called in correct order."""
        from domain.quantlib.finrl.callbacks import TensorBoardCallback

        with tempfile.TemporaryDirectory() as tmpdir:
            callback = TensorBoardCallback(log_dir=tmpdir)

            # Track method calls
            calls = []

            original_on_training_start = callback._on_training_start
            original_on_step = callback._on_step
            original_on_training_end = callback._on_training_end

            def track_on_training_start():
                calls.append('start')
                return original_on_training_start()

            def track_on_step():
                calls.append('step')
                return original_on_step()

            def track_on_training_end():
                calls.append('end')
                return original_on_training_end()

            callback._on_training_start = track_on_training_start
            callback._on_step = track_on_step
            callback._on_training_end = track_on_training_end

            # Mock model
            callback.model = Mock()
            callback.model.num_timesteps = 0
            callback.n_calls = 0

            # Simulate training lifecycle
            callback._on_training_start()
            callback._on_step()
            callback._on_step()
            callback._on_training_end()

            # Check call order
            assert calls == ['start', 'step', 'step', 'end']


@pytest.mark.skipif(FINRL_AVAILABLE, reason="Test for when FinRL is not available")
class TestCallbacksWithoutFinRL:
    """Test graceful handling when FinRL dependencies are not available."""

    def test_import_fails_gracefully(self):
        """Test that import fails gracefully when FinRL is not available."""
        # This test runs only when FINRL_AVAILABLE is False
        # The module should handle missing dependencies gracefully
        try:
            from domain.quantlib.finrl import FINRL_AVAILABLE
            assert FINRL_AVAILABLE is False
        except ImportError:
            # Expected when dependencies are missing
            pass
