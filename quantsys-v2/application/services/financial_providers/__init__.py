"""兼容 shim（2026-10-18）：已迁至二方包 qs_market_data（30 天观察期）。"""
import qs_market_data.application.services.financial_providers as _t

__path__ = _t.__path__
from qs_market_data.application.services.financial_providers import *  # noqa: F401,F403
