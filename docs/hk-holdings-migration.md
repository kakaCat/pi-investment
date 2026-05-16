# HK Holdings Migration Guide

## Overview

This migration script adds missing foreign exchange (FX) rate fields to existing Hong Kong stock holdings in your portfolio. These fields are required for accurate cost tracking and P&L calculation when dealing with HK stocks.

## Why Migration is Needed

Prior to the HK Stock FX Handling feature, HK stock holdings only stored the CNY (人民币) cost without tracking:
- The original HKD (港币) purchase price
- The FX rate at the time of purchase

Without these fields, the system cannot:
- Accurately calculate P&L when FX rates change
- Display both HKD and CNY costs
- Track the true cost basis for tax purposes

## What the Script Does

The migration script:

1. **Identifies HK holdings** that are missing `avg_cost_hkd` or `purchase_fx_rate` fields
2. **Fetches current FX rate** from Sina Finance API (with 4-layer fallback)
3. **Reverse-calculates HKD cost** using the formula: `avg_cost_hkd = avg_cost_cny / current_fx_rate`
4. **Records the current FX rate** as `purchase_fx_rate` (estimated)
5. **Creates a backup** of the original portfolio file before making changes
6. **Updates the portfolio** with the new fields

## How to Run

### Dry-Run Mode (Preview Only)

By default, the script runs in **dry-run mode** and shows what changes would be made without modifying any files:

```bash
npm run migrate:hk-holdings
```

This will display:
- Which HK holdings need migration
- Current data vs. migrated data
- Calculated HKD costs and FX rates
- Important warnings about estimation accuracy

### Apply Mode (Make Changes)

To actually apply the migration, use the `--apply` flag:

```bash
npm run migrate:hk-holdings -- --apply
```

This will:
- Create a timestamped backup file (e.g., `portfolio.backup.2026-05-16T04-38-52-006Z.json`)
- Update the portfolio with FX fields
- Display a summary of changes

## Example Output

### Dry-Run Mode

```
🔄 港股持仓数据迁移工具

模式: 🔍 预览模式（不会修改文件）

📊 找到 3 只港股持仓

🌐 获取当前汇率...
✅ 当前汇率: 1 HKD = 0.8692 CNY

🔧 需要迁移 3 只港股:

📋 迁移详情:

────────────────────────────────────────────────────────────────────────────────

股票: 00700 腾讯控股
持仓: 100 股

  当前数据:
    avg_cost (CNY):        666.57 元
    avg_cost_hkd:          (缺失)
    purchase_fx_rate:      (缺失)

  迁移后数据:
    avg_cost (CNY):        666.57 元 (不变)
    avg_cost_hkd:          766.88 港元 (反推)
    purchase_fx_rate:      0.8692 (当前汇率)

  市值计算:
    总成本 (CNY):          66657.00 元
    总成本 (HKD):          76688.00 港元

────────────────────────────────────────────────────────────────────────────────

⚠️  重要提示:
   • avg_cost_hkd 是根据当前汇率反推的，不是真实买入价
   • purchase_fx_rate 使用当前汇率估算，不是实际买入时汇率
   • 如果你记得真实买入价，可以在迁移后手动修正 portfolio.json
   • 迁移前会自动创建备份文件

🔍 预览模式 - 未修改任何文件

要应用这些更改，请运行:
  npm run migrate:hk-holdings -- --apply
```

### Apply Mode

```
💾 应用迁移...

✅ 已备份到: /path/to/.pi-invest/portfolio.backup.2026-05-16T04-38-52-006Z.json
✅ 已覆盖为 12 只持仓

🎉 迁移完成！共更新 3 只港股持仓

💡 提示: 如需修正真实买入价，请编辑 /path/to/.pi-invest/portfolio.json
```

## Limitations and Important Notes

### ⚠️ Estimated Values

The migration script uses **estimated values** for FX fields:

- **`avg_cost_hkd`**: Reverse-calculated from CNY cost using the **current** FX rate, not the actual purchase price
- **`purchase_fx_rate`**: Set to the **current** FX rate, not the actual rate at purchase time

### Why Estimation?

The original portfolio data did not store HKD prices or FX rates, so the script cannot know the true historical values. It uses the current FX rate as a best-effort estimate.

### Impact on Accuracy

- **P&L calculations**: May be slightly inaccurate if the FX rate has changed significantly since purchase
- **Cost basis**: The CNY cost (`avg_cost`) remains unchanged and accurate
- **Display**: HKD costs shown in the UI will be estimates

### Manual Correction

If you remember the actual purchase prices in HKD, you can manually correct the values:

1. Open `.pi-invest/portfolio.json` in a text editor
2. Find your HK holdings (where `"market": "HK"`)
3. Update `avg_cost_hkd` to the actual HKD purchase price
4. Update `purchase_fx_rate` to the actual FX rate at purchase (if known)
5. Save the file

Example:

```json
{
  "symbol": "00700",
  "name": "腾讯控股",
  "quantity": 100,
  "avg_cost": 666.57,
  "avg_cost_hkd": 750.00,  // ← Manually corrected
  "purchase_fx_rate": 0.8888,  // ← Manually corrected
  "market": "HK",
  ...
}
```

## Safety Features

### Automatic Backup

Before making any changes, the script creates a timestamped backup:

```
.pi-invest/portfolio.backup.2026-05-16T04-38-52-006Z.json
```

You can restore from this backup if needed:

```bash
cp .pi-invest/portfolio.backup.*.json .pi-invest/portfolio.json
```

### Idempotent

The script is **safe to run multiple times**. If holdings already have FX fields, it will skip them:

```
✅ 所有港股持仓已包含汇率信息，无需迁移
```

### Dry-Run by Default

The script defaults to dry-run mode, requiring explicit `--apply` to make changes. This prevents accidental modifications.

## Edge Cases

### No HK Holdings

If your portfolio has no HK stocks:

```
ℹ️  未找到港股持仓，无需迁移
```

### Already Migrated

If all HK holdings already have FX fields:

```
✅ 所有港股持仓已包含汇率信息，无需迁移
```

### Network Failure

If the FX rate fetch fails, the script uses a 4-layer fallback:
1. Fresh cache (< 24 hours)
2. Live fetch from Sina Finance
3. Stale cache (any age)
4. Default rate (0.88)

## Troubleshooting

### Script Fails to Run

```bash
# Ensure dependencies are installed
npm install

# Check Node.js version (requires 22+)
node --version
```

### FX Rate Fetch Fails

The script will use fallback rates. Check your network connection or wait and try again.

### Backup File Not Created

Ensure you have write permissions to the `.pi-invest/` directory.

### Wrong Values After Migration

Restore from backup and manually edit the portfolio file with correct values:

```bash
cp .pi-invest/portfolio.backup.*.json .pi-invest/portfolio.json
```

## Related Documentation

- [HK Stock FX Handling Implementation Plan](superpowers/plans/2026-05-16-hk-stock-fx-handling.md)
- [FxRateService Documentation](../src/services/fx-rate-service.ts)
- [Portfolio Service Documentation](../src/services/portfolio/portfolio-service.ts)

## Support

If you encounter issues or have questions about the migration, please:
1. Check the backup file was created
2. Review the dry-run output carefully
3. Manually verify the migrated values in `portfolio.json`
4. Correct any inaccurate values manually if needed
