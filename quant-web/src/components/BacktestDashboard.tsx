import React, { useEffect, useState } from 'react';
import { Card, Table, Statistic, Row, Col, Spin, Alert, Tag } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

interface BacktestSummary {
  symbol: string;
  date: string;
  best_strategy: string;
  best_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
}

const BacktestDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<BacktestSummary[]>([]);

  useEffect(() => {
    fetchBacktestResults();
  }, []);

  const fetchBacktestResults = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/backtest/results');
      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else {
        setSummary(data.summary || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取回测结果失败');
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<BacktestSummary> = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120,
      render: (symbol: string) => <strong>{symbol}</strong>
    },
    {
      title: '回测日期',
      dataIndex: 'date',
      key: 'date',
      width: 120
    },
    {
      title: '最佳策略',
      dataIndex: 'best_strategy',
      key: 'best_strategy',
      width: 150,
      render: (strategy: string) => <Tag color="blue">{strategy}</Tag>
    },
    {
      title: '总收益率',
      dataIndex: 'best_return',
      key: 'best_return',
      width: 120,
      sorter: (a, b) => a.best_return - b.best_return,
      render: (value: number) => (
        <span style={{ color: value >= 0 ? '#3f8600' : '#cf1322' }}>
          {value >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          {' '}{(value * 100).toFixed(2)}%
        </span>
      )
    },
    {
      title: '夏普比率',
      dataIndex: 'sharpe_ratio',
      key: 'sharpe_ratio',
      width: 120,
      sorter: (a, b) => a.sharpe_ratio - b.sharpe_ratio,
      render: (value: number) => value.toFixed(2)
    },
    {
      title: '最大回撤',
      dataIndex: 'max_drawdown',
      key: 'max_drawdown',
      width: 120,
      sorter: (a, b) => a.max_drawdown - b.max_drawdown,
      render: (value: number) => (
        <span style={{ color: '#cf1322' }}>
          {(value * 100).toFixed(2)}%
        </span>
      )
    },
    {
      title: '胜率',
      dataIndex: 'win_rate',
      key: 'win_rate',
      width: 100,
      sorter: (a, b) => a.win_rate - b.win_rate,
      render: (value: number) => `${(value * 100).toFixed(1)}%`
    }
  ];

  const calculateStats = () => {
    if (summary.length === 0) return { avgReturn: 0, avgSharpe: 0, avgWinRate: 0 };

    const avgReturn = summary.reduce((sum, item) => sum + item.best_return, 0) / summary.length;
    const avgSharpe = summary.reduce((sum, item) => sum + item.sharpe_ratio, 0) / summary.length;
    const avgWinRate = summary.reduce((sum, item) => sum + item.win_rate, 0) / summary.length;

    return { avgReturn, avgSharpe, avgWinRate };
  };

  const stats = calculateStats();

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return <Alert message="错误" description={error} type="error" showIcon />;
  }

  return (
    <div style={{ padding: '24px' }}>
      <h1>回测仪表板</h1>

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="回测股票数"
              value={summary.length}
              suffix="只"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均收益率"
              value={(stats.avgReturn * 100).toFixed(2)}
              precision={2}
              valueStyle={{ color: stats.avgReturn >= 0 ? '#3f8600' : '#cf1322' }}
              prefix={stats.avgReturn >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              suffix="%"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均夏普比率"
              value={stats.avgSharpe}
              precision={2}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均胜率"
              value={(stats.avgWinRate * 100).toFixed(1)}
              suffix="%"
            />
          </Card>
        </Col>
      </Row>

      <Card title="回测结果汇总">
        <Table
          columns={columns}
          dataSource={summary}
          rowKey={(record) => `${record.symbol}_${record.date}`}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
};

export default BacktestDashboard;
