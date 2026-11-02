# 硬编码依赖扫描报告

**扫描日期**: 2026-08-21
**扫描目录**: quantsys-v2/application/services
**扫描文件数**: 59
**发现问题数**: 151

## 问题详情

### application/services/data_service.py

问题数: 11

- **L40** [high] 直接实例化: IStockRepository()
- **L40** [high] 直接实例化: IKlineRepository()
- **L40** [high] 直接实例化: ISignalRepository()
- **L40** [high] 直接实例化: ISimulationRepository()
- **L40** [high] 直接实例化: IPortfolioRepository()
- **L40** [high] 直接实例化: IFactorRepository()
- **L40** [high] 直接实例化: IBacktestRepository()
- **L40** [high] 直接实例化: IRiskRepository()
- **L40** [high] 直接实例化: IStrategyRepository()
- **L40** [high] 直接实例化: ISignalExecutionRepository()
- **L40** [high] 直接实例化: FinancialDataService()

### application/services/data_service_orm.py

问题数: 10

- **L52** [high] 直接实例化: IStockRepository()
- **L52** [high] 直接实例化: IKlineRepository()
- **L52** [high] 直接实例化: ISignalRepository()
- **L52** [high] 直接实例化: ISimulationRepository()
- **L52** [high] 直接实例化: IPortfolioRepository()
- **L52** [high] 直接实例化: IFactorRepository()
- **L52** [high] 直接实例化: IBacktestRepository()
- **L52** [high] 直接实例化: IRiskRepository()
- **L52** [high] 直接实例化: ISignalExecutionRepository()
- **L52** [high] 直接实例化: FinancialDataService()

### application/services/signal_execution_scheduler.py

问题数: 7

- **L33** [high] 直接实例化: DataService()
- **L33** [high] 直接实例化: StrategyCodeService()
- **L33** [high] 直接实例化: RiskCheckService()
- **L33** [high] 直接实例化: ISignalRepository()
- **L33** [high] 直接实例化: ISignalExecutionLogRepository()
- **L33** [high] 直接实例化: IStrategyRepository()
- **L470** [high] 直接实例化: StockPoolService()

### application/services/ml_train_task.py

问题数: 7

- **L21** [high] 方法内部调用 ServiceFactory.get_stock_repository()
- **L21** [high] 方法内部调用 ServiceFactory.get_data_service()
- **L21** [high] 方法内部调用 ServiceFactory.get_ml_model_metadata_repository()
- **L176** [high] 方法内部调用 ServiceFactory.get_ml_model_repository()
- **L176** [high] 方法内部调用 ServiceFactory.get_ml_model_metadata_repository()
- **L215** [high] 方法内部调用 ServiceFactory.get_ml_model_repository()
- **L215** [high] 方法内部调用 ServiceFactory.get_ml_model_metadata_repository()

### application/services/daily_orchestrator.py

问题数: 5

- **L158** [high] 直接实例化: AccountTradingService()
- **L288** [high] 直接实例化: ISimulationRepository()
- **L344** [high] 直接实例化: ISimulationRepository()
- **L344** [high] 直接实例化: DataService()
- **L413** [high] 直接实例化: ISimulationRepository()

### application/services/configurable_scoring_service.py

问题数: 5

- **L104** [high] 直接实例化: StockScoringService()
- **L173** [high] 直接实例化: StockScoringService()
- **L224** [high] 直接实例化: StockScoringService()
- **L264** [high] 直接实例化: StockScoringService()
- **L298** [high] 直接实例化: StockScoringService()

### application/services/realtime_quote_service_v2.py

问题数: 5

- **L148** [high] 直接实例化: TencentQuoteProvider()
- **L148** [high] 直接实例化: EastmoneyQuoteProvider()
- **L148** [high] 直接实例化: SinaQuoteProvider()
- **L148** [high] 直接实例化: AkshareQuoteProvider()
- **L148** [high] 直接实例化: NeteaseQuoteProvider()

### application/services/battlefield_assessor.py

问题数: 4

- **L18** [high] 直接实例化: IStockPoolRepository()
- **L18** [high] 直接实例化: IFundFlowRepository()
- **L18** [high] 直接实例化: IAgentIntelligenceRepository()
- **L18** [high] 直接实例化: OpponentBehaviorService()

### application/services/account_trading_service.py

问题数: 4

- **L36** [high] 直接实例化: ISimulationRepository()
- **L36** [high] 直接实例化: TradingCalendarService()
- **L46** [high] 直接实例化: RealtimeQuoteService()
- **L340** [high] 直接实例化: DecisionService()

### application/services/factor_layering_service.py

问题数: 4

- **L26** [high] 直接实例化: IKlineRepository()
- **L26** [high] 直接实例化: IStockRepository()
- **L26** [high] 直接实例化: StockPoolService()
- **L227** [high] 方法内部导入适配器: domain.quantlib.adapters

### application/services/manipulation_detector.py

问题数: 4

- **L17** [high] 直接实例化: IAgentIntelligenceRepository()
- **L17** [high] 直接实例化: IFundFlowRepository()
- **L139** [high] 方法内部调用 ServiceFactory.get_data_provider_manager()
- **L218** [high] 方法内部调用 ServiceFactory.get_data_provider_manager()

### application/services/decision_evaluator.py

问题数: 3

- **L18** [high] 直接实例化: IAgentIntelligenceRepository()
- **L18** [high] 直接实例化: IStockPoolRepository()
- **L18** [high] 直接实例化: KnowledgeService()

### application/services/chan_knowledge_distiller.py

问题数: 3

- **L38** [high] 直接实例化: ISignalRepository()
- **L38** [high] 直接实例化: IKlineRepository()
- **L38** [high] 直接实例化: IAgentKnowledgeRepository()

### application/services/strategy_executor.py

问题数: 3

- **L21** [high] 直接实例化: IStrategyRepository()
- **L21** [high] 直接实例化: IKlineRepository()
- **L21** [high] 直接实例化: ISignalRepository()

### application/services/financial_data_service.py

问题数: 3

- **L198** [high] 直接实例化: IFinancialRepository()
- **L198** [high] 直接实例化: IKlineRepository()
- **L322** [high] 直接实例化: IFinancialRepository()

### application/services/chan_scan_service.py

问题数: 3

- **L30** [high] 直接实例化: ChanService()
- **L30** [high] 直接实例化: IStockPoolRepository()
- **L30** [high] 直接实例化: ISignalRepository()

### application/services/enhanced_risk_assessor.py

问题数: 3

- **L19** [high] 直接实例化: IStockPoolRepository()
- **L19** [high] 直接实例化: IFundFlowRepository()
- **L19** [high] 直接实例化: OpponentBehaviorService()

### application/services/watch_engine/factory.py

问题数: 3

- **L44** [high] 直接实例化: AgentNotificationService()
- **L44** [high] 直接实例化: WatchTriggerRepository()
- **L44** [high] 直接实例化: WatchRuleRepository()

### application/services/evolution/missed_opportunity_service.py

问题数: 3

- **L32** [high] 直接实例化: ISignalRepository()
- **L32** [high] 直接实例化: IAgentIntelligenceRepository()
- **L32** [high] 直接实例化: IKlineRepository()

### application/services/ml_train_notification.py

问题数: 2

- **L203** [high] 方法内部调用 ServiceFactory.get_ml_model_repository()
- **L203** [high] 方法内部调用 ServiceFactory.get_ml_model_metadata_repository()

### application/services/feishu_service.py

问题数: 2

- **L451** [high] 直接实例化: FeishuNotificationService()
- **L459** [high] 硬编码服务调用: get_feishu_service()

### application/services/enhanced_financial_data_service.py

问题数: 2

- **L29** [high] 直接实例化: FinancialDataService()
- **L302** [high] 直接实例化: EnhancedFinancialDataService()

### application/services/diagnosis_service.py

问题数: 2

- **L26** [high] 直接实例化: IBacktestRepository()
- **L26** [high] 直接实例化: IKlineRepository()

### application/services/strategy_service.py

问题数: 2

- **L37** [high] 直接实例化: ISimulationRepository()
- **L42** [high] 直接实例化: ISimulationRepository()

### application/services/game_alert_service.py

问题数: 2

- **L19** [high] 直接实例化: IFundFlowRepository()
- **L19** [high] 直接实例化: OpponentBehaviorService()

### application/services/data_gap_detector.py

问题数: 2

- **L21** [high] 直接实例化: IKlineRepository()
- **L21** [high] 直接实例化: TradingCalendarService()

### application/services/simulation_service.py

问题数: 2

- **L17** [high] 直接实例化: ISimulationRepository()
- **L233** [high] 直接实例化: RealtimeQuoteService()

### application/services/condition_monitor.py

问题数: 2

- **L33** [high] 直接实例化: IConditionRuleRepository()
- **L33** [high] 直接实例化: IConditionResultRepository()

### application/services/strategy_weight_adjuster.py

问题数: 2

- **L24** [high] 直接实例化: IStrategyWeightRepository()
- **L24** [high] 直接实例化: IStrategyPerformanceRepository()

### application/services/decision_service.py

问题数: 2

- **L20** [high] 直接实例化: IAgentIntelligenceRepository()
- **L20** [high] 直接实例化: IPoolChangeLogRepository()

### application/services/smart_scheduler.py

问题数: 2

- **L35** [high] 直接实例化: ISchedulerConfigRepository()
- **L404** [high] 直接实例化: SmartSchedulerService()

### application/services/opponent_behavior_service.py

问题数: 2

- **L18** [high] 直接实例化: IAgentIntelligenceRepository()
- **L18** [high] 直接实例化: IFundFlowRepository()

### application/services/chan_service.py

问题数: 2

- **L14** [high] 直接实例化: IKlineRepository()
- **L80** [high] 直接实例化: IAgentKnowledgeRepository()

### application/services/realtime_signal_service.py

问题数: 2

- **L22** [high] 直接实例化: MarketDataService()
- **L116** [high] 直接实例化: StrategyExecutionService()

### application/services/data_pipeline_service.py

问题数: 2

- **L209** [high] 直接实例化: IKlineRepository()
- **L209** [high] 直接实例化: IFactorRepository()

### application/services/intraday_monitor.py

问题数: 2

- **L143** [high] 直接实例化: DataService()
- **L163** [high] 直接实例化: DataService()

### application/services/data_quality_service.py

问题数: 2

- **L24** [high] 直接实例化: IKlineRepository()
- **L24** [high] 直接实例化: TradingCalendarService()

### application/services/technical_analysis_service.py

问题数: 2

- **L149** [high] 直接实例化: IKlineRepository()
- **L235** [high] 直接实例化: IKlineRepository()

### application/services/evolution/evolution_fitness_service.py

问题数: 2

- **L21** [high] 直接实例化: ISimulationRepository()
- **L21** [high] 直接实例化: EvolutionFitnessORMRepository()

### application/services/evolution/decision_score_service.py

问题数: 2

- **L39** [high] 直接实例化: IAgentIntelligenceRepository()
- **L39** [high] 直接实例化: IKlineRepository()

### application/services/benchmark_comparison.py

问题数: 1

- **L124** [high] 直接实例化: MarketDataService()

### application/services/strategy_discovery_service.py

问题数: 1

- **L311** [high] 直接实例化: StrategyCodeService()

### application/services/pool_health_tracker.py

问题数: 1

- **L18** [high] 直接实例化: IStockPoolRepository()

### application/services/stock_code_validator.py

问题数: 1

- **L25** [high] 直接实例化: IKlineRepository()

### application/services/data_validator.py

问题数: 1

- **L24** [high] 直接实例化: IKlineRepository()

### application/services/strategy_circuit_breaker.py

问题数: 1

- **L41** [high] 直接实例化: IStrategyCircuitBreakerRepository()

### application/services/scheduler_config_service.py

问题数: 1

- **L28** [high] 直接实例化: ISchedulerConfigRepository()

### application/services/order_service.py

问题数: 1

- **L478** [high] 直接实例化: IStrategyPerformanceRepository()

### application/services/experience_accumulator.py

问题数: 1

- **L22** [high] 直接实例化: IStrategyPerformanceRepository()

### application/services/knowledge_service.py

问题数: 1

- **L20** [high] 直接实例化: IAgentKnowledgeRepository()

### application/services/heatmap_service.py

问题数: 1

- **L17** [high] 直接实例化: IHeatmapRepository()

### application/services/trading_calendar_service.py

问题数: 1

- **L24** [high] 直接实例化: IKlineRepository()

### application/services/risk_check_service.py

问题数: 1

- **L27** [high] 直接实例化: IRiskConfigRepository()

### application/services/enterprise_scheduler.py

问题数: 1

- **L228** [high] 直接实例化: ISchedulerRepository()

### application/services/swing_point_service.py

问题数: 1

- **L29** [high] 直接实例化: IKlineRepository()

### application/services/agent_scheduler_tool.py

问题数: 1

- **L405** [high] 直接实例化: AgentNotificationService()

### application/services/performance_tracker.py

问题数: 1

- **L30** [high] 直接实例化: ISimulationRepository()

### application/services/attribution_analyzer.py

问题数: 1

- **L17** [high] 直接实例化: IStockPoolRepository()

### application/services/scoring/regime_signal_provider.py

问题数: 1

- **L35** [high] 硬编码服务调用: get_cache_service()

