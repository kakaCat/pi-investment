# DRAFT — application-services-bc-split

> Resume point for the ulw-plan workflow. Status: awaiting-approval.

## Intent
- intent: clear
- review_required: false
- target problem: #1 `application/services` 扁平化 (from domain-division review)
- depth: 深层限界上下文拆分 (subdomain packages + interfaces / dependency inversion)

## Decisions (adopted defaults + owner answers)
- Owner answered 2026-08-24:
  - Target problem = `#1 application/services 扁平化`.
  - Depth = `深层限界上下文拆分` (introduce subdomain packages AND subdomain interfaces/ports + DI wiring).
- Mechanical move is script-driven, not hand-edits (894 refs / 336 files). A single idempotent AST-based script performs move + import rewrite + config/yaml update in one pass.
- **Preserve the lazy-import discipline** mandated by `application/services/__init__.py` (2026-08-20 segfault fix): new `application/<sub>/services/__init__.py` and `application/<sub>/__init__.py` must NOT eagerly re-export heavy services (no `from .heavy import X` at module top). Module-level singletons (e.g. `order_service`) keep their lazy `from application.<sub>.services import order_service` import style.
- Old `application/services/` directory is removed after the move (all 894 references rewritten in the same pass), so there is exactly one path per service.
- Scope is limited to problem #1 only. Doc drift (#4), quantlib dedup (#2), domain cross-layer violations (#3) are NOT in scope (separate plans).

## Proposed subdomain taxonomy (bounded contexts under `application/`)
Each subdomain becomes `application/<sub>/services/...` (existing nested subdirs preserved under their owner subdomain).

1. `core` — base_service, core_async_services, stock_code_validator, report_generator
2. `data` — data_service, data_service_orm, data_validator, data_gap_detector, data_backfiller, data_quality_service, data_pipeline_service, dividend_service, dividend_data_source, financial_data_service, enhanced_financial_data_service, financial_analysis_service, financial_providers/, stock_data_service, valuation_data_service, realtime_quote_service, realtime_quote_service_v2, quote_providers/
3. `market` — market_data_service, hk_market_data_service, market_style_detector, market_regime_detector, market_sentiment_service, market_monitor_scheduler, sentiment_service, lhb_service
4. `pool` — stock_pool_service, stock_pool_async_service, pool_scanner_service, pool_scan_scheduler, pool_signal_scanner, pool_validation_service, pool_health_tracker
5. `strategy` — strategy_service, strategy_code_service, strategy_code_service_factor_patch, strategy_code_validator, strategy_executor, strategy_execution_service, strategy_factor_injector, strategy_optimizer, strategy_performance_stats, strategy_rotation_engine, strategy_validation_service, strategy_weight_adjuster, strategy_analyzer, strategy_backtest_service, strategy_discovery_service, strategy_circuit_breaker, strategy_engine/, search_space, enhanced_buy_range_service, combo_strategy_backtest_service
6. `risk` — risk_service, risk_metrics_service, risk_check_service, enhanced_risk_assessor, circuit_breaker_alert_service
7. `factor` — factor_analysis_service, factor_layering_service, factor_selector
8. `signal` — signal_processor, signal_monitoring, signal_test_log, signal_execution_scheduler, signal_execution_async_scheduler, realtime_signal_service
9. `scheduler` — scheduler, scheduler_tasks, scheduler_config_service, scheduler_handlers, smart_scheduler, enterprise_scheduler
10. `analysis` — analysis_services, technical_analysis_service, heatmap_service, opportunity_scoring_service, quality_scoring_service, stock_scoring_service, configurable_scoring_service, scoring/, stock_screening_service, sector_rotation_service, swing_point_service, benchmark_service, benchmark_comparison
11. `backtest` — backtest_async_engine, simulation_service
12. `game` — game_alert_service, manipulation_detector, opponent_behavior_service, battlefield_assessor
13. `execution` — order_service, account_trading_service, trade_service, execution_service, position_service, portfolio_optimization_service, trading_calendar_service
14. `monitoring` — watch_engine/, intraday_monitor, condition_monitor
15. `ml` — ml_pipeline/, ml_train_task, ml_train_notification, ml_weight_optimizer, qlib/
16. `intelligence` — decision_service, decision_evaluator, knowledge_service, experience_accumulator, attribution_analyzer, diagnosis_service, evolution/, performance_tracker
17. `integration` — feishu_service, llm_service, agent_notification_service, agent_os_client, agent_scheduler_tool, session_service, registry_client
18. `orchestration` — daily_orchestrator, task_orchestrator

(The full per-file manifest will be emitted 1:1 into the plan file after approval; the taxonomy above is the contract.)

## Approach (phased, each phase independently green)
- Phase 0 — Tooling: add `scripts/refactor/split_app_services.py` (AST-based, idempotent, dry-run + check modes) encoding the manifest. Rewrites `application.services.X` / `from application.services import X` / `import application.services.X` across the repo; updates `config/services.yaml`; generates lazy `__init__.py` per subdomain; removes old `application/services/`.
- Phase 1 — Structural move (behavior-preserving): run script; fix `infrastructure/services/service_factory.py`, `service_registry.py`, `infrastructure/di/container*.py` import paths; verify pytest + import smoke + zero `application.services` refs in code.
- Phase 2 — Interface/port extraction (the "deep" part): per subdomain add `application/<sub>/ports.py` (Protocols) for cross-boundary hub services; convert cross-subdomain deps to depend on the interface (resolved via EnhancedServiceFactory / config/services.yaml); within-subdomain concrete imports stay.
- Phase 3 — Facade & cleanup: curated lazy public API per subdomain; top-level `application/__init__.py` aggregator; confirm no stale dual path.

## Verification strategy (agent-executed, zero human intervention)
- Per phase: `pytest -q` must pass; `python -c "import application"` and import every subdomain package (no circular import, no OpenMP segfault regression); `grep -rn "application\.services" --include=*.py .` returns 0 in source (docs excluded).
- DI smoke: `ServiceFactory.get_data_service()` + `register_all_services()` succeed; one FastAPI route import resolves.

## Approval gate
status: awaiting-approval
approach: as above (phased, script-driven, scope = #1 only, deep BC split)
next: on explicit okay, write `.omo/plans/application-services-bc-split.md` with full `## Todos` + `## Final verification wave`, then stop.
