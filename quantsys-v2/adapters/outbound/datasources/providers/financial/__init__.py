# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""Financial statement data providers."""
from adapters.outbound.datasources.providers.financial.akshare import AkshareFinancialStatementProvider

__all__ = [
    'AkshareFinancialStatementProvider',
]
