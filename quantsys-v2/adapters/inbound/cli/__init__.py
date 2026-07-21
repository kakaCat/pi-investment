"""
CLI Package Initialization
"""

from .command_base import Command, HTTPCommand, CommandResult
from .command_registry import CommandRegistry, get_registry, auto_discover_commands
from .http_client import HTTPClient
from .formatters import get_formatter

__all__ = [
    'Command',
    'HTTPCommand',
    'CommandResult',
    'CommandRegistry',
    'get_registry',
    'auto_discover_commands',
    'HTTPClient',
    'get_formatter',
]

__version__ = '2.0.0'
