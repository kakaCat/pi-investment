# QuantSys V2 Daemon

JSON-RPC 2.0 daemon service for TypeScript agent tools.

## Overview

The daemon provides a bridge between TypeScript agent tools and the quantsys-v2 Python backend. It communicates via stdin/stdout using JSON-RPC 2.0 protocol.

## Architecture

```
TypeScript Agent Tools
        ↓
quantsys-daemon-adapter.ts
        ↓ (stdin/stdout)
daemon/server.py (JSON-RPC 2.0)
        ↓
daemon/handlers/* (L1/L2/L3 handlers)
        ↓ (HTTP)
quantsys-v2 REST API (Flask)
```

## Starting the Daemon

```bash
cd quantsys-v2
python -m daemon.server
```

## Available Methods

### L1 Data Layer (6 methods)
- `get_stock_info`, `get_stock_price`, `get_stock_fundamentals`
- `search_stocks`, `get_market_data`, `update_stock_data`

### L2 Factor Layer (5 methods)
- `calculate_factor`, `batch_calculate_factors`, `get_factor_values`
- `list_available_factors`, `validate_factor_expression`

### L3 Model Layer (5 methods)
- `model_train`, `model_predict`, `model_evaluate`
- `model_list`, `model_monitor`

### Built-in Methods
- `ping` - Health check

## Testing

```bash
pytest tests/daemon/ -v
```

## Dependencies

- Python 3.9+
- aiohttp >= 3.9.0
- quantsys-v2 REST API running on http://127.0.0.1:5001
