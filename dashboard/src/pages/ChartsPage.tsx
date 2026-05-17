import { useState } from 'react';
import { chartsApi } from '../api/client';
import './ChartsPage.css';

type ChartType = 'accuracy_trend' | 'equity_curve' | 'strategy_comparison' | 'feature_importance';

export default function ChartsPage() {
  const [selectedChart, setSelectedChart] = useState<ChartType>('accuracy_trend');
  const [loading, setLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState<string>('');

  const charts = [
    { id: 'accuracy_trend', name: '准确率趋势', description: '模型训练准确率随时间变化' },
    { id: 'feature_importance', name: '特征重要性', description: '各技术指标对预测的贡献度' },
    { id: 'strategy_comparison', name: '策略对比', description: '多个策略的胜率和收益对比' },
    { id: 'equity_curve', name: '权益曲线', description: '回测资金变化曲线' },
  ];

  const loadChart = async (type: ChartType) => {
    setLoading(true);
    setSelectedChart(type);

    try {
      // 生成图表
      if (type === 'accuracy_trend') {
        await chartsApi.accuracy(90);
      } else if (type === 'feature_importance') {
        await chartsApi.importance();
      }

      // 获取图片URL
      const url = chartsApi.getImage(type);
      setImageUrl(`${url}?t=${Date.now()}`); // 添加时间戳避免缓存
    } catch (err: any) {
      alert(err.error || '加载图表失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="charts-page">
      <div className="page-header">
        <h2>图表可视化</h2>
        <p className="subtitle">量化系统性能分析图表</p>
      </div>

      <div className="charts-grid">
        {charts.map((chart) => (
          <div
            key={chart.id}
            className={`chart-card ${selectedChart === chart.id ? 'active' : ''}`}
            onClick={() => loadChart(chart.id as ChartType)}
          >
            <h3>{chart.name}</h3>
            <p>{chart.description}</p>
          </div>
        ))}
      </div>

      <div className="chart-viewer">
        {loading ? (
          <div className="loading">生成图表中...</div>
        ) : imageUrl ? (
          <img src={imageUrl} alt={selectedChart} />
        ) : (
          <div className="placeholder">点击上方卡片查看图表</div>
        )}
      </div>
    </div>
  );
}
