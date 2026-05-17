import { useEffect, useState } from 'react';
import { signalsApi } from '../api/client';
import { Signal } from '../types';
import './SignalsPage.css';

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(7);

  useEffect(() => {
    loadSignals();
  }, []);

  const loadSignals = async () => {
    setLoading(true);
    try {
      const response = await signalsApi.history(days);
      setSignals(response.data);
    } catch (err: any) {
      alert(err.error || '加载信号失败');
    } finally {
      setLoading(false);
    }
  };

  const getSignalColor = (signal: string) => {
    if (signal === 'buy') return 'success';
    if (signal === 'sell') return 'danger';
    return 'neutral';
  };

  return (
    <div className="signals-page">
      <div className="page-header">
        <h2>历史信号</h2>
        <p className="subtitle">查看最近生成的交易信号</p>
      </div>

      <div className="controls">
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="days-select">
          <option value={7}>最近7天</option>
          <option value={30}>最近30天</option>
          <option value={90}>最近90天</option>
        </select>
        <button onClick={loadSignals} className="btn btn-primary" disabled={loading}>
          {loading ? '加载中...' : '查询'}
        </button>
      </div>

      <div className="signals-table">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>股票</th>
              <th>信号</th>
              <th>置信度</th>
              <th>价格</th>
              <th>策略</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((signal, idx) => (
              <tr key={idx}>
                <td>{new Date(signal.timestamp).toLocaleString('zh-CN')}</td>
                <td>
                  {signal.symbol} {signal.name}
                </td>
                <td>
                  <span className={`signal-badge ${getSignalColor(signal.signal)}`}>
                    {signal.signal === 'buy' ? '买入' : signal.signal === 'sell' ? '卖出' : '持有'}
                  </span>
                </td>
                <td>{(signal.confidence * 100).toFixed(0)}%</td>
                <td>¥{signal.price.toFixed(2)}</td>
                <td>{signal.strategy_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {signals.length === 0 && !loading && <div className="empty">暂无信号数据</div>}
      </div>
    </div>
  );
}
