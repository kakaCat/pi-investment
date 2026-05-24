# Signals API

## POST /api/signals/scan

Scan stocks for investment opportunities with multi-dimensional scoring.

### Request

**Endpoint:** `POST /api/signals/scan`

**Headers:**
- `Content-Type: application/json`

**Body Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| stocks | array[string] | No | Specific stock codes to scan. If empty, scans watchlist + hot stock pool (~400 stocks) |
| minScore | number | No | Minimum comprehensive score (0-100). Default: 0 |
| maxRiskLevel | string | No | Maximum risk level: "low", "medium", "high". Default: "high" |
| technical | array[string] | No | Technical indicator filters: "rsi_oversold", "macd_golden_cross", "bollinger_breakout", "volume_surge" |
| fundamental | array[string] | No | Fundamental filters: "low_pe", "high_roe", "high_margin", "low_debt" |
| industries | array[string] | No | Industry filters (optional) |

**Example Request:**
```json
{
  "minScore": 70,
  "maxRiskLevel": "medium",
  "technical": ["rsi_oversold", "macd_golden_cross"],
  "fundamental": ["low_pe", "high_roe"]
}
```

### Response

**Success Response (200 OK):**

```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "score": 85,
      "technical_score": 90,
      "fundamental_score": 80,
      "capital_score": 75,
      "confidence": 0.85,
      "risk_level": "low",
      "signal_type": "buy",
      "timestamp": "2026-05-24T12:00:00"
    }
  ],
  "total": 1,
  "scanned": 400
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| success | boolean | Whether the scan completed successfully |
| opportunities | array[object] | List of investment opportunities |
| opportunities[].symbol | string | Stock code (e.g., "600519.SH") |
| opportunities[].name | string | Stock name |
| opportunities[].score | number | Comprehensive score (0-100) |
| opportunities[].technical_score | number | Technical analysis score (0-100) |
| opportunities[].fundamental_score | number | Fundamental analysis score (0-100) |
| opportunities[].capital_score | number | Capital flow score (0-100) |
| opportunities[].confidence | number | Confidence level (0-1) |
| opportunities[].risk_level | string | Risk level: "low", "medium", "high" |
| opportunities[].signal_type | string | Signal type (currently always "buy") |
| opportunities[].timestamp | string | ISO 8601 timestamp |
| total | number | Number of opportunities returned |
| scanned | number | Total number of stocks scanned |

**Error Response (500 Internal Server Error):**

```json
{
  "success": false,
  "error": "Error message"
}
```

### Scoring Details

#### Comprehensive Score
The overall opportunity score is calculated as a weighted average:
```
comprehensive_score = technical_score × 0.5 + fundamental_score × 0.3 + capital_score × 0.2
```

#### Technical Score (0-100)
Based on technical indicators:
- **RSI oversold** (RSI < 30): +25 points
- **MACD golden cross**: +25 points
- **Bollinger Band breakout** (price > upper band): +25 points
- **Volume surge** (volume > 2x average): +25 points

#### Fundamental Score (0-100)
Based on fundamental metrics:
- **Low PE** (PE < 30): +25 points
- **High ROE** (ROE > 15%): +25 points
- **High Gross Margin** (margin > 30%): +25 points
- **Low Debt Ratio** (debt < 50%): +25 points

#### Capital Score (0-100)
Based on capital flow indicators:
- **Volume growth** (> 50% vs 5-day avg): +25 points
- **Consecutive volume increases** (3+ days): +25 points
- **Volume above MA20**: +25 points
- **Volume MA5 > MA20**: +25 points

#### Risk Level
Determined by confidence score:
- **low**: confidence ≥ 0.7 (score ≥ 70)
- **medium**: confidence ≥ 0.5 (score ≥ 50)
- **high**: confidence < 0.5 (score < 50)

### Performance

- **Response Time**: < 1 second for 400 stocks
- **Timeout**: 30 seconds
- **Rate Limit**: None (consider adding in production)

### Notes

- If `stocks` parameter is empty, the endpoint scans the user's watchlist plus the hot stock pool (沪深300 + 创业板50 + 科创50)
- Scoring uses 120 days of K-line data
- Fundamental data is optional; stocks without fundamentals get 50 (neutral) fundamental score
- Results are sorted by comprehensive score (descending)
- The scoring engine uses parallel processing (10 workers) for optimal performance
- Batch queries minimize database load (3-5 queries total for 400 stocks)

### Examples

#### Example 1: Basic Scan
Scan all stocks in watchlist and hot pool:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### Example 2: Scan Specific Stocks
Scan only specific stocks:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "stocks": ["600519.SH", "000001.SZ"]
  }'
```

#### Example 3: Filter by Score and Risk
Only show high-quality, low-risk opportunities:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "minScore": 70,
    "maxRiskLevel": "low"
  }'
```

#### Example 4: Technical Pattern Screening
Find stocks with specific technical patterns:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "technical": ["rsi_oversold", "macd_golden_cross"],
    "minScore": 60
  }'
```

#### Example 5: Fundamental Screening
Find stocks with strong fundamentals:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "fundamental": ["low_pe", "high_roe", "low_debt"],
    "minScore": 65
  }'
```

#### Example 6: Combined Filters
Combine multiple filters for precise screening:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "minScore": 70,
    "maxRiskLevel": "medium",
    "technical": ["rsi_oversold"],
    "fundamental": ["low_pe", "high_roe"]
  }'
```
