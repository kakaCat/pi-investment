import { useEffect, useState } from 'react';
import { performanceApi, strategiesApi } from '../api/client';
import { PerformanceMetrics, QuantStrategy } from '../types';
import './PerformancePage.css';

export default function PerformancePage() {
  const [strategies, setStrategies] = useState<QuantStrategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const response = await strategiesApi.list();
      setStrategies(response.data);
      if (response.data.length > 0) {
        setSelectedStrategy(response.data[0].id);
      }
    } catch (err) {
      console.error('加载策略失败:', err);
    }
  };

  const loadPerformance = async () => {
    if (!selectedStrategy) return;

    setLoading(true);
    try {
      const response = await performanceApi.getStrategy(selectedStrategy, 30);
      setPerformance(response.data);
    } catch (err: any) {
      alert(err.error || '加载性能数据失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="performance-page">
      <div className="page-header">
        <h2>性能监控</h2>
        <p className="subtitle">策略历史表现分析</p>
      </div>

      <div className="controls">
        <select
          value={selectedStrategy}
          onChange={(e) => setSelectedStrategy(e.target.value)}
          className="strategy-select"
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <button onClick={loadPerformance} className="btn btn-primary" disabled={loading}>
          {loading ? '加载中...' : '查询'}
        </button>
      </div>

      {performance && (
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-label">总信号数</div>
            <div className="metric-value">{performance.total_signals}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">胜率</div>
            <div className="metric-value success">{performance.win_rate.toFixed(1)}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">平均收益</div>
            <div className="metric-value">{performance.avg_profit_pct.toFixed(2)}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">最大盈利</div>
            <div className="metric-value success">{performance.max_profit_pct.toFixed(2)}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">最大亏损</div>
            <div className="metric-value danger">{performance.max_loss_pct.toFixed(2)}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">夏普比率</div>
            <div className="metric-value">
              {performance.sharpe_ratio !== null ? performance.sharpe_ratio.toFixed(2) : 'N/A'}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">最大回撤</div>
            <div className="metric-value danger">{performance.max_drawdown_pct.toFixed(2)}%</div>
          </div>
        </div>
      )}
    </div>
  );
}
