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
  CompetitionAnalysis,
  CalendarEvent,
  EventListRequest,
  EventUpsertRequest,
  EventListResponse,
  ProviderResponse,
  FundFlowDay,
  MarginDay,
  LimitUpRecord,
  StockNewsItem,
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

    // 2026-08-27: 统一错误包装拦截器——改写 error.message 为结构化中文（端点+状态码+后端原因+建议），
    // 同时保留原 axios 错误对象（response/config/code）给 axiosRetry 判断重试条件。
    // 关键设计：不 new Error，而是修改原错误.message 并 rethrow 原对象 → retry 仍能读 error.response.status
    // → 5xx 正常重试；用户最终看到的 error.message 是包装后的中文提示。
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // 防二次包装：已包装过直接透传（retry 重新 dispatch 可能再次经过本拦截器）
        if (error?.message?.startsWith('[quantsys-v2]') || error?.message?.startsWith('[quantsys-v2 不可达]')) {
          return Promise.reject(error);
        }

        const method = error.config?.method?.toUpperCase() ?? '?';
        const url = error.config?.url ?? '?';
        const endpoint = `${method} ${url}`;

        // 网络层错误（后端未启动/连接拒绝/超时）
        if (!error.response) {
          const code = error.code ?? 'NETWORK_ERROR';
          const hint = code === 'ECONNREFUSED'
            ? '后端服务未启动或端口不通——可用 quantsys_v2_status 检查后端健康，必要时 quantsys_v2_restart 拉起'
            : code === 'ECONNABORTED'
              ? '请求超时——后端可能过载或挂死（历史上由事件循环阻塞引起），可用 quantsys_v2_status 确认'
              : '网络异常——检查后端进程与端口';
          error.message = `[quantsys-v2 不可达] ${endpoint} (${code})。${hint}`;
          return Promise.reject(error);
        }

        // HTTP 错误：提取后端错误详情（FastAPI 常见格式：{success:false,error} / {detail} / {message}）
        const status = error.response.status;
        const body = error.response.data;
        const backendMsg =
          (body && typeof body === 'object'
            ? (typeof body.error === 'string' ? body.error : null) ?? body.message ??
              (typeof body.detail === 'string' ? body.detail : String(JSON.stringify(body.detail ?? body) ?? '').slice(0, 200))
            : String(body ?? '').slice(0, 200)) || '无详情';

        const hintMap: Record<number, string> = {
          400: '请求参数不合法——检查入参（字段名/格式/必填项）',
          404: '接口不存在或资源未找到——检查 URL 路径与参数',
          422: '参数校验失败（FastAPI schema）——检查字段类型',
          500: '后端内部错误——用 quantsys_v2_logs 查看后端日志定位',
          502: '上游数据源故障（网关）——稍后重试或切换数据源',
          503: '服务暂不可用——可能在重启或过载，稍后重试',
        };
        const hint = hintMap[status] ?? '查看后端日志定位原因';

        error.message = `[quantsys-v2] ${endpoint} → HTTP ${status}: ${backendMsg}。${hint}`;
        return Promise.reject(error);
      }
    );

    // Configure retry mechanism（必须注册在包装器之后：错误路径逆序执行，retry 才能先看到原始错误）
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
   * Parse condition string to conditions array for watch rules (backend schema)
   * Examples:
   *   "price>100" -> [{type: "price_break", params: {direction: "above", price: 100}}]
   *   "price<90" -> [{type: "price_break", params: {direction: "below", price: 90}}]
   *   "change_pct>5" -> [{type: "pct_change", params: {direction: "above", pct: 5}}]
   *   "change_pct<-3" -> [{type: "pct_change", params: {direction: "below", pct: -3}}]
   * 
   * Supports:
   *   - price > N / price < N  → price_break (突破/跌破价格)
   *   - change_pct > N / change_pct < N  → pct_change (涨跌幅)
   *   - Operators: >, <, >=, <=
   */
  private parseCondition(condition: string): Array<{type: string; params: Record<string, any>}> {
    const match = condition.trim().match(/^([a-z_]+)\s*(>=?|<=?)\s*(-?[0-9]+\.?[0-9]*)$/);
    if (!match) {
      throw new Error(
        `Invalid watch condition format: "${condition}". \n` +
        `Expected: "field operator value" (e.g., "price>100", "change_pct>5")\n` +
        `Supported: price>N, price<N, change_pct>N, change_pct<N`
      );
    }
    const [, field, operator, valueStr] = match;
    const value = parseFloat(valueStr);
    
    // Map to backend condition schema
    if (field === 'price') {
      const direction = (operator === '>' || operator === '>=') ? 'above' : 'below';
      return [{ type: 'price_break', params: { direction, price: value } }];
    } else if (field === 'change_pct') {
      const direction = (operator === '>' || operator === '>=') ? 'above' : 'below';
      return [{ type: 'pct_change', params: { direction, pct: value } }];
    } else {
      throw new Error(
        `Unknown watch condition field: "${field}".\n` +
        `Supported fields: price, change_pct`
      );
    }
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

    // Pattern 2b: {success, events} - events list endpoint (E1 事件日历)
    if (response.success === true && 'events' in response) {
      return response as T;
    }

    // Pattern 2c: {success, event} - single event endpoint
    if (response.success === true && 'event' in response) {
      return response.event as T;
    }

    // Pattern 2d: {success, deleted} - delete endpoint
    if (response.success === true && 'deleted' in response) {
      return response as T;
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
    // 2026-08-25 审计修复：/api/indicators/backtest 是指标回测端点（要 indicator_id，400），
    // 策略回测正确端点是 /api/backtest/run（strategy_id + 单 symbol）
    const body: Record<string, any> = {
      strategy_id: request.strategy_id,
      symbol: request.symbol || request.symbols?.[0],
      start_date: request.start_date,
      end_date: request.end_date,
      initial_capital: request.initial_capital ?? 100000,
    };
    if (request.parameters) body.parameters = request.parameters;
    const response = await this.client.post('/api/backtest/run', body);
    return this.unwrap(response.data, 'backtestStrategy');
  }

  /**
   * Optimize strategy parameters (backtest matrix)
   * Real endpoint: POST /api/strategies/optimize
   */
  async optimizeStrategy(params: {
    strategy_id: number;
    symbol: string;
    start_date: string;
    end_date: string;
    param_ranges: Record<string, number[]>;
    initial_cash?: number;
    sort_by?: 'sharpe_ratio' | 'total_return' | 'max_drawdown' | 'win_rate';
  }): Promise<{
    success: boolean;
    results: Array<{
      params: Record<string, any>;
      sharpeRatio?: number;
      totalReturn?: number;
      maxDrawdown?: number;
      winRate?: number;
      totalTrades?: number;
    }>;
    totalCombinations: number;
    successfulCombinations: number;
  }> {
    const body = {
      strategyId: params.strategy_id,
      symbol: params.symbol,
      startDate: params.start_date,
      endDate: params.end_date,
      paramRanges: params.param_ranges,
      initialCash: params.initial_cash,
      sortBy: params.sort_by,
    };
    const response = await this.client.post('/api/strategies/optimize', body);
    return response.data;
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
    // 后端 akshare 上游较慢（线程兜底 45s + 缓存），客户端超时放宽到 60s
    const response = await this.client.get('/api/market/macro', { timeout: 60000 });
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

  /**
   * Get platform status (for quantsys_v2_status tool)
   */
  async getPlatformStatus(): Promise<{
    status: string;
    holdings_count: number;
    balance: any;
    recent_signals: number;
    db_connected: boolean;
    model_loaded: boolean;
    recent_report: boolean;
    timestamp: string;
  }> {
    const response = await this.client.get('/api/health/platform/status');
    return response.data.data;
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

  /**
   * Get competition analysis
   */
  async getCompetitionAnalysis(
    symbol: string,
    includeFinancial: boolean = true
  ): Promise<CompetitionAnalysis> {
    const response = await this.client.get(`/api/analysis/competition/${symbol}`, {
      params: { include_financial: includeFinancial },
    });
    return this.unwrap<CompetitionAnalysis>(response.data, 'getCompetitionAnalysis');
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

  /**
   * Get financial statements (provider sina-statements, 真实报表数据)
   * Real endpoint: GET /api/provider/financial/{symbol}/sina-statements
   * 2026-08-30 新增：/api/v2/stock/{symbol}/financials 的 sina-web 指标源已失效
   * （全部返回 null），改用 DataProviderManager 的原始报表接口兜底。
   * 返回 { data_type, data: { income, balance, cashflow } }
   */
  async getFinancialStatements(symbol: string): Promise<any> {
    const response = await this.client.get('/api/provider/financial/' + symbol + '/sina-statements');
    return this.unwrap<any>(response.data, 'getFinancialStatements');
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
   * 2026-08-31 修复：改调 /api/simulation/accounts/{account}（get_account_status），
   * 该接口每次请求实时拉行情刷新持仓价格并返回 price_stale / price_updated_at；
   * 原 /api/portfolio/positions 直读数据库 current_price 快照（陈旧价，曾导致 8/28 旧价）。
   * 响应为 snake_case，映射为工具层期望的 camelCase Position[]。
   */
  async getPositions(accountName: string = 'agent_virtual'): Promise<Position[]> {
    const response = await this.client.get(`/api/simulation/accounts/${encodeURIComponent(accountName)}`);
    const data = this.unwrap<SimulationAccountStatus>(response.data, 'getPositions');
    const positions = Array.isArray(data.positions) ? data.positions : [];
    return positions.map((p) => this.mapPosition(p, data));
  }

  /**
   * Get portfolio summary
   * 2026-08-31 修复：同样改调 /api/simulation/accounts/{account}（实时刷新），
   * 原 /api/portfolio/summary 直读数据库快照（account.lastUpdated 曾停更在 8/28）。
   */
  async getPortfolioSummary(accountName: string = 'agent_virtual'): Promise<PortfolioSummary> {
    const response = await this.client.get(`/api/simulation/accounts/${encodeURIComponent(accountName)}`);
    const data = this.unwrap<SimulationAccountStatus>(response.data, 'getPortfolioSummary');
    const positions = Array.isArray(data.positions) ? data.positions : [];
    // 新接口持仓项无 cost 字段，总成本 = Σ(avg_cost × shares_total)
    const totalCost = positions.reduce((sum, p) => sum + ((Number(p.avg_cost) || 0) * (Number(p.shares_total) || 0)), 0);
    const marketValue = Number(data.position_value) || 0;
    const totalPnl = marketValue - totalCost;
    const cash = (Number(data.cash_available) || 0) + (Number(data.cash_frozen) || 0);
    return {
      accountName: String(data.account_name || accountName),
      totalValue: Number(data.total_value) || 0,
      totalCost,
      totalMarketValue: marketValue,
      totalPnl,
      totalPnlPct: totalCost > 0 ? Number(((totalPnl / totalCost) * 100).toFixed(2)) : 0,
      dailyChange: 0,
      positions: positions.length,
      cash,
      liquidAssets: cash,
      profitCount: positions.filter((p) => Number(p.profit_total) > 0).length,
      lossCount: positions.filter((p) => Number(p.profit_total) < 0).length,
      lastUpdated: data.last_updated || new Date().toISOString(),
      priceStale: Boolean(data.price_stale),
    } as PortfolioSummary;
  }

  /**
   * 将 simulation 账户接口的 snake_case 持仓项映射为 Position（camelCase）
   */
  private mapPosition(p: SimulationPositionItem, account: SimulationAccountStatus): Position {
    const quantity = Number(p.shares_total) || 0;
    const avgCost = Number(p.avg_cost) || 0;
    const currentPrice = Number(p.current_price) || avgCost;
    const marketValue = Number(p.market_value) || quantity * currentPrice;
    const totalCost = quantity * avgCost;
    const profitTotal = Number(p.profit_total) ?? marketValue - totalCost;
    const profitTotalRate = Number(p.profit_total_rate) ?? (totalCost > 0 ? profitTotal / totalCost : 0);
    return {
      symbol: String(p.symbol || ''),
      name: String(p.name || ''),
      quantity,
      sharesAvailable: Number(p.shares_available) ?? quantity,
      avgCost,
      currentPrice,
      totalCost,
      currentValue: marketValue,
      profitLoss: profitTotal,
      profitLossPct: Number((profitTotalRate * 100).toFixed(2)),
      profitToday: Number(p.profit_today) || 0,
      // 行情时效信息：价格刷新时间戳 + 账户级陈旧标记（true=本次行情拉取失败，价格为旧值）
      priceUpdatedAt: p.price_updated_at || account.last_updated || null,
      priceStale: Boolean(account.price_stale),
    } as Position;
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
  /**
   * Execute a trade（虚拟账户立即成交）
   * 2026-08-25 修复：改走 simulation 交易端点（/api/orders/create 属于订单管理系统，
   * 只建单不成交、不动虚拟账户持仓——卖出校验也查的是废弃 holdings 表）。
   * 正确端点：POST /api/simulation/accounts/{account}/trade（立即成交并更新持仓）。
   */
  async executeTrade(params: TradeRequest): Promise<TradeResponse> {
    const account = params.account_name || 'agent_virtual';
    const body: Record<string, any> = {
      action: params.action,
      symbol: params.symbol,
      shares: params.quantity,
      // 后端要求交易理由 ≥10 字（R-005 同款纪律）
      reason: params.reason && params.reason.length >= 10
        ? params.reason
        : (params.reason ? `${params.reason}（虚拟盘委托）` : '虚拟账户委托交易（未注明理由）'),
    };
    if (params.price) body.price = params.price;
    if (params.genome_version) body.genome_version = params.genome_version;  // RFC 005 决策打标
    const response = await this.client.post(`/api/simulation/accounts/${encodeURIComponent(account)}/trade`, body);
    const data = this.unwrap<any>(response.data, 'executeTrade');
    // 映射为 TradeResponse 契约
    return {
      order_id: String(data.order_id ?? data.trade_id ?? ''),
      action: data.action ?? params.action,
      symbol: data.symbol ?? params.symbol,
      quantity: Number(data.shares ?? params.quantity),
      price: Number(data.price ?? 0),
      amount: Number(data.amount ?? 0),
      status: data.order_status ?? 'filled',
      timestamp: data.timestamp ?? new Date().toISOString(),
    } as TradeResponse;
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
    page?: number;
    pageSize?: number;
  }): Promise<TradeHistoryResponse> {
    // 2026-08-31: 修复路由，后端实际是 /api/simulation/trades
    const response = await this.client.get('/api/simulation/trades', { params });
    return this.unwrap<TradeHistoryResponse>(response.data, 'getTradeHistory');
  }

  /**
   * Execute algorithmic order (TWAP/VWAP)
   * Real endpoint: POST /api/orders/algo-execute
   */
  async executeAlgo(params: AlgoExecuteRequest): Promise<AlgoExecuteResponse> {
    // 2026-08-30 修复：后端契约用 duration_minutes（此前传 duration 会被忽略，回落默认 30）
    const { duration, ...rest } = params;
    const body: Record<string, any> = { ...rest };
    if (duration !== undefined) body.duration_minutes = duration;
    const response = await this.client.post('/api/orders/algo-execute', body);
    const raw: any = this.unwrap(response.data, 'executeAlgo');
    // 2026-08-30 修复：运行中的后端统一 camelCase（orderId/parentQuantity/childOrders/
    // executionStats），与 AlgoExecuteResponse 契约（algo_order_id/total_quantity/slices）
    // 不一致，此前导致 AlgoExecuteTool.wrap 永远报"缺少必需字段"。此处兼容两种命名。
    return {
      algo_order_id: raw.orderId ?? raw.order_id ?? raw.algo_order_id,
      algo: raw.algo,
      symbol: raw.symbol,
      total_quantity: raw.parentQuantity ?? raw.parent_quantity ?? raw.total_quantity,
      filled_quantity: raw.filled_quantity ?? 0,
      avg_price: raw.avg_price ?? 0,
      slices: raw.childOrders ?? raw.child_orders ?? raw.slices ?? [],
      status: raw.status,
      side: raw.side,
      execution_stats: raw.executionStats ?? raw.execution_stats,
      parent_quantity: raw.parentQuantity ?? raw.parent_quantity,
      order_id: raw.orderId ?? raw.order_id,
    } as AlgoExecuteResponse;
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
    const { action, rule_id, condition, ...rest } = params;
    if (action === 'list') {
      // List all rules (calls listWatchRules internally)
      return await this.listWatchRules();
    }
    if (action === 'create') {
      // Transform condition string to conditions array (backend contract)
      // e.g. "price>100" -> [{type: "price_threshold", params: {operator: ">", value: 100}}]
      const conditions = condition ? this.parseCondition(condition) : [];
      const body = { ...rest, conditions };
      const response = await this.client.post('/api/watch/rules', body);
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
    // /api/alerts/check 触发 opponent+manipulation 检测，冷路径实测 30-40s，超时放宽到 60s
    const response = await this.client.get('/api/alerts/check', { params, timeout: 60000 });
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

  /**
   * Get sector constituent stocks（板块成分股，M2-1 主线→标的映射数据源）
   * Real endpoint: GET /api/market/sector/{sector:path}（sector 传中文板块名，如"白银"）
   * Response data: {sector, sectorCode, stocks: [{symbol, name, pe, marketCapBillion}], count}
   */
  async getSectorStocks(sector: string): Promise<{
    sector: string;
    sectorCode?: string;
    stocks: Array<{ symbol: string; name: string; pe?: number; marketCapBillion?: number }>;
    count: number;
  }> {
    const response = await this.client.get(`/api/market/sector/${encodeURIComponent(sector)}`);
    return this.unwrap(response.data, 'getSectorStocks');
  }

  // ==================== Risk APIs (P0) ====================

  /**
   * Risk control: position_size / stop_loss / portfolio_risk
   * Dispatches to different endpoints based on command.
   */
  async riskControl(params: RiskControlRequest): Promise<any> {
    const { command, symbol, account_name, risk_level, price, entry_price } = params;
    if (command === 'position_size') {
      const response = await this.client.post(`/api/stock/${symbol}/risk/position-size`, { account_name, price });
      return this.unwrap(response.data, 'riskControl');
    }
    if (command === 'stop_loss') {
      const response = await this.client.post(`/api/stock/${symbol}/risk/stop-loss`, {
        account_name,
        risk_level: risk_level || 'large_cap',
        entry_price,
      });
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
    symbols?: string[];
    start_date?: string;
    end_date?: string;
    weights?: number[];
    account_name?: string;
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
    const data = response.data;
    if (data?.success === false) {
      throw new Error(data?.error || 'API request failed: scanOpportunities');
    }
    // 后端返回 {success, scan_mode, opportunities: [...]}，无 data 信封，需显式提取
    const list = data?.opportunities ?? data?.data ?? [];
    return (Array.isArray(list) ? list : []) as Opportunity[];
  }

  /**
   * Screen stocks by filters
   * Real endpoint: GET /api/stocks/screen
   */
  async screenStocks(params?: ScreenRequest): Promise<ScreenResponse> {
    // 2026-09-01 修复：工具层 criteria 是区间对象 {pe:[min,max], roe:[...]}，
    // 后端 /api/stocks/screen 只认扁平参数（max_pe/min_roe/...）。
    // 此前直接透传嵌套对象 → Axios 序列化为 criteria[pe][0]=...，后端读不到
    // → criteria 全空 → 全市场通过（含退市股），筛选形同虚设。
    const { criteria, filters, sort_by, limit, ...rest } = params ?? {};
    const flat: Record<string, any> = { ...rest };
    const crit = { ...(criteria ?? {}), ...(filters ?? {}) };
    const rng = (key: string): [number, number] => {
      const v = crit[key];
      if (Array.isArray(v) && v.length >= 2) return [v[0], v[1]];
      if (typeof v === 'number') return [v, v];
      return [undefined, undefined];
    };
    const [peMin, peMax] = rng('pe');
    const [roeMin] = rng('roe');
    const [capMin, capMax] = rng('market_cap');
    const [, debtMax] = rng('debt_ratio');
    const [scoreMin] = rng('score');
    const [pbMax] = rng('pb');
    if (peMax != null) flat.max_pe = peMax;
    if (roeMin != null) flat.min_roe = roeMin;
    if (capMin != null) flat.min_market_cap = capMin;
    if (capMax != null) flat.max_market_cap = capMax;
    if (debtMax != null) flat.max_debt_ratio = debtMax;
    if (scoreMin != null) flat.min_score = scoreMin;
    if (pbMax != null) flat.max_pb = pbMax;
    if (sort_by) flat.sort_by = sort_by;
    if (limit) flat.limit = limit;
    if (crit.exclude_st !== undefined) flat.exclude_st = crit.exclude_st;
    const response = await this.client.get('/api/stocks/screen', { params: flat });
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
    // 2026-08-30 修复：后端 RotationSimulate 模型字段为 actions（策略级轮动动作），
    // 工具层传 proposals（买卖建议），需映射后再 POST，否则 FastAPI 422 校验失败。
    const { proposals, ...rest } = params;
    const response = await this.client.post('/api/agent/rotation/simulate', { actions: proposals ?? [], ...rest });
    return this.unwrap<RotationSimulateResponse>(response.data, 'simulateRotation');
  }

  /**
   * Execute rotation proposal
   * Real endpoint: POST /api/agent/rotation/execute
   */
  async executeRotation(params: RotationExecuteRequest): Promise<RotationExecuteResponse> {
    // 2026-09-01 修复：后端 RotationExecution 模型字段为 actions/decision/reason，
    // 工具层传 proposals（买卖建议），需映射后再 POST，否则 FastAPI 422 校验失败。
    const { proposals, ...rest } = params;
    const response = await this.client.post('/api/agent/rotation/execute', {
      actions: proposals ?? [],
      decision: 'approve',
      reason: 'agent rotation_execute',
      ...rest,
    });
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
   * 解析 agent 侧 model_id（如 "lightgbm_20260820_195134"）为后端所需的
   * model_type + version。裸类型名（如 "lightgbm"、"lgbm"）视为 latest。
   * 无法识别时抛错——禁止静默回退默认模型（RFC003-P3 验收发现）。
   */
  private parseModelId(modelId: string): { model_type: string; version?: string } {
    const alias: Record<string, string> = {
      lgbm: 'lightgbm',
      lightgbm: 'lightgbm',
      xgboost: 'xgboost',
      randomforest: 'randomforest',
      random_forest: 'randomforest',
      neural_net: 'neural_net',
    };
    const id = modelId.trim();
    // 注意：按前缀长度降序匹配，避免 "random_forest" 被 "random" 之类短前缀误吞
    for (const [prefix, canonical] of Object.entries(alias).sort((a, b) => b[0].length - a[0].length)) {
      if (id === prefix) return { model_type: canonical };
      if (id.startsWith(prefix + '_')) {
        const version = id.slice(prefix.length + 1);
        if (version) return { model_type: canonical, version };
      }
    }
    throw new Error(
      `无法解析 model_id "${modelId}"，正确格式如 lightgbm_20260820_195134（{model_type}_{version}）或裸类型名 lightgbm/xgboost`
    );
  }

  /**
   * 列出已注册模型
   * Real endpoint: GET /api/ml/models
   */
  async listModels(params?: { model_type?: string; status?: string; limit?: number }): Promise<any> {
    const response = await this.client.get('/api/ml/models', { params });
    return this.unwrap(response.data, 'listModels');
  }

  /**
   * 选择默认模型：最新一个通过上线门禁（roc_auc >= 0.55, status=ready）的模型。
   * 无达标模型时返回 null，由后端默认路径兜底（RFC003-P3 门禁规则）。
   */
  private async resolveGatedDefaultModel(): Promise<{ model_type: string; version: string } | null> {
    try {
      const res = await this.listModels({ status: 'ready', limit: 50 });
      const models: any[] = res?.models || [];
      const gated = models
        .filter((m) => typeof m.roc_auc === 'number' && m.roc_auc >= 0.55 && m.train_date)
        .sort((a, b) => String(b.train_date).localeCompare(String(a.train_date)));
      if (!gated.length) return null;
      return { model_type: gated[0].model_type, version: gated[0].version };
    } catch {
      return null; // 列表不可用时回退后端默认（不阻断预测）
    }
  }

  /**
   * Predict with ML model
   * Real endpoint: POST /api/ml/predict
   */
  async predictWithModel(params: ModelPredictRequest): Promise<ModelPrediction> {
    let modelType: string | undefined;
    let version: string | undefined;
    if (params.model_id) {
      const parsed = this.parseModelId(params.model_id);
      modelType = parsed.model_type;
      version = parsed.version;
    } else {
      // 默认路径走门禁模型，避免落到 AUC<0.55 的退役模型（S1 恒等输出源）
      const gated = await this.resolveGatedDefaultModel();
      if (gated) {
        modelType = gated.model_type;
        version = gated.version;
      }
    }
    const response = await this.client.post('/api/ml/predict', {
      symbols: [params.symbol],
      ...(modelType ? { model_type: modelType } : {}),
      ...(version ? { version } : {}),
    });
    const result = this.unwrap<ModelPrediction>(response.data, 'predictWithModel');
    if (modelType) {
      (result as any).model_used = `${modelType}${version ? '_' + version : '@latest'}`;
    }
    return result;
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

  /**
   * Sync daily K-line data
   * Real endpoint: POST /api/data/sync-daily-klines
   */
  async syncDailyKlines(params?: { date?: string; symbols?: string[]; force?: boolean }): Promise<{
    success: boolean;
    sync_date: string;
    success_count: number;
    failed_count: number;
    total_stocks: number;
    total_rows: number;
    elapsed_time: number;
    message: string;
    failed_symbols?: string[];
  }> {
    const response = await this.client.post('/api/data/sync-daily-klines', params || {});
    return response.data;
  }

  /**
   * Get data sync status
   * Real endpoint: GET /api/data/sync-status
   */
  async getDataSyncStatus(): Promise<{
    status: string;
    latest_date: string | null;
    latest_count?: number;
    active_stocks_count?: number;
    coverage?: string;
    message: string;
  }> {
    const response = await this.client.get('/api/data/sync-status');
    return response.data;
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
   * Real endpoint: GET /api/ml/model/evaluate（后端参数为 model_type + version）
   * 注意：后端不支持按 test_period 重估，返回的是训练时落库的指标；
   * 未知 model_id 会明确报错（success=false），不再静默回退默认模型。
   */
  async evaluateModel(params: {
    model_id: string;
    test_period?: string;
  }): Promise<any> {
    const parsed = this.parseModelId(params.model_id);
    const response = await this.client.get('/api/ml/model/evaluate', {
      params: { model_type: parsed.model_type, version: parsed.version || 'latest' },
    });
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

  /**
   * Retail panic index (M7-2)
   * Real endpoint: GET /api/market/perception/panic-index
   */
  async getRetailPanicIndex(params?: {
    trade_date?: string;
    days?: number;
  }): Promise<any> {
    const url = params?.days != null
      ? '/api/market/perception/panic-index/series'
      : '/api/market/perception/panic-index';
    const response = await this.client.get(url, { params: params?.days != null ? { days: params.days } : params });
    return this.unwrap(response.data, 'getRetailPanicIndex');
  }

  // ==================== Signal Tracking APIs (M3-1) ====================

  /**
   * Record a buy signal
   * Real endpoint: POST /api/signals/track
   * Body: {signal_date, symbol, grade, source, price, reason?}
   */
  async recordSignal(params: {
    signal_date: string;
    symbol: string;
    grade: 'A' | 'B' | 'C';
    source: string;
    price: number;
    reason?: string;
  }): Promise<{ signalId: number; message: string }> {
    const response = await this.client.post('/api/signals/track', params);
    return this.unwrap<{ signalId: number; message: string }>(response.data, 'recordSignal');
  }

  /**
   * Update signal performance (backfill 5/10/20-day returns)
   * Real endpoint: PUT /api/signals/track/update
   * Body: {signal_date?, lookback_days?}
   */
  async updateSignalPerformance(params?: {
    signal_date?: string;
    lookback_days?: number;
  }): Promise<{ updated: number; details: Record<string, number> }> {
    const response = await this.client.put('/api/signals/track/update', params ?? {});
    return this.unwrap<{ updated: number; details: Record<string, number> }>(response.data, 'updateSignalPerformance');
  }

  /**
   * Get signal statistics report
   * Real endpoint: GET /api/signals/track/report?start_date=&end_date=&grade=&source=
   */
  async getSignalReport(params?: {
    start_date?: string;
    end_date?: string;
    grade?: 'A' | 'B' | 'C';
    source?: string;
  }): Promise<{
    total: number;
    dateRange: { start: string; end: string };
    byGrade: Record<string, any>;
    bySource: Record<string, any>;
    recentSignals: any[];
  }> {
    const response = await this.client.get('/api/signals/track/report', { params });
    return this.unwrap(response.data, 'getSignalReport');
  }

  /**
   * 生成周报并推送到飞书（M6-2）
   */
  async pushWeeklyReport(params?: {
    week_start?: string;
    week_end?: string;
    feishu_webhook?: string;
  }): Promise<{
    success: boolean;
    report: any;
    markdown: string;
    push_result: {
      success: boolean;
      message?: string;
      error?: string;
    } | null;
  }> {
    const response = await this.client.post('/api/reports/weekly/push', null, { params });
    return this.unwrap(response.data, 'pushWeeklyReport');
  }

  /**
   * 获取最新周报（M6-2）
   */
  async getLatestWeeklyReport(format: 'json' | 'markdown' = 'json'): Promise<any> {
    const response = await this.client.get('/api/reports/weekly/latest', {
      params: { format }
    });
    return this.unwrap(response.data, 'getLatestWeeklyReport');
  }

  // ==================== E1 事件日历 ====================

  /**
   * 查未来 N 天待处理事件（每日检查任务核心调用）
   */
  async getUpcomingEvents(days: number = 2): Promise<EventListResponse> {
    const response = await this.client.get('/api/events/upcoming', {
      params: { days }
    });
    return this.unwrap(response.data, 'getUpcomingEvents');
  }

  /**
   * 范围查询事件日历（按日期区间/类型/状态/标的过滤）
   */
  async listEvents(params?: EventListRequest): Promise<EventListResponse> {
    const response = await this.client.get('/api/events', { params });
    return this.unwrap(response.data, 'listEvents');
  }

  /**
   * 按 ID 查单个事件
   */
  async getEvent(id: number): Promise<CalendarEvent> {
    const response = await this.client.get(`/api/events/${id}`);
    return this.unwrap(response.data, 'getEvent');
  }

  /**
   * 创建/更新事件（幂等 upsert：按类型+日期+标题去重）
   */
  async upsertEvent(event: EventUpsertRequest): Promise<CalendarEvent> {
    const response = await this.client.post('/api/events', event);
    return this.unwrap(response.data, 'upsertEvent');
  }

  /**
   * 更新事件（状态/结果/影响评估）
   */
  async updateEvent(id: number, updates: Partial<EventUpsertRequest>): Promise<CalendarEvent> {
    const response = await this.client.patch(`/api/events/${id}`, updates);
    return this.unwrap(response.data, 'updateEvent');
  }

  /**
   * 标记事件状态（状态机：pending→notified→collected→reviewed/skipped）
   */
  async markEventStatus(id: number, status: string, metaPatch?: Record<string, any>): Promise<CalendarEvent> {
    const payload: any = { status };
    if (metaPatch) payload.meta = metaPatch;
    const response = await this.client.patch(`/api/events/${id}`, payload);
    return this.unwrap(response.data, 'markEventStatus');
  }

  /**
   * 删除事件
   */
  async deleteEvent(id: number): Promise<{ success: boolean; deleted: number }> {
    const response = await this.client.delete(`/api/events/${id}`);
    return this.unwrap(response.data, 'deleteEvent');
  }

  // ==================== P0 情报数据层（多数据源，降级友好） ====================
  // 注意：以下方法**不走 unwrap**——数据源失败（success:false）是常态，
  // 需把原始响应（含 error/attempted_sources）透传给工具层做降级处理。

  /** 个股资金流（主力/大单/中单/小单净流入） */
  async getStockFundFlow(symbol: string, days: number = 5): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/stock/${symbol}/fund-flow`, {
      params: { days }
    }).catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 板块资金流 */
  async getSectorFlow(): Promise<ProviderResponse> {
    const response = await this.client.get('/api/market/sector-flow')
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 个股融资融券（杠杆资金） */
  async getStockMargin(symbol: string, days: number = 5): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/stock/${symbol}/margin`, {
      params: { days }
    }).catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 龙虎榜：某日上榜记录 */
  async getLhbDaily(date: string): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/provider/lhb/daily/${date}`)
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 龙虎榜：个股上榜明细 */
  async getLhbDetail(symbol: string): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/provider/lhb/detail/${symbol}`)
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 涨停池（某日涨停股+连板/封单） */
  async getLimitUpPool(date: string): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/provider/zt-pool/${date}`)
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 个股公告 */
  async getStockAnnouncements(symbol: string): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/provider/stock/${symbol}/announcements`)
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 个股新闻 */
  async getStockNews(symbol: string): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/provider/stock/${symbol}/news`)
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 内部人交易（高管增减持） */
  async getInsiderTrades(symbol: string): Promise<ProviderResponse> {
    const response = await this.client.get(`/api/provider/stock/${symbol}/insider-trades`)
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }

  /** 交易日历 */
  async getTradingCalendar(): Promise<ProviderResponse> {
    const response = await this.client.get('/api/provider/trading-calendar')
      .catch((e: any) => ({ data: { success: false, error: e.message } }));
    return response.data;
  }
}
