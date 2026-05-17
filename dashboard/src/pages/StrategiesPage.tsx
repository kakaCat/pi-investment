import { useEffect, useState } from 'react';
import { strategiesApi } from '../api/client';
import { QuantStrategy } from '../types';
import './StrategiesPage.css';

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<QuantStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      setLoading(true);
      const response = await strategiesApi.list();
      setStrategies(response.data);
      setError(null);
    } catch (err: any) {
      setError(err.error || '加载策略失败');
    } finally {
      setLoading(false);
    }
  };

  const toggleStrategy = async (id: string, enabled: boolean) => {
    try {
      if (enabled) {
        await strategiesApi.disable(id);
      } else {
        await strategiesApi.enable(id);
      }
      loadStrategies();
    } catch (err: any) {
      alert(err.error || '操作失败');
    }
  };

  if (loading) return <div className="loading">加载中...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="strategies-page">
      <div className="page-header">
        <h2>策略管理</h2>
        <p className="subtitle">共 {strategies.length} 个策略</p>
      </div>

      <div className="strategies-grid">
        {strategies.map((strategy) => (
          <div key={strategy.id} className="strategy-card">
            <div className="card-header">
              <h3>{strategy.name}</h3>
              <span className={`status ${strategy.enabled ? 'enabled' : 'disabled'}`}>
                {strategy.enabled ? '已启用' : '已禁用'}
              </span>
            </div>
            <p className="description">{strategy.description}</p>

            <div className="strategy-details">
              <div className="detail-item">
                <span className="label">入场条件:</span>
                <span className="value">{strategy.entry.conditions.length} 个</span>
              </div>
              <div className="detail-item">
                <span className="label">出场条件:</span>
                <span className="value">{strategy.exit.conditions.length} 个</span>
              </div>
              <div className="detail-item">
                <span className="label">最大仓位:</span>
                <span className="value">{strategy.position.max_position_pct}%</span>
              </div>
              <div className="detail-item">
                <span className="label">最大持股:</span>
                <span className="value">{strategy.position.max_stocks} 只</span>
              </div>
            </div>

            <div className="card-actions">
              <button
                className={`btn ${strategy.enabled ? 'btn-danger' : 'btn-success'}`}
                onClick={() => toggleStrategy(strategy.id, strategy.enabled)}
              >
                {strategy.enabled ? '禁用' : '启用'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
