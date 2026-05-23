# NaN JSON Serialization Fix

## Problem

The QuantSys daemon was failing to parse JSON responses when pandas DataFrames contained NaN values. The error occurred because:

1. **Root Cause**: When pandas DataFrames are converted to dictionaries using `to_dict(orient="records")`, NaN values remain as Python's `float('nan')`
2. **JSON Issue**: Python's `json.dumps()` serializes `float('nan')` as the literal string `NaN`, which is **not valid JSON** (JSON only supports `null`, not `NaN`)
3. **Parse Failure**: TypeScript's `JSON.parse()` fails when encountering `NaN` in the response

### Example Error
```
SyntaxError: Unexpected token 'N', ...", "变动比率": NaN}, {"名次"... is not valid JSON
    at JSON.parse (<anonymous>)
    at QuantSysDaemon.handleResponse (quantsys-daemon-adapter.ts:172:46)
```

### Example Data
Shareholder data from `get_top_holders` for stock 600600:
```json
{
  "data": [
    {"名次": 1, "股东名称": "香港中央结算", "变动比率": 0.0074904},
    {"名次": 2, "股东名称": "青岛啤酒集团", "变动比率": NaN}  // ❌ Invalid JSON
  ]
}
```

## Solution

Added a `_sanitize_for_json()` function in [daemon.py](../quant/quantsys/cli/daemon.py) that:

1. **Recursively traverses** all data structures (dicts, lists, tuples)
2. **Converts NaN/Infinity to None**: Uses `math.isnan()` and `math.isinf()` to detect invalid float values
3. **Preserves valid data**: Normal floats and other types pass through unchanged

### Implementation

```python
def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert NaN/Infinity values to None for JSON serialization."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_sanitize_for_json(item) for item in obj)
    else:
        return obj
```

Applied in `handle_request()` before returning the result:
```python
result = handler(params)
result = _sanitize_for_json(result)  # Clean NaN values
return {"jsonrpc": "2.0", "id": request_id, "result": result}
```

## Result

After the fix, the same data becomes valid JSON:
```json
{
  "data": [
    {"名次": 1, "股东名称": "香港中央结算", "变动比率": 0.0074904},
    {"名次": 2, "股东名称": "青岛啤酒集团", "变动比率": null}  // ✓ Valid JSON
  ]
}
```

## Impact

- **Affected APIs**: All daemon methods that return pandas DataFrame data, especially:
  - `get_top_holders` (shareholder data)
  - `get_holder_changes` (shareholder count changes)
  - Any financial/market data with missing values
  
- **No Breaking Changes**: `null` values are semantically correct for missing/undefined data
- **TypeScript Compatibility**: `JSON.parse()` handles `null` correctly

## Testing

Verified with test cases covering:
- Simple NaN/Infinity values
- Nested dictionaries with NaN
- Lists with NaN
- Complex shareholder data structures
- JSON serialization round-trip

## Date
2026-05-22
