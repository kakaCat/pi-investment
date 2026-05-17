import { useState, useEffect } from 'react';
import { backtestApi, strategiesApi } from '../api/client';
import { QuantStrategy, BacktestResult } from '../types';
import './BacktestPage.css';

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<QuantStrategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [initialCapital, setInitialCapital] = useState(100000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

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

  const runBacktest = async () => {
    if (!selectedStrategy) return;

    setLoading(true);
    try {
      const response = await backtestApi.run({
        strategy_id: selectedStrategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
      });
      setResult(response.data);
    } catch (err: any) {
      alert(err.error || '回测失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="backtest-page">
      <div className="page-header">
        <h2>回测分析</h2>
        <p className="subtitle">模拟历史交易验证策略效果</p>
      </div>

      <div className="backtest-form">
        <div className="form-group">
          <label>选择策略</label>
          <select value={selectedStrategy} onChange={(e) => setSelectedStrategy(e.target.value)}>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>开始日期</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label>结束日期</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label>初始资金</label>
          <input
            type="number"
            value={initialCapital}
            onChange={(e) => setInitialCapital(Number(e.target.value))}
            step={10000}
          />
        </div>

        <button onClick={runBacktest} className="btn btn-primary btn-large" disabled={loading}>
          {loading ? '回测中...' : '开始回测'}
        </button>
      </div>

      {result && (
        <div className="backtest-results">
          <h3>回测结果</h3>
          <div className="results-grid">
            <div className="result-card">
              <div className="result-label">总收益率</div>
              <div className={`result-value ${result.total_return >= 0 ? 'success' : 'danger'}`}>
                {(result.total_return * 100).toFixed(2)}%
              </div>
            </div>
            <div className="result-card">
              <div className="result-label">年化收益率</div>
              <div className="result-value">{(result.annual_return * 100).toFixed(2)}%</div>
            </div>
            <div className="result-card">
              <div className="result-label">最大回撤</div>
              <div className="result-value danger">{(result.max_drawdown * 100).toFixed(2)}%</div>
            </div>
            <div className="result-card">
              <div className="result-label">夏普比率</div>
              <div className="result-value">{result.sharpe_ratio.toFixed(2)}</div>
            </div>
            <div className="result-card">
              <div className="result-label">胜率</div>
              <div className="result-value">{(result.win_rate * 100).toFixed(1)}%</div>
            </div>
            <div className="result-card">
              <div className="result-label">盈亏比</div>
              <div className="result-value">{result.profit_loss_ratio.toFixed(2)}</div>
            </div>
            <div className="result-card">
              <div className="result-label">总交易次数</div>
              <div className="result-value">{result.total_trades}</div>
            </div>
            <div className="result-card">
              <div className="result-label">盈利/亏损</div>
              <div className="result-value">
                {result.winning_trades} / {result.losing_trades}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
