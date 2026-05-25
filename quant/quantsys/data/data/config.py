"""Data source configuration."""

import os
from pathlib import Path

# Tushare configuration
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_ENABLED = bool(TUSHARE_TOKEN)
TUSHARE_RATE_LIMIT = 200  # requests per minute (free tier)

# AkShare configuration
AKSHARE_ENABLED = True
AKSHARE_RATE_LIMIT = 1000  # requests per minute (estimated)

# Data source priorities (lower = higher priority)
DATA_SOURCE_PRIORITIES = {
    "tushare": 1,   # Most stable, but has rate limit
    "akshare": 2,   # Free and fast, but may be unstable
}

# Data source configuration
DATA_SOURCES = {
    "tushare": {
        "enabled": TUSHARE_ENABLED,
        "priority": DATA_SOURCE_PRIORITIES["tushare"],
        "rate_limit": TUSHARE_RATE_LIMIT,
        "token": TUSHARE_TOKEN,
        "description": "Tushare Pro API - stable but rate limited",
    },
    "akshare": {
        "enabled": AKSHARE_ENABLED,
        "priority": DATA_SOURCE_PRIORITIES["akshare"],
        "rate_limit": AKSHARE_RATE_LIMIT,
        "description": "AkShare - free and fast",
    },
}

# Cache configuration
CACHE_ENABLED = True
CACHE_MAX_SIZE = 1000  # Max number of cached items
CACHE_DEFAULT_TTL = 300  # Default TTL in seconds (5 minutes)

# Database configuration
DB_PATH = Path(__file__).parent.parent.parent.parent.parent / ".pi-invest" / "stock-db" / "stocks.db"
