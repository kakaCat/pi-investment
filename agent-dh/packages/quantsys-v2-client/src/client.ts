import axios, { AxiosInstance } from 'axios';
import axiosRetry from 'axios-retry';
import type {
  Stock,
  KlineData,
  Strategy,
  BacktestRequest,
  BacktestResult,
  Pool,
  PoolMember,
  Signal,
  QuantsysV2ClientConfig,
  QuoteData,
  FinancialData,
  WatchRule,
  Position,
  PortfolioSummary,
  EvolutionLeaderboard,
  EvolutionDecisionScores,
  StrategyListResponse,
  // P0 missing method types
  TradeRequest,
  TradeResponse,
  AlgoExecuteRequest,
  AlgoExecuteResponse,
  TradeHistoryResponse,
  TradeVerifyResponse,
  Alert,
  WatchRuleManageRequest,
  SectorAnalysisResponse,
  RiskMetrics,
  RiskControlRequest,
  BarraDecompositionResponse,
  SignalGenerateRequest,
  OpportunityScanRequest,
  Opportunity,
  ScreenRequest,
  ScreenResponse,
  RotationProposalRequest,
  RotationProposal,
  RotationSimulateRequest,
  RotationSimulateResponse,
  RotationExecuteRequest,
  RotationExecuteResponse,
  FactorCalculateRequest,
  FactorData,
  FactorAnalyzeRequest,
  FactorAnalysisResponse,
  ModelPredictRequest,
  ModelPrediction,
  DataQualityReportRequest,
  DataQualityReportResponse,
  DataManagerRequest,
  DataManagerResponse,
  MacroData,
  NorthFlowDay,
  MarketSentiment,
} from './types.js';

/**
 * QuantsysV2 API Client
 */
export class QuantsysV2Client {
  private client: AxiosInstance;

  constructor(config: QuantsysV2ClientConfig) {
    this.client = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        ...config.headers,
      },
    });

    // Configure retry mechanism
    axiosRetry(this.client, {
      retries: 3,
      retryDelay: axiosRetry.exponentialDelay,
      retryCondition: (error) => {
        // Retry on network errors or 5xx server errors
        return axiosRetry.isNetworkOrIdempotentRequestError(error) ||
               (error.response?.status ? error.response.status >= 500 : false);
      },
      onRetry: (retryCount, error, requestConfig) => {
        console.log(
          `[QuantsysV2Client] Retrying request (${retryCount}/3): ${requestConfig.method?.toUpperCase()} ${requestConfig.url} - ${error.message}`
        );
      },
    });
  }

  /**
   * Unwrap response envelope based on endpoint-specific patterns
   */
  private unwrap<T>(response: any, endpoint: string): T {
    // Check for success: false
    if (response.success === false) {
      throw new Error(response.error || `API request failed: ${endpoint}`);
    }

    // Pattern 1: {success, data}
    if (response.success === true && 'data' in response) {
      return response.data as T;
    }

    // Pattern 2: {success, rules} - watch/rules endpoint
    if (response.success === true && 'rules' in response) {
      return response.rules as T;
    }

    // Pattern 3: No envelope (klines returns {symbol, count, klines})
    return response as T;
  }

  // ==================== Stock APIs ====================

  /**
   * Search stocks
   */
  async searchStocks(query: string): Promise<Stock[]> {
    const response = await this.client.get('/api/stocks/search', {
      params: { q: query },
    });
    return this.unwrap(response.data, 'searchStocks');
  }

  /**
   * Get K-line data
   * Real endpoint: GET /api/stock/{symbol}/klines
   * Response: {symbol, count, klines: [...]} - no success envelope
   */
  async getKlines(
    symbol: string,
    startDate: string,
    endDate: string,
    period: 'daily' | 'weekly' | 'monthly' = 'daily',
    limit?: number
  ): Promise<KlineData[]> {
    const response = await this.client.get(`/api/stock/${symbol}/klines`, {
      params: { start_date: startDate, end_date: endDate, period, limit },
    });
    // Special case: no success envelope, direct {symbol, count, klines}
    return response.data.klines || [];
  }

  // ==================== Strategy APIs ====================

  /**
   * List strategies
   * Real endpoint: GET /api/strategies/list
   * Response: {success, data: {total, page, pageSize, items: [...]}}
   */
  async listStrategies(params?: {
    source?: 'builtin' | 'user';
    code_type?: string;
    page?: number;
    pageSize?: number;
  }): Promise<StrategyListResponse> {
    const response = await this.client.get('/api/strategies/list', {
      params,
    });
    return this.unwrap<StrategyListResponse>(response.data, 'listStrategies');
  }

  /**
   * Get strategy by ID
   */
  async getStrategy(id: number): Promise<Strategy> {
    const response = await this.client.get(`/api/strategies/${id}`);
    return this.unwrap(response.data, 'getStrategy');
  }

  /**
   * Create strategy
   */
  async createStrategy(strategy: Omit<Strategy, 'id'>): Promise<Strategy> {
    const response = await this.client.post('/api/strategies/create', strategy);
    return this.unwrap(response.data, 'createStrategy');
  }

  /**
   * Update strategy
   */
  async updateStrategy(id: number, updates: Partial<Strategy>): Promise<Strategy> {
    const response = await this.client.put(`/api/strategies/${id}`, updates);
    return this.unwrap(response.data, 'updateStrategy');
  }

  /**
   * Delete strategy
   */
  async deleteStrategy(id: number): Promise<void> {
    await this.client.delete(`/api/strategies/${id}`);
  }

  /**
   * Backtest strategy
   */
  async backtestStrategy(request: BacktestRequest): Promise<BacktestResult> {
    const response = await this.client.post(
      '/api/indicators/backtest',
      request
    );
    return this.unwrap(response.data, 'backtestStrategy');
  }

  /**
   * Optimize strategy parameters
   */
  async optimizeStrategy(params: {
    strategy_id: number;
    symbol: string;
    start_date: string;
    end_date: string;
    param_ranges: Record<string, number[]>;
  }): Promise<Array<{ parameters: Record<string, any>; result: BacktestResult }>> {
    const response = await this.client.post('/api/strategies/optimize', params);
    return this.unwrap(response.data, 'optimizeStrategy');
  }

  // ==================== Pool APIs ====================

  /**
   * List pools
   * Real endpoint: GET /api/pools
   * Response: {success, data: [...]}
   */
  async listPools(): Promise<Pool[]> {
    const response = await this.client.get('/api/pools');
    return this.unwrap<Pool[]>(response.data, 'listPools');
  }

  /**
   * Get pool by ID
   */
  async getPool(id: number): Promise<Pool> {
    const response = await this.client.get(`/api/pools/${id}`);
    return this.unwrap(response.data, 'getPool');
  }

  /**
   * Create pool
   */
  async createPool(pool: { name: string; description?: string }): Promise<Pool> {
    const response = await this.client.post('/api/pools', pool);
    return this.unwrap(response.data, 'createPool');
  }

  /**
   * Update pool
   */
  async updatePool(id: number, updates: Partial<Pool>): Promise<Pool> {
    const response = await this.client.put(`/api/pools/${id}`, updates);
    return this.unwrap(response.data, 'updatePool');
  }

  /**
   * Delete pool
   */
  async deletePool(id: number): Promise<void> {
    await this.client.delete(`/api/pools/${id}`);
  }

  /**
   * Get pool members
   */
  async getPoolMembers(poolId: number): Promise<PoolMember[]> {
    const response = await this.client.get(`/api/pools/${poolId}/members`);
    return this.unwrap(response.data, 'getPoolMembers');
  }

  /**
   * Add member to pool
   */
  async addPoolMember(
    poolId: number,
    member: { symbol: string; metadata?: Record<string, any> }
  ): Promise<void> {
    await this.client.post(`/api/pools/${poolId}/members`, member);
  }

  /**
   * Remove member from pool
   */
  async removePoolMember(poolId: number, symbol: string): Promise<void> {
    await this.client.delete(`/api/pools/${poolId}/members/${symbol}`);
  }

  /**
   * Refresh pool (re-scan members)
   */
  async refreshPool(poolId: number): Promise<void> {
    await this.client.post(`/api/pools/${poolId}/refresh`);
  }

  // ==================== Signal APIs ====================

  /**
   * List signals
   */
  async listSignals(params?: {
    symbol?: string;
    signal_type?: 'buy' | 'sell';
    start_date?: string;
    end_date?: string;
  }): Promise<Signal[]> {
    const response = await this.client.get('/api/signals', {
      params,
    });
    return this.unwrap(response.data, 'listSignals');
  }

  // ==================== Market Data APIs ====================

  /**
   * Get real-time quote
   * Real endpoint: GET /api/stock/{symbol}/quote?source=auto
   * Response: {success, data: {symbol, name, price, open, high, low, prevClose, volume, amount, change, changePct, source, timestamp}}
   */
  async getQuote(symbol: string, source: 'realtime' | 'db' | 'auto' = 'auto'): Promise<QuoteData> {
    const response = await this.client.get(`/api/stock/${symbol}/quote`, {
      params: { source },
    });
    return this.unwrap<QuoteData>(response.data, 'getQuote');
  }

  /**
   * Get market style
   * Real endpoint: GET /api/market/style
   * Real response data: {style, confidence, scores, indicators, recommendedFactors, detectionDate}
   */
  async getMarketStyle(): Promise<{
    style: string;
    confidence: number;
    scores: Record<string, number>;
    indicators: Record<string, number>;
    recommendedFactors: string[];
    detectionDate: string;
  }> {
    const response = await this.client.get('/api/market/style');
    return this.unwrap(response.data, 'getMarketStyle');
  }

  /**
   * Get macroeconomic data (GDP/CPI/PMI)
   * Real endpoint: GET /api/market/macro
   * Response: {success, data: {gdp: [...], cpi: [...], pmi: [...], updateTime}}
   */
  async getMacroData(): Promise<MacroData> {
    const response = await this.client.get('/api/market/macro');
    return this.unwrap<MacroData>(response.data, 'getMacroData');
  }

  /**
   * Get north-bound capital flow
   * Real endpoint: GET /api/market/north-flow?start_date=&end_date=
   * Response: {success, data: [{tradeDate, netFlow, shNetFlow, szNetFlow}]}
   * Note: upstream data source is slow (~50s cold); uses an extended timeout.
   */
  async getNorthFlow(startDate?: string, endDate?: string): Promise<NorthFlowDay[]> {
    const response = await this.client.get('/api/market/north-flow', {
      params: { start_date: startDate, end_date: endDate },
      timeout: 90000,
    });
    return this.unwrap<NorthFlowDay[]>(response.data, 'getNorthFlow');
  }

  /**
   * Get market sentiment
   * Real endpoint: GET /api/market/sentiment
   * Response: {success, data: {sentimentScore, sentimentLevel, fearGreedIndex, indicators, marketPhase, recommendation, ...}}
   */
  async getMarketSentiment(): Promise<MarketSentiment> {
    const response = await this.client.get('/api/market/sentiment');
    return this.unwrap<MarketSentiment>(response.data, 'getMarketSentiment');
  }

  // ==================== Analysis APIs ====================

  /**
   * Get chip distribution
   */
  async getChipDistribution(symbol: string): Promise<{
    symbol: string;
    date: string;
    profit_ratio: number;
    avg_cost: number;
    peak_price: number;
    concentration: number;
    cost_ranges: {
      p70_low: number;
      p70_high: number;
      p90_low: number;
      p90_high: number;
    };
  }> {
    const response = await this.client.get(`/api/analysis/chip-distribution/${symbol}`);
    return this.unwrap(response.data, 'getChipDistribution');
  }

  // ==================== Financial Data APIs ====================

  /**
   * Get financial data
   * Response: existing .data.data || .data fallback works
   */
  async getFinancialData(symbol: string, params?: {
    statement_type?: 'income' | 'balance' | 'cash_flow' | 'all';
    periods?: number;
    source?: 'auto' | 'fresh' | 'cache_only';
  }): Promise<FinancialData> {
    const response = await this.client.get(`/api/v2/stock/${symbol}/financials`, {
      params: {
        statement_type: params?.statement_type || 'all',
        periods: params?.periods || 4,
        source: params?.source || 'auto',
      },
    });
    // Keep existing fallback logic
    return response.data.data || response.data;
  }

  // ==================== Watch APIs ====================

  /**
   * List watch rules
   * Real endpoint: GET /api/watch/rules
   * Response: {success, rules: [...]} - key is 'rules' not 'data'
   */
  async listWatchRules(): Promise<WatchRule[]> {
    const response = await this.client.get('/api/watch/rules');
    return this.unwrap<WatchRule[]>(response.data, 'listWatchRules');
  }

  // ==================== Portfolio/Trading APIs ====================

  /**
   * Get portfolio positions
   * Real endpoint: GET /api/portfolio/positions?account_name=xxx
   * Response: {success, data: {positions: [...], count}}
   */
  async getPositions(accountName: string = 'agent_virtual'): Promise<Position[]> {
    const response = await this.client.get('/api/portfolio/positions', {
      params: { account_name: accountName },
    });
    const data = this.unwrap<{ positions: Position[]; count: number }>(response.data, 'getPositions');
    return data.positions || [];
  }

  /**
   * Get portfolio summary
   * Real endpoint: GET /api/portfolio/summary?account_name=xxx
   * Response: {success, data: {...}}
   */
  async getPortfolioSummary(accountName: string = 'agent_virtual'): Promise<PortfolioSummary> {
    const response = await this.client.get('/api/portfolio/summary', {
      params: { account_name: accountName },
    });
    return this.unwrap<PortfolioSummary>(response.data, 'getPortfolioSummary');
  }

  // ==================== Evolution APIs ====================

  /**
   * Get evolution leaderboard
   * Real endpoint: GET /api/evolution/leaderboard
   * Response: {success, data: {windowEnd, windowDays, ranking: [...]}}
   */
  async getEvolutionLeaderboard(): Promise<EvolutionLeaderboard> {
    const response = await this.client.get('/api/evolution/leaderboard');
    return this.unwrap<EvolutionLeaderboard>(response.data, 'getEvolutionLeaderboard');
  }

  /**
   * Get evolution decision scores
   * Real endpoint: GET /api/evolution/decision-scores
   * Response: {success, data: {total, items: [...]}}
   */
  async getEvolutionDecisionScores(): Promise<EvolutionDecisionScores> {
    const response = await this.client.get('/api/evolution/decision-scores');
    return this.unwrap<EvolutionDecisionScores>(response.data, 'getEvolutionDecisionScores');
  }

  // ==================== Trading APIs (P0) ====================

  /**
   * Execute a trade (virtual account)
   * Real endpoint: POST /api/orders/create
   */
  async executeTrade(params: TradeRequest): Promise<TradeResponse> {
    const response = await this.client.post('/api/orders/create', params);
    return this.unwrap<TradeResponse>(response.data, 'executeTrade');
  }

  /**
   * Get trade history
   * Real endpoint: GET /api/trades/list
   */
  async getTradeHistory(params?: {
    account_name?: string;
    order_id?: string;
    symbol?: string;
    direction?: string;
  }): Promise<TradeHistoryResponse> {
    const response = await this.client.get('/api/trades/list', { params });
    return this.unwrap<TradeHistoryResponse>(response.data, 'getTradeHistory');
  }

  /**
   * Execute algorithmic order (TWAP/VWAP)
   * Real endpoint: POST /api/orders/algo-execute
   */
  async executeAlgo(params: AlgoExecuteRequest): Promise<AlgoExecuteResponse> {
    const response = await this.client.post('/api/orders/algo-execute', params);
    return this.unwrap<AlgoExecuteResponse>(response.data, 'executeAlgo');
  }

  /**
   * Verify trades (reconciliation)
   * Real endpoint: POST /api/risk/trade-verify
   */
  async verifyTrades(params?: {
    account_name?: string;
    date?: string;
  }): Promise<TradeVerifyResponse> {
    const response = await this.client.post('/api/risk/trade-verify', params ?? {});
    return this.unwrap<TradeVerifyResponse>(response.data, 'verifyTrades');
  }

  // ==================== Intelligence APIs (P0) ====================

  /**
   * Manage watch rules (create/enable/disable/delete)
   * Real endpoints:
   *   POST   /api/watch/rules           (create)
   *   PATCH  /api/watch/rules/{id}      (enable/disable - update enabled field)
   *   DELETE /api/watch/rules/{id}      (delete)
   */
  async manageWatchRule(params: WatchRuleManageRequest): Promise<any> {
    const { action, rule_id, ...rest } = params;
    if (action === 'create') {
      const response = await this.client.post('/api/watch/rules', rest);
      return this.unwrap(response.data, 'manageWatchRule');
    }
    if (action === 'enable') {
      const response = await this.client.patch(`/api/watch/rules/${rule_id}`, { enabled: true });
      return this.unwrap(response.data, 'manageWatchRule');
    }
    if (action === 'disable') {
      const response = await this.client.patch(`/api/watch/rules/${rule_id}`, { enabled: false });
      return this.unwrap(response.data, 'manageWatchRule');
    }
    if (action === 'delete') {
      const response = await this.client.delete(`/api/watch/rules/${rule_id}`);
      return this.unwrap(response.data, 'manageWatchRule');
    }
    throw new Error(`Unknown watch rule action: ${action}`);
  }

  /**
   * Get market alerts
   * Real endpoint: GET /api/alerts/check
   */
  async getAlerts(params?: { level?: string; limit?: number }): Promise<Alert[]> {
    const response = await this.client.get('/api/alerts/check', { params });
    return this.unwrap<Alert[]>(response.data, 'getAlerts');
  }

  // ==================== Market APIs (P0) ====================

  /**
   * Get sector analysis
   * Real endpoint: GET /api/market/sectors
   */
  async getSectorAnalysis(params?: {
    sector?: string;
    days?: number;
    date?: string;
    window?: number;
    limit?: number;
  }): Promise<SectorAnalysisResponse> {
    const response = await this.client.get('/api/market/sectors', { params });
    return this.unwrap<SectorAnalysisResponse>(response.data, 'getSectorAnalysis');
  }

  // ==================== Risk APIs (P0) ====================

  /**
   * Risk control: position_size / stop_loss / portfolio_risk
   * Dispatches to different endpoints based on command.
   */
  async riskControl(params: RiskControlRequest): Promise<any> {
    const { command, symbol, account_name } = params;
    if (command === 'position_size') {
      const response = await this.client.post(`/api/stock/${symbol}/risk/position-size`, { account_name });
      return this.unwrap(response.data, 'riskControl');
    }
    if (command === 'stop_loss') {
      const response = await this.client.post(`/api/stock/${symbol}/risk/stop-loss`, { account_name });
      return this.unwrap(response.data, 'riskControl');
    }
    if (command === 'portfolio_risk') {
      const response = await this.client.post('/api/risk/check', { account_name });
      return this.unwrap(response.data, 'riskControl');
    }
    throw new Error(`Unknown risk control command: ${command}`);
  }

  /**
   * Calculate risk metrics
   * Real endpoint: POST /api/risk/metrics
   */
  async getRiskMetrics(params?: {
    account_name?: string;
    days?: number;
    returns?: number[];
    benchmark_returns?: number[];
    risk_free_rate?: number;
  }): Promise<RiskMetrics> {
    const response = await this.client.post('/api/risk/metrics', params ?? {});
    return this.unwrap<RiskMetrics>(response.data, 'getRiskMetrics');
  }

  /**
   * Barra risk decomposition
   * Real endpoint: POST /api/factor-models/barra/calculate
   */
  async getBarraDecomposition(params?: {
    account_name?: string;
    returns?: number[];
    positions?: any[];
  }): Promise<BarraDecompositionResponse> {
    const response = await this.client.post('/api/factor-models/barra/calculate', params ?? {});
    return this.unwrap<BarraDecompositionResponse>(response.data, 'getBarraDecomposition');
  }

  // ==================== Strategy APIs (P0) ====================

  /**
   * Generate trading signals
   * Real endpoint: POST /api/signals/scan
   */
  async generateSignals(params: SignalGenerateRequest): Promise<Signal[]> {
    const response = await this.client.post('/api/signals/scan', params);
    return this.unwrap<Signal[]>(response.data, 'generateSignals');
  }

  /**
   * Scan market opportunities
   * Real endpoint: POST /api/signals/scan
   */
  async scanOpportunities(params?: OpportunityScanRequest): Promise<Opportunity[]> {
    const response = await this.client.post('/api/signals/scan', params ?? {});
    return this.unwrap<Opportunity[]>(response.data, 'scanOpportunities');
  }

  /**
   * Screen stocks by filters
   * Real endpoint: GET /api/stocks/screen
   */
  async screenStocks(params?: ScreenRequest): Promise<ScreenResponse> {
    const response = await this.client.get('/api/stocks/screen', { params });
    return this.unwrap<ScreenResponse>(response.data, 'screenStocks');
  }

  /**
   * Generate rotation proposal
   * Real endpoint: GET /api/agent/rotation/proposal
   */
  async generateRotationProposal(params?: RotationProposalRequest): Promise<RotationProposal> {
    const response = await this.client.get('/api/agent/rotation/proposal', { params });
    return this.unwrap<RotationProposal>(response.data, 'generateRotationProposal');
  }

  /**
   * Simulate rotation proposal
   * Real endpoint: POST /api/agent/rotation/simulate
   */
  async simulateRotation(params: RotationSimulateRequest): Promise<RotationSimulateResponse> {
    const response = await this.client.post('/api/agent/rotation/simulate', params);
    return this.unwrap<RotationSimulateResponse>(response.data, 'simulateRotation');
  }

  /**
   * Execute rotation proposal
   * Real endpoint: POST /api/agent/rotation/execute
   */
  async executeRotation(params: RotationExecuteRequest): Promise<RotationExecuteResponse> {
    const response = await this.client.post('/api/agent/rotation/execute', params);
    return this.unwrap<RotationExecuteResponse>(response.data, 'executeRotation');
  }

  // ==================== Factor APIs (P0) ====================

  /**
   * Calculate stock factors
   * Real endpoint: GET /api/stock/{symbol}/factors
   */
  async calculateFactors(params: FactorCalculateRequest): Promise<FactorData> {
    const response = await this.client.get(`/api/stock/${params.symbol}/factors`, {
      params: { factors: params.factors },
    });
    return this.unwrap<FactorData>(response.data, 'calculateFactors');
  }

  /**
   * Analyze factor effectiveness
   * Real endpoint: POST /api/portfolio/factor-analyze
   */
  async analyzeFactor(params: FactorAnalyzeRequest): Promise<FactorAnalysisResponse> {
    const response = await this.client.post('/api/portfolio/factor-analyze', {
      factors: [params.factor_name],
      start_date: params.start_date,
      end_date: params.end_date,
    });
    return this.unwrap<FactorAnalysisResponse>(response.data, 'analyzeFactor');
  }

  // ==================== Model APIs (P0) ====================

  /**
   * Predict with ML model
   * Real endpoint: POST /api/ml/predict
   */
  async predictWithModel(params: ModelPredictRequest): Promise<ModelPrediction> {
    const response = await this.client.post('/api/ml/predict', {
      symbols: [params.symbol],
      model_type: params.model_id,
    });
    return this.unwrap<ModelPrediction>(response.data, 'predictWithModel');
  }

  // ==================== Data Manager APIs (P0) ====================

  /**
   * Get data quality report
   * Real endpoint: GET /api/data/quality-report
   */
  async getDataQualityReport(params?: DataQualityReportRequest): Promise<DataQualityReportResponse> {
    const response = await this.client.get('/api/data/quality-report', { params });
    return this.unwrap<DataQualityReportResponse>(response.data, 'getDataQualityReport');
  }

  /**
   * Data manager operations (status/refresh/cleanup/backup)
   * Real endpoint: POST /api/data/update
   */
  async dataManager(params: DataManagerRequest): Promise<DataManagerResponse> {
    const response = await this.client.post('/api/data/update', params);
    return this.unwrap<DataManagerResponse>(response.data, 'dataManager');
  }

  // ==================== Model Training APIs ====================

  /**
   * Train ML model
   * Real endpoint: POST /api/ml/train
   */
  async trainModel(params: {
    model_type: string;
    name?: string;
    symbols?: string[];
    features?: string[];
    target?: string;
  }): Promise<any> {
    const response = await this.client.post('/api/ml/train', params);
    return this.unwrap(response.data, 'trainModel');
  }

  /**
   * Evaluate ML model
   * Real endpoint: GET /api/ml/model/evaluate
   */
  async evaluateModel(params: {
    model_id: string;
    test_period?: string;
  }): Promise<any> {
    const response = await this.client.get('/api/ml/model/evaluate', { params });
    return this.unwrap(response.data, 'evaluateModel');
  }

  // ==================== Game Intelligence APIs ====================

  /**
   * Opponent behavior analysis
   * Real endpoint: GET /api/game/market/opponent-behavior
   */
  async getOpponentBehavior(params?: {
    symbol?: string;
    focus?: string;
  }): Promise<any> {
    const response = await this.client.get('/api/game/market/opponent-behavior', { params });
    return this.unwrap(response.data, 'getOpponentBehavior');
  }

  /**
   * Pool battlefield assessment
   * Real endpoint: GET /api/game/pools/{pool_id}/battlefield-assessment
   */
  async getPoolBattlefield(params: { pool_id: number }): Promise<any> {
    const response = await this.client.get(`/api/game/pools/${params.pool_id}/battlefield-assessment`);
    return this.unwrap(response.data, 'getPoolBattlefield');
  }

  /**
   * Manipulation detection
   * Real endpoint: GET /api/game/market/manipulation-detect
   */
  async detectManipulation(params: {
    symbol: string;
    days?: number;
  }): Promise<any> {
    const response = await this.client.get('/api/game/market/manipulation-detect', { params });
    return this.unwrap(response.data, 'detectManipulation');
  }
}
