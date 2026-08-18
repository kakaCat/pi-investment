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
          `[QuantsysV2Client] Retrying request (${retryCount}/3): ${requestConfig.method?.toUpperCase()} ${requestConfig.url}`
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
      throw new Error(response.error || 'API request failed');
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
    const response = await this.client.post('/api/pools/create', pool);
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
    const response = await this.client.get('/api/signals/list', {
      params,
    });
    return this.unwrap(response.data, 'listSignals');
  }

  /**
   * Generate signals
   */
  async generateSignals(params: {
    strategy_id: number;
    symbols?: string[];
    date?: string;
  }): Promise<Signal[]> {
    const response = await this.client.post('/api/signals/generate', params);
    return this.unwrap(response.data, 'generateSignals');
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
   */
  async getMarketStyle(): Promise<{
    style: string;
    confidence: number;
    description: string;
    updated_at: string;
  }> {
    const response = await this.client.get('/api/analysis/market-style');
    return this.unwrap(response.data, 'getMarketStyle');
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
}
