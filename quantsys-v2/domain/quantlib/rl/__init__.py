"""
Reinforcement Learning Module
==============================

Base RL infrastructure for quantitative trading strategies.

This module provides common RL components that can be used with different
RL frameworks (FinRL, Qlib, custom implementations).

Modules:
    - base_agent: Abstract base class for RL agents
    - base_environment: Abstract base class for trading environments

Usage:
    from domain.quantlib.rl import BaseRLAgent, BaseRLEnvironment

Author: RL Migration Team
Date: 2026-05-25
"""

from .base_agent import BaseRLAgent
from .base_environment import BaseRLEnvironment

__all__ = [
    'BaseRLAgent',
    'BaseRLEnvironment',
]
