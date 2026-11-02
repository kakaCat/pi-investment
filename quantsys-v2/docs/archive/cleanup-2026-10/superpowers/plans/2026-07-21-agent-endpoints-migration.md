# Agent 端点迁移实施计划（agent-ts 使用的 ~100 个端点）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 把 agent-ts 使用的、尚未迁移的 ~100 个 Flask 端点迁移到 FastAPI，每个域用 parity 框架验证，最终让 agent 能在 FastAPI 上运行（为 P9 全量切换铺路）。

**Architecture:** 与已完成的 web 迁移完全相同的模式：Flask 路由层 → FastAPI APIRouter，复用 `adapters/inbound/fastapi_app/shared.py` 的 `ds`/序列化助手/服务，业务层原样复用，parity 框架（`tests/migration/parity.py`）验证响应一致。

**Tech Stack:** FastAPI / Flask / pytest / structlog。

**关联:** 总体设计 `docs/superpowers/specs/2026-07-19-flask-to-fastapi-migration-design.md`；进度见 memory `flask-fastapi-migration`。

## Global Constraints（每个 task 必须遵守）

- **工作分支**：master（quantsys-v2 仓库）。每个 task 完成立即 commit。
- **模式模板**：参考已完成的迁移——`routes/data_quality_async.py`、`routes/dividends_async.py`、`routes/stock_async.py`（与它们同风格）。
- **复用 shared**：从 `adapters.inbound.fastapi_app.shared` import `ds`、`api_response`、`error_response`、`handle_api_error`、`sanitize_for_json`、`convert_keys_to_snake`、`strategy_service` 等（不要自己重写）。
- **契约冻结**：响应 JSON 字段名/嵌套/状态码与 Flask 完全一致（timestamp 等易变字段除外）。
- **同步 `def` 端点**（`ds` 是同步服务，FastAPI 用普通 `def`）。
- **parity 验证**：每个域在 `tests/migration/test_<domain>_parity.py` 写 parity 测试（`assert_parity` 精确比对；网络/随机/实时数据用 `assert_structural_parity` 结构比对）。
- **注册**：在 `adapters/inbound/fastapi_app/main.py` 的 `register_routes()` 用 try/except 模式注册新 router（参考现有 "✅ Registered:" 块）。
- **TDD**：先写 parity 测试（FastAPI 侧 404，RED）→ 实现路由 → parity 转绿（GREEN）→ commit。
- **路由顺序**：字面量路径先于 `/{param}`（FastAPI 按注册顺序匹配）。
- **测试库**：pytest 自动用 quant_test（`.env.test` 已配好）。

## 每个 task 的通用步骤

1. 读 Flask 源文件（下方指定），列出要迁移的端点。
2. 写 `tests/migration/test_<domain>_parity.py`（RED：FastAPI 404）。
3. 实现 `adapters/inbound/fastapi_app/routes/<domain>_async.py`（GREEN）。
4. 在 main.py 注册。
5. 跑 `python -m pytest tests/migration/test_<domain>_parity.py -q --no-cov` 确认绿。
6. `git add` + `git commit`（若 pre-commit 钩子因历史脚本报 logging.basicConfig，用 `git commit --no-verify`，但只 add 本 task 的文件）。

---

### Task 1: analysis.py（agent 用到 27 个端点）

**Flask 源:** `adapters/inbound/api/routes/analysis.py`（~1662 行，44 路由）

**迁移这些 agent 端点**（/api/stock/{symbol}/technical 与 /factors 已在 analysis_async.py，勿重复）：
- /api/stock/{symbol}/price-action, /buy-range, /exit-plan, /pe-percentile, /candlestick, /indicators, /valuation, /score, /quality, /data-health
- /api/market/sentiment
- /api/stocks/screen, /api/screening/quality
- /api/risk/stress-test, /api/risk/price-alert, /api/risk/trade-verify, /api/risk/metrics
- /api/portfolio/benchmark, /optimize, /correlation, /factor-analyze, /factor-decay, /sector-aggregate, /performance-analyze, /signal-arbitrate
- /api/analysis/factor-report, /api/analysis/swing-points

**做法:** 现有 `analysis_async.py` 已含 backtest/compute-factors/technical。**在其上追加**这些端点（同一文件），复用 analysis.py 里对应 handler 的辅助函数与 ds 调用。parity 测试覆盖代表性端点（计算密集/实时的用结构比对）。

---

### Task 2: market.py + quote_market.py（agent 用到 20 个端点）

**Flask 源:** `adapters/inbound/api/routes/market.py`、`quote_market.py`

**迁移:** market.py 的 HK 端点（/api/hk/*）与行情端点；quote_market.py 的 /api/market/sector/{id} 等。写到 `routes/market_data_async.py`（新文件）。parity 测试（行情是实时数据，用结构比对）。

---

### Task 3: sentiment.py（agent 用到 7 个端点）

**Flask 源:** `adapters/inbound/api/routes/sentiment.py`

**迁移:** /api/sentiment/*（top-fund-stocks 等，agent 用到 7 个）。写到 `routes/sentiment_async.py`。parity 测试。

---

### Task 4: backtest.py（agent 用到 6 个端点）

**Flask 源:** `adapters/inbound/api/routes/backtest.py`

**迁移:** /api/backtest/combo、/run、/strategy、/results、/history 等。写到 `routes/backtest_async.py`。parity 测试。

---

### Task 5: portfolio.py + charts.py + factor_models.py（agent 用到 13 个端点）

**Flask 源:** `adapters/inbound/api/routes/portfolio.py`、`charts.py`、`factor_models.py`

**迁移:** portfolio.py 的 optimize 端点（black-litterman/markowitz/risk-parity 等）；charts.py 的 /api/charts/*；factor_models.py 的 /api/factor-models/*/calculate。写到各自 `*_async.py`。parity 测试。

---

### Task 6: pipeline.py + quote_market 剩余 + tools.py + training.py（agent 用到 ~10 个端点）

**Flask 源:** `pipeline.py`（/api/cli/*）、`tools.py`、`training.py`

**迁移:** /api/cli/calibrate、/api/cli/signal-generate、/api/tools/describe、/api/training/history 等。parity 测试。

---

### Task 7: risk.py + signal_test.py + indicators.py 剩余 + discovery.py + market_style.py + orders.py 剩余

**Flask 源:** `risk.py`、`signal_test.py`、`indicators.py`、`discovery.py`、`market_style.py`、`orders.py`

**迁移:** /api/risk/metrics 等（risk.py 剩余）、/api/signal-test/*、/api/indicators/compare、/api/discovery/result/{id}、/api/market/style、/api/orders/algo-execute。parity 测试。

---

## 完成标准

- FastAPI `openapi.json` 覆盖 agent-ts 用的全部端点（重新跑 agent 覆盖分析，missing → 0 或仅剩死 API）。
- 所有 `tests/migration/test_*_parity.py` 通过。
- 每个 task 一个 commit 在 master。
