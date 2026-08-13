#!/usr/bin/env python3
"""Market Driver CLI - AKShare data provider for Agent OS

Provides real-time quotes, K-line data, and market status via AKShare.
Includes Redis caching layer for performance optimization.

Usage:
    market-driver quote --symbol 600519.SH
    market-driver kline --symbol 600519.SH --period daily --start 20240101 --end 20240131
    market-driver market-status
"""
import sys
import json
import logging
from typing import Any, Dict, List, Optional
import click

from adapters.akshare_adapter import AkShareMarketAdapter
from cache.redis_cache import RedisCache

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketDriver:
    """Market data driver with caching"""

    def __init__(self):
        self.adapter = AkShareMarketAdapter()
        self.cache = RedisCache()

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote for symbol with cache"""
        # Try cache first (TTL: 60 seconds for real-time data)
        cache_key = f"quote:{symbol}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for quote: {symbol}")
            return cached

        # Fetch from AKShare
        logger.info(f"Fetching quote from AKShare: {symbol}")
        quotes = self.adapter.get_realtime_quote([symbol])

        if symbol not in quotes:
            return {
                "error": "symbol_not_found",
                "message": f"Symbol {symbol} not found or market closed"
            }

        result = quotes[symbol]

        # Cache for 60 seconds
        self.cache.set(cache_key, result, ttl=60)

        return result

    def get_kline(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20240101",
        end_date: str = "20240131"
    ) -> List[Dict[str, Any]]:
        """Get K-line data with cache"""
        # Try cache first (TTL: 1 day for K-line data)
        cache_key = f"kline:{symbol}:{period}:{start_date}:{end_date}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for kline: {symbol}")
            return cached

        # Fetch from AKShare
        logger.info(f"Fetching kline from AKShare: {symbol}")
        klines = self.adapter.get_klines(symbol, period, start_date, end_date)

        if not klines:
            return []

        # Cache for 1 day (86400 seconds)
        self.cache.set(cache_key, klines, ttl=86400)

        return klines

    def get_market_status(self) -> Dict[str, Any]:
        """Get market status (is market open/closed)"""
        from datetime import datetime
        import time

        now = datetime.now()
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        hour = now.hour
        minute = now.minute

        # Check if it's a trading day (Monday to Friday)
        if weekday >= 5:  # Saturday or Sunday
            return {
                "is_open": False,
                "status": "closed",
                "reason": "weekend",
                "timestamp": int(time.time())
            }

        # Check trading hours (9:30-11:30, 13:00-15:00)
        current_time = hour * 60 + minute
        morning_open = 9 * 60 + 30  # 9:30
        morning_close = 11 * 60 + 30  # 11:30
        afternoon_open = 13 * 60  # 13:00
        afternoon_close = 15 * 60  # 15:00

        is_trading_hours = (morning_open <= current_time <= morning_close) or \
                          (afternoon_open <= current_time <= afternoon_close)

        if is_trading_hours:
            session = "morning" if current_time <= morning_close else "afternoon"
            return {
                "is_open": True,
                "status": "open",
                "session": session,
                "timestamp": int(time.time())
            }
        else:
            if current_time < morning_open:
                reason = "pre_market"
            elif morning_close < current_time < afternoon_open:
                reason = "lunch_break"
            else:
                reason = "after_market"

            return {
                "is_open": False,
                "status": "closed",
                "reason": reason,
                "timestamp": int(time.time())
            }


# CLI Commands

@click.group()
def cli():
    """Market Driver - AKShare data provider for Agent OS"""
    pass


@cli.command()
@click.option('--symbol', required=True, help='Stock symbol (e.g., 600519.SH)')
def quote(symbol: str):
    """Get real-time quote for a symbol"""
    try:
        driver = MarketDriver()
        result = driver.get_quote(symbol)

        if "error" in result:
            click.echo(json.dumps(result, ensure_ascii=False, indent=2), err=True)
            sys.exit(2)  # Business error

        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    except Exception as e:
        error_result = {
            "error": "system_error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, ensure_ascii=False, indent=2), err=True)
        logger.exception("Failed to get quote")
        sys.exit(3)  # System error


@cli.command()
@click.option('--symbol', required=True, help='Stock symbol (e.g., 600519.SH)')
@click.option('--period', default='daily', help='Period: daily, weekly, monthly')
@click.option('--start', 'start_date', default='20240101', help='Start date (YYYYMMDD)')
@click.option('--end', 'end_date', default='20240131', help='End date (YYYYMMDD)')
def kline(symbol: str, period: str, start_date: str, end_date: str):
    """Get K-line data for a symbol"""
    try:
        driver = MarketDriver()
        result = driver.get_kline(symbol, period, start_date, end_date)

        if not result:
            error_result = {
                "error": "no_data",
                "message": f"No K-line data found for {symbol}"
            }
            click.echo(json.dumps(error_result, ensure_ascii=False, indent=2), err=True)
            sys.exit(2)  # Business error

        output = {
            "symbol": symbol,
            "period": period,
            "count": len(result),
            "data": result
        }
        click.echo(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(0)
    except Exception as e:
        error_result = {
            "error": "system_error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, ensure_ascii=False, indent=2), err=True)
        logger.exception("Failed to get kline")
        sys.exit(3)  # System error


@cli.command()
def market_status():
    """Get market status (open/closed)"""
    try:
        driver = MarketDriver()
        result = driver.get_market_status()
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    except Exception as e:
        error_result = {
            "error": "system_error",
            "message": str(e)
        }
        click.echo(json.dumps(error_result, ensure_ascii=False, indent=2), err=True)
        logger.exception("Failed to get market status")
        sys.exit(3)  # System error


if __name__ == '__main__':
    cli()
