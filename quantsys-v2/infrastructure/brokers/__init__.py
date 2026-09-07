# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""
Broker Infrastructure Setup

This module registers concrete broker implementations into the domain registry.
Follows hexagonal architecture: infrastructure depends on domain, not vice versa.
"""

from .setup import setup_brokers

__all__ = ['setup_brokers']
