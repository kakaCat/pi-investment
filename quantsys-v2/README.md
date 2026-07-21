# QuantSys V2

**Quantitative Investment System - Version 2**

A comprehensive quantitative investment platform built with Python, featuring factor calculation, machine learning models, backtesting, and reinforcement learning capabilities.

## ⚠️ Environment Requirements (READ THIS FIRST)

**CRITICAL**: This project requires **Python 3.12+** and **MUST** use a virtual environment.

### Quick Setup

```bash
# 1. Check Python version (REQUIRED: 3.13+)
/opt/homebrew/bin/python3.13 --version  # Must be 3.13.x or higher

# 2. Create virtual environment (MANDATORY) - 如果不存在
/opt/homebrew/bin/python3.13 -m venv venv

# 3. Activate virtual environment (ALWAYS required)
source activate-py313.sh
# 或
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start services
python start_all.py
```

**❌ DO NOT**:
- Use system Python (`python3` may be 3.8)
- Skip virtual environment setup
- Install packages globally
- Create venv in project root directory (should be in quantsys-v2/)

**📖 Detailed guide**: [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md)

---

## 🚀 Quick Start

**New to the project?** Start here: [📖 Quick Start Guide](QUICK_START_GUIDE.md)

**For ML model deployment:** [📋 Deployment Plan](DEPLOYMENT_PLAN.md) | [✅ Project Handover Checklist](PROJECT_HANDOVER_CHECKLIST.md)

**ML Training Results:** IC=0.25 (target >0.04), IR=0.48 (target >1.5) - [📊 Final Report](PROJECT_FINAL_CONCLUSION_REPORT.md)

## Overview

QuantSys V2 is a refactored quantitative investment system with a dual anti-corruption layer architecture and Pipeline pattern. It provides HTTP/WebSocket APIs, CLI tools, and a comprehensive quant pipeline for factor calculation, model prediction, backtesting, and risk assessment.

## Key Features

- **Factor Library** - 62+ technical and fundamental factors
- **ML Pipeline** - XGBoost/LightGBM models with feature engineering
- **Backtesting Engine** - Realistic simulation with transaction costs
- **Strategy Diagnosis** - Automated strategy effectiveness analysis with comprehensive reports
- **Risk Management** - Position sizing, stop-loss, portfolio constraints
- **RL Modules** - Reinforcement learning with FinRL and Qlib integration
- **Real-time APIs** - HTTP REST and WebSocket endpoints
- **CLI Tools** - Command-line interface for all operations
- **Data Pipeline** - Automated data fetching and processing

## Architecture

### Layered Architecture

```
quantsys-v2/
├── api/                    # HTTP and WebSocket APIs
├── cli/                    # Command-line interface
├── services/               # Business logic layer
├── repositories/           # Data access layer
├── quantlib/               # Quantitative library
│   ├── base_calculator.py  # Base calculator class
│   ├── rl/                 # Base RL abstractions
│   ├── finrl/              # FinRL integration (Stable-Baselines3)
│   └── qlib/               # Qlib RL integration
├── quant/stages/           # Pipeline stages
│   └── data/               # Data pipeline stages
├── runtime/                # Runtime infrastructure
├── infrastructure/         # External integrations
└── tests/                  # Test suite
```

## Data Pipeline

The data pipeline processes stock market data through 8 stages with automatic quality control and multi-source integration:

### Pipeline Stages

1. **DataFetch** - Fetch from multiple sources (akshare, tushare) with parallel execution
2. **Deduplication** - Remove duplicate records, keep latest fetch
3. **TimeAlignment** - Filter non-trading days, mark suspensions
4. **AnomalyDetection** - Detect price jumps, volume spikes, assign quality scores
5. **ConflictResolution** - Merge sources by priority (akshare > tushare > eastmoney)
6. **Imputation** - Fill missing values (forward-fill prices, zero-fill volume)
7. **Storage** - Write to three-layer database (raw_klines, daily_klines, weekly_klines)
8. **FactorCompute** - Trigger factor computation for updated symbols

### Usage

```python
from services.data_pipeline_service import DataPipelineService

# Initialize service
service = DataPipelineService()

# Daily update (single date)
result = service.run_daily_update(
    symbols=['600000.SH', '000001.SZ'],
    date='2024-01-05'
)

# Full rebuild (date range)
result = service.run_full_rebuild(
    symbols=['600000.SH'],
    start_date='2024-01-01',
    end_date='2024-01-31'
)

# Check results
print(f"Success: {result['success']}")
print(f"Records processed: {result['records_processed']}")
print(f"Factors computed: {result['factors_computed']}")
```

### Configuration

Pipeline configuration in `config/data_pipeline.yaml`:

```yaml
pipeline:
  sources:
    - name: akshare
      priority: 1
      enabled: true
    - name: tushare
      priority: 2
      enabled: false
  
  anomaly_detection:
    price_jump_threshold: 0.15
    volume_spike_threshold: 5.0
  
  storage:
    batch_size: 1000
```

### Scheduled Tasks

Automated data updates via scheduler:

- **Daily update**: 16:30 weekdays (after market close)
- **Weekly rebuild**: Sunday 2:00 AM (last 90 days)
- **Factor compute**: 16:00 weekdays (after data update)

### Database Schema

Three-layer storage for different use cases:

- **raw_klines** - Raw data with source tracking and quality scores
- **daily_klines** - Cleaned daily data (primary query table)
- **weekly_klines** - Aggregated weekly data for long-term analysis

## Reinforcement Learning Modules

QuantSys V2 includes comprehensive RL capabilities for algorithmic trading:

### Base RL Module (`quantlib/rl/`)

Abstract base classes for RL agents and environments:
- **BaseRLAgent** - Inherits from BaseCalculator, provides train/predict/save/load interface
- **BaseRLEnvironment** - Gymnasium-compatible trading environment interface

[📖 Read the RL Module Documentation](quantlib/rl/README.md)

### FinRL Integration (`quantlib/finrl/`)

Stable-Baselines3 wrapper for financial RL:
- **Supported Algorithms:** PPO, A2C, DDPG, SAC, TD3
- **StockTradingEnv** - Realistic trading simulation with transaction costs
- **Configuration System** - Default hyperparameters for each algorithm
- **Training Callbacks** - Logging, checkpointing, evaluation

[📖 Read the FinRL Documentation](quantlib/finrl/README.md)

### Qlib Integration (`quantlib/qlib/`)

Microsoft Qlib RL framework integration:
- **Supported Algorithms:** PPO, DQN, A2C, SAC, TD3
- **QlibTradingEnv** - Qlib-compatible trading environment
- **Data Integration** - Native Qlib data handler support
- **Backtesting** - Integrated with Qlib backtest framework

[📖 Read the Qlib Documentation](quantlib/qlib/README.md)

### Quick Start: RL Training

```python
from quantlib.finrl import FinRLAgent, StockTradingEnv
from quantlib.finrl.config import get_default_config
import pandas as pd

# Load data
df = pd.read_csv('stock_data.csv')

# Create environment
env = StockTradingEnv(df=df, initial_balance=100000, transaction_cost=0.001)

# Create and train agent
agent = FinRLAgent(algorithm='ppo', env=env)
config = get_default_config('ppo', training={'total_timesteps': 100000})
result = agent.train(env=env, config=config)

# Save model
agent.save_model('./models/ppo_agent')

# Use for trading
obs, _ = env.reset()
action = agent.predict(obs)
```

## Installation

### Prerequisites

- Python >= 3.9
- PostgreSQL >= 12
- Redis (optional, for caching)

### Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# RL dependencies (optional)
pip install stable-baselines3>=2.0.0  # For FinRL
pip install pyqlib torch>=1.9.0       # For Qlib RL
```

### Database Setup

```bash
# Create databases
createdb quant_investment      # Production
createdb quant_test            # Testing

# Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

## Usage

### Start Services

```bash
# Start all services (HTTP + WebSocket + Scheduler)
python start_all.py

# Or start individually
python api/server.py              # HTTP API (port 5001)
python api/server_websocket.py    # WebSocket API (port 5003)

# Initialize scheduler tasks (first time only)
PYTHONPATH=. python scripts/init_scheduler_tasks.py
```

### CLI Commands

```bash
# Stock search
python cli/main.py stock search --q 平安

# Factor calculation
python cli/main.py factor calculate --symbol 000001.SZ

# Model training
python cli/main.py model train --symbols 000001.SZ,600000.SH

# Backtesting
python cli/main.py backtest run --strategy momentum --start 2023-01-01
```

### Data Management

```bash
# Backfill historical data (补救缺失数据)
PYTHONPATH=. python scripts/backfill_data.py --days 10

# Backfill specific date range
PYTHONPATH=. python scripts/backfill_data.py --start-date 2026-05-01 --end-date 2026-05-25

# Test with limited stocks
PYTHONPATH=. python scripts/backfill_data.py --days 10 --limit 10
```

### Scheduler Management

The scheduler automatically runs data updates and other tasks. Default tasks:

- **daily-data-update**: 15:30 weekdays (after market close)
- **update_market_style**: 15:30 weekdays (market style detection)
- **daily-factor-compute**: 16:00 weekdays
- **daily-signal-generate**: 16:30 weekdays
- **weekly-risk-check**: 09:00 Monday
- **weekly-report**: 18:00 Friday

```bash
# View all tasks
curl http://127.0.0.1:5001/api/scheduler/tasks

# Manually trigger a task
curl -X POST http://127.0.0.1:5001/api/scheduler/tasks/<task_id>/trigger

# View run history
curl http://127.0.0.1:5001/api/scheduler/runs
```

## Strategy Diagnosis System

### Overview

Automated strategy effectiveness analysis system that helps users quickly determine if a strategy is worth using. Integrated into the BacktestCenter page with comprehensive diagnostic reports.

### Core Features

- **Quick Effectiveness Check** - Sharpe ratio < 1.0 indicates strategy underperforms benchmark
- **Hybrid Rating System** - Combines fixed thresholds with benchmark comparison
- **Comprehensive Grading** - A/B/C/D ratings based on multiple metrics
- **Diagnostic Insights** - Identifies strengths, weaknesses, and optimization suggestions
- **Markdown Reports** - Generates detailed reports saved to `docs/superpowers/reports/`

### Usage

**Via Web Interface:**
1. Navigate to BacktestCenter page
2. Run a backtest for your strategy
3. Switch to "Strategy Diagnosis" tab
4. Click "Run Diagnosis" button
5. Review diagnostic results and optimization suggestions

**Via API:**

```bash
# Run diagnosis
curl -X POST http://127.0.0.1:5001/api/diagnosis/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600000.SH",
    "strategyName": "MA Cross Strategy",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "benchmark": "000300.SH"
  }'

# Health check
curl http://127.0.0.1:5001/api/diagnosis/health
```

### Response Format

```json
{
  "success": true,
  "data": {
    "diagnosisId": "diag_20260526_123456",
    "overallRating": "B",
    "ratings": {
      "return": "A",
      "risk": "B",
      "stability": "B",
      "efficiency": "C"
    },
    "strengths": [
      "年化收益率 18.5% 显著超越基准 12.3%",
      "胜率 65% 表现优秀"
    ],
    "weaknesses": [
      "最大回撤 -25% 偏高，需要优化止损策略"
    ],
    "suggestions": [
      "建议添加动态止损机制，将最大回撤控制在 -20% 以内",
      "考虑增加仓位管理规则，在高波动期降低仓位"
    ],
    "conclusion": "该策略在收益表现上优于基准，但风险控制有待加强。建议优化止损和仓位管理后再投入实盘。",
    "reportPath": "docs/superpowers/reports/2026-05-26-ma-cross-600000-diagnosis.md"
  }
}
```

### Rating System

**Overall Rating (A/B/C/D):**
- **A (Excellent)**: 3+ A ratings, no D ratings
- **B (Good)**: 2+ A/B ratings, max 1 D rating
- **C (Fair)**: 2+ B/C ratings, max 2 D ratings
- **D (Poor)**: 2+ D ratings or critical failures

**Dimension Ratings:**
- **Return**: Total return, annual return, win rate
- **Risk**: Max drawdown, volatility, downside risk
- **Stability**: Sharpe ratio, Calmar ratio, consistency
- **Efficiency**: Trade frequency, profit factor, average holding period

### Report Location

Diagnostic reports are saved to:
```
docs/superpowers/reports/YYYY-MM-DD-{strategy}-{symbol}-diagnosis.md
```

### API Endpoints

- `POST /api/diagnosis/run` - Run strategy diagnosis
- `GET /api/diagnosis/health` - Health check endpoint

### Implementation Files

- **Service**: `services/diagnosis_service.py` - Core diagnosis logic
- **Analyzer**: `services/strategy_analyzer.py` - Rating calculation
- **Report Generator**: `services/report_generator.py` - Markdown report generation
- **API Routes**: `api/routes/diagnosis.py` - HTTP endpoints
- **Tests**: `tests/test_diagnosis_service.py`, `tests/test_strategy_analyzer.py`, `tests/test_report_generator.py`

### Performance

- Diagnosis time: < 2 seconds for typical backtest results
- Report generation: < 500ms
- Supports concurrent diagnosis requests

---

## Market Style Detection API

### GET /api/market/style

Get current market style detection results.

**Query Parameters:**
- `trade_date` (optional): Trading date in YYYY-MM-DD format, defaults to today

**Response:**
```json
{
  "success": true,
  "data": {
    "tradeDate": "2026-06-01",
    "style": "momentum",
    "confidence": 0.68,
    "metrics": {
      "rsi_avg": 58.3,
      "macd_golden_ratio": 0.65,
      "atr_percentile": 72,
      "volume_growth": 1.15
    },
    "scores": {
      "momentum": 75,
      "oscillation": 42,
      "low_volatility": 28,
      "value": 35
    }
  }
}
```

**Market Styles:**
- `momentum` - Strong trending market with high momentum
- `oscillation` - Range-bound market with frequent reversals
- `low_volatility` - Stable market with low price fluctuations
- `value` - Value-driven market with fundamental focus
- `unknown` - Insufficient data or unclear pattern

### GET /api/strategies/{strategy_name}/weight

Get strategy weight adjustment for current market style.

**Path Parameters:**
- `strategy_name`: Strategy name

**Query Parameters:**
- `market_style` (required): Market style (momentum/oscillation/low_volatility/value)
- `strategy_type` (optional): Strategy type, auto-detected if not provided

**Response:**
```json
{
  "success": true,
  "data": {
    "strategyName": "my_ma_cross",
    "strategyType": "trend_following",
    "marketStyle": "momentum",
    "weight": 1.30
  }
}
```

**Weight Interpretation:**
- `> 1.0`: Strategy performs well in this market style (increase position)
- `= 1.0`: Neutral performance (maintain position)
- `< 1.0`: Strategy underperforms in this market style (reduce position)
- `= 0.0`: No historical data available (use default weight)

**Scheduled Updates:**
- Market style detection runs daily at 15:30 (30 minutes after market close)
- Results are cached in database for fast API access
- Task ID: `update_market_style`
- Logs: `/tmp/quantsys-v2.log`

## Documentation

- [RL Module Documentation](quantlib/rl/README.md) - Base RL abstractions
- [FinRL Documentation](quantlib/finrl/README.md) - FinRL integration guide
- [Qlib Documentation](quantlib/qlib/README.md) - Qlib integration guide
- [Data Recovery Report](docs/data-recovery-report.md) - Data backfill and scheduler setup
- [Scheduler Analysis](docs/scheduler-analysis.md) - Scheduler root cause analysis
- [Migration Reports](docs/superpowers/reports/) - Implementation reports
- [CLAUDE.md](CLAUDE.md) - Project instructions for Claude Code

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific module tests
pytest tests/quantlib/rl/ -v
```

## License

Proprietary - All rights reserved

---

**Built with ❤️ by the QuantSys Team**
