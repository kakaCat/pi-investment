"""Daemon handlers - auto-import all handlers to register them."""

# Import all handler modules to trigger @register_method decorators
from . import data_handlers
from . import model_handlers
from . import factor_handlers

__all__ = ['data_handlers', 'model_handlers', 'factor_handlers']
