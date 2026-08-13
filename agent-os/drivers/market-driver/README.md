# Market Driver

Python CLI tool that provides market data via AKShare for Agent OS.

## Features

- **Real-time Quotes**: Get live stock quotes (price, volume, change, etc.)
- **K-line Data**: Fetch historical OHLCV data (daily, weekly, monthly)
- **Market Status**: Check if market is open/closed
- **Redis Caching**: Automatic caching with TTL (60s for quotes, 1 day for K-lines)
- **Error Handling**: Standardized error codes and JSON output

## Installation

```bash
cd agent-os/drivers/market-driver
pip install -r requirements.txt
chmod +x main.py
```

## Usage

### CLI Commands

```bash
# Get real-time quote
./main.py quote --symbol 600519.SH

# Get K-line data
./main.py kline --symbol 600519.SH --period daily --start 20240101 --end 20240131

# Check market status
./main.py market-status
```

### Integration with Agent OS

The Go CLI calls this Python driver via `exec.Command`:

```bash
# Via agent-os command
agent-os data quote --symbol 600519.SH
agent-os data kline --symbol 600519.SH --period daily
agent-os data market-status
```

## Architecture

```
market-driver/
├── main.py                  # CLI entry point
├── adapters/
│   └── akshare_adapter.py  # AKShare API wrapper
├── cache/
│   └── redis_cache.py      # Redis caching layer
└── requirements.txt
```

## Error Codes

- `0`: Success
- `1`: Parameter error (invalid arguments)
- `2`: Business error (symbol not found, no data)
- `3`: System error (AKShare API failure, network error)

## Cache Strategy

- **Real-time quotes**: TTL 60 seconds
- **K-line data**: TTL 1 day (86400 seconds)
- **Graceful degradation**: Works without Redis, just slower

## Dependencies

- Python 3.13+
- AKShare (data source)
- Redis (optional, for caching)
- Click (CLI framework)
- Pandas (data processing)
