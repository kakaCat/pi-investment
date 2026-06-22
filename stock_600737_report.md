# Stock Data Report: 600737 (中粮糖业)

**Generated**: 2026-06-22

## Basic Information

- **Symbol**: 600737
- **Name**: 中粮糖业 (COFCO Sugar Industry)
- **Market**: A股 (A-share)
- **Industry**: 制造业-农副食品加工业 (Manufacturing - Agricultural & Food Processing)

## Data Status

⚠️ **Current Status**: Incomplete data in system

The stock exists in the database but shows:
- `dataStatus`: "incomplete"
- `klineDays`: 0 (no K-line data)
- `factorCount`: 0 (no factor data)
- `price`: 0.0 (no current price data)

## Attempted Data Sources

### 1. API Endpoints Tested
- ✅ `/api/stocks/600737` - Basic info retrieved
- ❌ `/api/stock/600737/news` - All data providers failed
- ❌ `/api/stock/600737/announcements` - All data providers failed  
- ❌ `/api/stock/600737/quote` - No database data available
- ❌ `/api/stocks/batch-quotes` - Request failed

### 2. Network Data Sources
- ❌ AkShare `stock_individual_info_em()` - Connection timeout
- ❌ AkShare `stock_news_em()` - Connection timeout after 30s

## Recommendations

To populate data for this stock:

1. **Check network connectivity**: The external data sources (EastMoney, Sina, etc.) are timing out
2. **Run data backfill script**: 
   ```bash
   cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
   python scripts/backfill_stocks.py --symbol 600737
   ```
3. **Initialize stock data**:
   ```bash
   python scripts/init_stocks.py
   ```
4. **Verify database connection**: Ensure the PostgreSQL/SQLite database is accessible

## Available Information Summary

From the limited data retrieved:

| Field | Value |
|-------|-------|
| Symbol | 600737 |
| Name | 中粮糖业 |
| Industry | 制造业-农副食品加工业 |
| Market | A |
| Data Status | incomplete |

**Note**: News and announcements require external network access to EastMoney, Sina, or other data providers. All attempts encountered network timeouts or provider failures.

---

## Next Steps

If you need current data for 600737:
1. Check if the API service has proper network access to Chinese financial data sources
2. Verify firewall/proxy settings
3. Consider running the service with VPN if accessing from outside China
4. Use the backfill scripts to populate historical data once network issues are resolved
