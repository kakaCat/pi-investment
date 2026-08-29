"""
FinRL Callbacks Module
======================

Provides training callbacks for monitoring, logging, and checkpointing.

This module implements callbacks that integrate with stable-baselines3 training:
- TensorBoardCallback: Logs training metrics to TensorBoard
- CheckpointCallback: Saves model checkpoints at specified intervals
- EvalCallback: Evaluates model performance periodically

Usage:
    from domain.quantlib.finrl.callbacks import create_callbacks

    # Create all callbacks
    callbacks = create_callbacks(
        log_dir='./logs',
        save_path='./models',
        save_freq=5000,
        eval_env=eval_env,
        eval_freq=1000
    )

    # Use with stable-baselines3 model
    model.learn(total_timesteps=100000, callback=callbacks)

Requirements:
    - stable-baselines3>=2.0.0
    - gym>=0.21.0 or gymnasium>=0.29.0

Author: RL Migration Team
Date: 2026-05-25
"""
import structlog
logger = structlog.get_logger(__name__)

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

try:
    from stable_baselines3.common.callbacks import BaseCallback
    CALLBACKS_AVAILABLE = True
except ImportError:
    CALLBACKS_AVAILABLE = False
    # Define dummy BaseCallback for type hints
    class BaseCallback:
        """Dummy BaseCallback when stable-baselines3 is not available."""
        def __init__(self, verbose: int = 0):
            self.verbose = verbose
            self.model = None
            self.training_env = None
            self.n_calls = 0
            self.num_timesteps = 0
            self.locals: Dict[str, Any] = {}
            self.globals: Dict[str, Any] = {}


class TensorBoardCallback(BaseCallback):
    """
    Callback for logging training metrics to TensorBoard.

    Logs episode rewards, lengths, and other training metrics during training.
    Creates TensorBoard event files that can be visualized with tensorboard.

    Args:
        log_dir: Directory to save TensorBoard logs
        verbose: Verbosity level (0: no output, 1: info, 2: debug)

    Example:
        >>> callback = TensorBoardCallback(log_dir='./logs/tensorboard')
        >>> model.learn(total_timesteps=10000, callback=callback)
    """

    def __init__(self, log_dir: str, verbose: int = 0):
        """
        Initialize TensorBoardCallback.

        Args:
            log_dir: Directory to save TensorBoard logs
            verbose: Verbosity level (0: no output, 1: info, 2: debug)
        """
        super().__init__(verbose)
        self.log_dir = log_dir
        self.writer = None

    def _on_training_start(self) -> None:
        """
        Called before training starts.

        Creates log directory and initializes TensorBoard writer.
        """
        # Create log directory
        log_path = Path(self.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        if self.verbose > 0:
            logger.info(f'TensorBoard logs will be saved to: {self.log_dir}')

        # Initialize TensorBoard writer if available
        try:
            from torch.utils.tensorboard import SummaryWriter
            self.writer = SummaryWriter(log_dir=self.log_dir)
        except ImportError:
            if self.verbose > 0:
                logger.info('Warning: tensorboard not available, logging disabled')
            self.writer = None

    def _on_step(self) -> bool:
        """
        Called after each training step.

        Logs metrics to TensorBoard if available.

        Returns:
            True to continue training, False to stop
        """
        if self.writer is None:
            return True

        # Log episode rewards if available
        if 'rewards' in self.locals and len(self.locals['rewards']) > 0:
            mean_reward = np.mean(self.locals['rewards'])
            self.writer.add_scalar(
                'train/mean_reward',
                mean_reward,
                self.num_timesteps
            )

        # Log episode lengths if available
        if 'episode_lengths' in self.locals and len(self.locals['episode_lengths']) > 0:
            mean_length = np.mean(self.locals['episode_lengths'])
            self.writer.add_scalar(
                'train/mean_episode_length',
                mean_length,
                self.num_timesteps
            )

        return True

    def _on_training_end(self) -> None:
        """
        Called after training ends.

        Closes TensorBoard writer.
        """
        if self.writer is not None:
            self.writer.close()

        if self.verbose > 0:
            logger.info('TensorBoard logging completed')


class CheckpointCallback(BaseCallback):
    """
    Callback for saving model checkpoints at specified intervals.

    Saves model to disk every `save_freq` steps during training.
    Useful for resuming training or selecting best checkpoint.

    Args:
        save_path: Directory to save model checkpoints
        save_freq: Save checkpoint every N steps
        name_prefix: Prefix for checkpoint filenames (default: 'model')
        verbose: Verbosity level (0: no output, 1: info, 2: debug)

    Example:
        >>> callback = CheckpointCallback(
        ...     save_path='./models',
        ...     save_freq=5000,
        ...     name_prefix='ppo_model'
        ... )
        >>> model.learn(total_timesteps=100000, callback=callback)
    """

    def __init__(
        self,
        save_path: str,
        save_freq: int = 10000,
        name_prefix: str = 'model',
        verbose: int = 0
    ):
        """
        Initialize CheckpointCallback.

        Args:
            save_path: Directory to save model checkpoints
            save_freq: Save checkpoint every N steps
            name_prefix: Prefix for checkpoint filenames
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.save_path = save_path
        self.save_freq = save_freq
        self.name_prefix = name_prefix

    def _on_training_start(self) -> None:
        """
        Called before training starts.

        Creates save directory.
        """
        # Create save directory
        save_dir = Path(self.save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose > 0:
            logger.info(f'Model checkpoints will be saved to: {self.save_path}')
            logger.info(f'Save frequency: every {self.save_freq} steps')

    def _on_step(self) -> bool:
        """
        Called after each training step.

        Saves model checkpoint if save_freq steps have elapsed.

        Returns:
            True to continue training, False to stop
        """
        # Check if it's time to save
        if self.n_calls % self.save_freq == 0:
            checkpoint_path = Path(self.save_path) / f"{self.name_prefix}_{self.num_timesteps}_steps"
            self.model.save(str(checkpoint_path))

            if self.verbose > 0:
                logger.info(f'Saved checkpoint at step {self.num_timesteps}: {checkpoint_path}')

        return True

    def _on_training_end(self) -> None:
        """
        Called after training ends.

        Saves final model checkpoint.
        """
        final_path = Path(self.save_path) / f"{self.name_prefix}_final"
        self.model.save(str(final_path))

        if self.verbose > 0:
            logger.info(f'Saved final model: {final_path}')


class EvalCallback(BaseCallback):
    """
    Callback for periodic model evaluation during training.

    Evaluates model on a separate evaluation environment every `eval_freq` steps.
    Tracks best model performance and optionally saves best model.

    Args:
        eval_env: Environment for evaluation
        eval_freq: Evaluate every N steps
        n_eval_episodes: Number of episodes to run for each evaluation
        best_model_save_path: Optional path to save best model
        verbose: Verbosity level (0: no output, 1: info, 2: debug)

    Example:
        >>> eval_env = gym.make('TradingEnv-v0')
        >>> callback = EvalCallback(
        ...     eval_env=eval_env,
        ...     eval_freq=1000,
        ...     n_eval_episodes=5
        ... )
        >>> model.learn(total_timesteps=100000, callback=callback)
    """

    def __init__(
        self,
        eval_env: Any,
        eval_freq: int = 10000,
        n_eval_episodes: int = 5,
        best_model_save_path: Optional[str] = None,
        verbose: int = 0
    ):
        """
        Initialize EvalCallback.

        Args:
            eval_env: Environment for evaluation
            eval_freq: Evaluate every N steps
            n_eval_episodes: Number of episodes per evaluation
            best_model_save_path: Optional path to save best model
            verbose: Verbosity level
        """
        super().__init__(verbose)
        self.eval_env = eval_env
        self.eval_freq = eval_freq
        self.n_eval_episodes = n_eval_episodes
        self.best_model_save_path = best_model_save_path
        self.best_mean_reward = -np.inf
        self.last_mean_reward = 0.0

    def _on_training_start(self) -> None:
        """
        Called before training starts.

        Creates save directory if best_model_save_path is specified.
        """
        if self.best_model_save_path is not None:
            save_dir = Path(self.best_model_save_path)
            save_dir.mkdir(parents=True, exist_ok=True)

        if self.verbose > 0:
            logger.info(f'Evaluation frequency: every {self.eval_freq} steps')
            logger.info(f'Number of evaluation episodes: {self.n_eval_episodes}')

    def _on_step(self) -> bool:
        """
        Called after each training step.

        Evaluates model if eval_freq steps have elapsed.

        Returns:
            True to continue training, False to stop
        """
        # Check if it's time to evaluate
        if self.n_calls % self.eval_freq == 0:
            self._evaluate_model()

        return True

    def _evaluate_model(self) -> None:
        """
        Evaluate model on evaluation environment.

        Runs n_eval_episodes and computes mean reward.
        Updates best model if performance improves.
        """
        episode_rewards = []
        episode_lengths = []

        for episode in range(self.n_eval_episodes):
            obs = self.eval_env.reset()
            done = False
            episode_reward = 0.0
            episode_length = 0

            while not done:
                # Predict action
                action, _ = self.model.predict(obs, deterministic=True)

                # Take step
                obs, reward, done, info = self.eval_env.step(action)
                episode_reward += reward
                episode_length += 1

            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)

        # Compute statistics
        mean_reward = np.mean(episode_rewards)
        std_reward = np.std(episode_rewards)
        mean_length = np.mean(episode_lengths)

        self.last_mean_reward = mean_reward

        if self.verbose > 0:
            logger.info(f'\nEvaluation at step {self.num_timesteps}:')
            logger.info(f'  Mean reward: {mean_reward:.2f} +/- {std_reward:.2f}')
            logger.info(f'  Mean episode length: {mean_length:.1f}')

        # Save best model
        if mean_reward > self.best_mean_reward:
            self.best_mean_reward = mean_reward

            if self.verbose > 0:
                logger.info(f'  New best mean reward: {self.best_mean_reward:.2f}')

            if self.best_model_save_path is not None:
                best_model_path = Path(self.best_model_save_path) / "best_model"
                self.model.save(str(best_model_path))

                if self.verbose > 0:
                    logger.info(f'  Saved best model to: {best_model_path}')

    def _on_training_end(self) -> None:
        """
        Called after training ends.

        Performs final evaluation.
        """
        if self.verbose > 0:
            logger.info('\nFinal evaluation:')

        self._evaluate_model()

        if self.verbose > 0:
            logger.info(f'Best mean reward achieved: {self.best_mean_reward:.2f}')


def create_callbacks(
    log_dir: str,
    save_path: str,
    save_freq: int = 10000,
    eval_env: Optional[Any] = None,
    eval_freq: int = 10000,
    n_eval_episodes: int = 5,
    name_prefix: str = 'model',
    verbose: int = 0
) -> List[BaseCallback]:
    """
    Create a list of configured callbacks for training.

    Convenience function to create commonly used callbacks with consistent settings.

    Args:
        log_dir: Directory for TensorBoard logs
        save_path: Directory for model checkpoints
        save_freq: Save checkpoint every N steps
        eval_env: Optional evaluation environment
        eval_freq: Evaluate every N steps (only if eval_env provided)
        n_eval_episodes: Number of episodes per evaluation
        name_prefix: Prefix for checkpoint filenames
        verbose: Verbosity level for all callbacks

    Returns:
        List of configured callbacks

    Example:
        >>> callbacks = create_callbacks(
        ...     log_dir='./logs',
        ...     save_path='./models',
        ...     save_freq=5000,
        ...     eval_env=eval_env,
        ...     eval_freq=1000
        ... )
        >>> model.learn(total_timesteps=100000, callback=callbacks)
    """
    callbacks: List[BaseCallback] = []

    # Always add TensorBoard callback
    callbacks.append(TensorBoardCallback(log_dir=log_dir, verbose=verbose))

    # Always add Checkpoint callback
    callbacks.append(CheckpointCallback(
        save_path=save_path,
        save_freq=save_freq,
        name_prefix=name_prefix,
        verbose=verbose
    ))

    # Add Eval callback if eval_env is provided
    if eval_env is not None:
        callbacks.append(EvalCallback(
            eval_env=eval_env,
            eval_freq=eval_freq,
            n_eval_episodes=n_eval_episodes,
            best_model_save_path=save_path,
            verbose=verbose
        ))

    return callbacks


__all__ = [
    'TensorBoardCallback',
    'CheckpointCallback',
    'EvalCallback',
    'create_callbacks',
]
