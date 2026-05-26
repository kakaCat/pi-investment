# K-line Data Backfill Script Usage Guide

## Overview

`backfill_klines.py` is a command-line tool to backfill missing K-line data (daily or minute) for stocks. It integrates all components of the backfill system and provides progress tracking with resume support.

## Quick Start

```bash
# Activate Python environment
source activate-py313.sh

# Backfill daily data for specific symbols
python quant/scripts/backfill_klines.py --data-type daily --symbols 600519.SH,000001.SZ

# Backfill minute data for all A-share stocks
python quant/scripts/backfill_klines.py --data-type minute --market A

# Backfill with custom settings
python quant/scripts/backfill_klines.py \
  --data-type daily \
  --market A \
  --target-days 365 \
  --batch-size 20 \
  --reset-progress
```

## Command-Line Options

### Required

- `--data-type {daily,minute}` — Type of K-line data to backfill

### Optional

- `--symbols SYMBOLS` — Comma-separated list of symbols (e.g., "600519.SH,000001.SZ")
  - If not provided, uses `--market` filter to get all symbols from database

- `--market {A,HK}` — Market filter (default: A)
  - `A`: A-share stocks (.SH, .SZ suffixes)
  - `HK`: Hong Kong stocks (.HK suffix)
  - Only used if `--symbols` not provided

- `--target-days TARGET_DAYS` — Number of calendar days to backfill
  - Default: 730 for daily (2 years)
  - Default: 365 for minute (1 year)

- `--batch-size BATCH_SIZE` — Number of symbols to process in one batch (default: 10)
  - Progress is saved after each batch
  - Smaller batches = more frequent saves, slower overall
  - Larger batches = less frequent saves, faster overall

- `--reset-progress` — Clear progress tracker before starting
  - Use this to start fresh (ignores previous progress)
  - Without this flag, script resumes from last saved progress

## Usage Examples

### Example 1: Backfill specific symbols (daily)

```bash
python quant/scripts/backfill_klines.py \
  --data-type daily \
  --symbols 600519.SH,000001.SZ,000002.SZ
```

**Output:**
```
============================================================
K-line Data Backfill
============================================================
Data Type:    daily
Target Days:  730
Batch Size:   10
Market:       A
Symbols:      600519.SH,000001.SZ,000002.SZ
Reset Progress: False
============================================================

Initializing components...
✓ Components initialized

Loading symbol list...
✓ Loaded 3 symbols

============================================================
Processing Batch 1/1 (3 symbols)
============================================================

Processing [1/3] 600519.SH...
✓ 600519.SH: 10 succeeded, 0 failed, 5 skipped

Processing [2/3] 000001.SZ...
✓ 000001.SZ: 8 succeeded, 0 failed, 12 skipped

Processing [3/3] 000002.SZ...
✓ 000002.SZ: 12 succeeded, 0 failed, 3 skipped

============================================================
Batch 1/1 complete: 3/3 symbols succeeded
============================================================

✓ Progress saved after batch 1

============================================================
FINAL SUMMARY
============================================================
Symbols Processed:    3/3
Symbols Succeeded:    3
Dates Backfilled:     30
Dates Failed:         0
Dates Skipped:        20
============================================================

✓ Backfill complete!
```

### Example 2: Backfill all A-share stocks (minute)

```bash
python quant/scripts/backfill_klines.py \
  --data-type minute \
  --market A \
  --target-days 180 \
  --batch-size 20
```

This will:
- Get all A-share symbols from database
- Backfill minute data for last 180 days
- Process 20 symbols per batch
- Save progress after each batch

### Example 3: Resume interrupted backfill

If you interrupt the script (Ctrl+C), progress is automatically saved:

```
^C
Interrupted by user (Ctrl+C)
Saving progress...
✓ Progress saved. You can resume by running the same command again.
```

To resume, simply run the same command again:

```bash
python quant/scripts/backfill_klines.py \
  --data-type daily \
  --market A
```

The script will skip already-completed dates and continue from where it left off.

### Example 4: Start fresh (reset progress)

```bash
python quant/scripts/backfill_klines.py \
  --data-type daily \
  --market A \
  --reset-progress
```

This clears all saved progress and starts backfilling from scratch.

### Example 5: Backfill HK stocks

```bash
python quant/scripts/backfill_klines.py \
  --data-type daily \
  --market HK \
  --target-days 365
```

## Progress Tracking

Progress is automatically saved:
- After each batch completes
- When you interrupt with Ctrl+C
- Stored in database (managed by ProgressTracker)

Progress tracking ensures:
- No duplicate downloads
- Resume support after interruption
- Efficient incremental backfills

## Performance Tips

1. **Batch size**: Larger batches (20-50) are faster but save progress less frequently
2. **Target days**: Start with smaller windows (365 days) for testing
3. **Specific symbols**: Use `--symbols` for targeted backfills instead of full market
4. **Rate limiting**: Built-in 0.1s delay between requests (configurable in DataBackfiller)

## Error Handling

The script handles errors gracefully:

- **Network errors**: Retries up to 3 times with exponential backoff
- **Symbol failures**: Logs error and continues with next symbol
- **Database errors**: Logs error and continues with next date
- **Ctrl+C**: Saves progress and exits cleanly

## Integration with Other Components

The script integrates:
- **Database** (`quantsys.data.db`) — Storage layer
- **TradingCalendar** (`quantsys.data.trading_calendar`) — Trading day validation
- **GapDetector** (`quantsys.data.gap_detector`) — Missing data detection
- **ProgressTracker** (`quantsys.data.progress_tracker`) — Resume support
- **DataBackfiller** (`quantsys.data.data_backfiller`) — Download and storage

## Troubleshooting

### No symbols found

```
Loading symbol list...
✓ Loaded 0 symbols
No symbols to process. Exiting.
```

**Solution**: Check that symbols exist in database with correct market suffix (.SH, .SZ, .HK)

### All dates skipped

```
✓ 600519.SH: 0 succeeded, 0 failed, 100 skipped
```

**Solution**: Data already exists. Use `--reset-progress` to re-download, or check target-days window.

### High failure rate

```
⚠ 600519.SH: 5 succeeded, 15 failed, 0 skipped
```

**Solution**: Check network connection, akshare API status, or increase retry count in DataBackfiller.

## See Also

- `quant/quantsys/data/data_backfiller.py` — Core backfill logic
- `quant/quantsys/data/gap_detector.py` — Gap detection algorithm
- `quant/quantsys/data/progress_tracker.py` — Progress tracking implementation
- `quant/tests/test_backfill_klines.py` — Test suite
