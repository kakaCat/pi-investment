import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error.response?.data || error);
  }
);

// 策略API
export const strategiesApi = {
  list: () => apiClient.get('/api/strategies'),
  get: (id: string) => apiClient.get(`/api/strategies/${id}`),
  create: (data: any) => apiClient.post('/api/strategies', data),
  update: (id: string, data: any) => apiClient.put(`/api/strategies/${id}`, data),
  delete: (id: string) => apiClient.delete(`/api/strategies/${id}`),
  enable: (id: string) => apiClient.post(`/api/strategies/${id}/enable`),
  disable: (id: string) => apiClient.post(`/api/strategies/${id}/disable`),
};

// 信号API
export const signalsApi = {
  generate: (data: { strategy_id: string; symbol: string; name: string; days?: number }) =>
    apiClient.post('/api/signals/generate', data),
  scan: (data: { strategy_id: string; stocks: Array<{ symbol: string; name: string }>; confidence_threshold?: number }) =>
    apiClient.post('/api/signals/scan', data),
  history: (days?: number) => apiClient.get('/api/signals/history', { params: { days } }),
};

// 回测API
export const backtestApi = {
  run: (data: { strategy_id: string; start_date: string; end_date: string; initial_capital?: number }) =>
    apiClient.post('/api/backtest', data),
};

// 性能API
export const performanceApi = {
  getStrategy: (strategyId: string, days?: number) =>
    apiClient.get(`/api/performance/strategy/${strategyId}`, { params: { days } }),
  compare: (strategyIds: string[], days?: number) =>
    apiClient.get('/api/performance/compare', { params: { strategy_ids: strategyIds.join(','), days } }),
};

// 图表API
export const chartsApi = {
  accuracy: (days?: number) => apiClient.get('/api/charts/accuracy', { params: { days } }),
  equity: (backtestResult: any) => apiClient.get('/api/charts/equity', { data: { backtest_result: backtestResult } }),
  comparison: (strategiesPerformance: any[]) =>
    apiClient.get('/api/charts/comparison', { data: { strategies_performance: strategiesPerformance } }),
  importance: () => apiClient.get('/api/charts/importance'),
  getImage: (type: 'accuracy_trend' | 'equity_curve' | 'strategy_comparison' | 'feature_importance') =>
    `${API_BASE_URL}/api/charts/image/${type}`,
};

export default apiClient;
