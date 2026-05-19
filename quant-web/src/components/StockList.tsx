import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Statistic, Row, Col, Spin, Alert, Input } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, SearchOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

interface StockData {
  symbol: string;
  name: string;
  market: string;
  kline_days: number;
  earliest_date: string;
  latest_date: string;
  factor_days: number;
  factor_count: number;
  data_complete: boolean;
}

interface StockDataStatus {
  total_stocks: number;
  complete_stocks: number;
  incomplete_stocks: number;
  stocks: StockData[];
}

const StockList: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<StockDataStatus | null>(null);
  const [searchText, setSearchText] = useState('');
  const [filters, setFilters] = useState<{
    market: string[];
    dataComplete: (string | number | boolean)[];
  }>({
    market: [],
    dataComplete: []
  });

  useEffect(() => {
    fetchStockDataStatus();
  }, []);

  const fetchStockDataStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/stocks/data-status');
      const result = await response.json();

      if (result.error) {
        setError(result.error);
      } else {
        setData(result);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取股票数据状态失败');
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<StockData> = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120,
      fixed: 'left',
      render: (symbol: string) => <strong>{symbol}</strong>,
      filteredValue: searchText ? [searchText] : null,
      onFilter: (value, record) =>
        record.symbol.toLowerCase().includes(value.toString().toLowerCase()) ||
        record.name.toLowerCase().includes(value.toString().toLowerCase())
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      width: 150
    },
    {
      title: '市场',
      dataIndex: 'market',
      key: 'market',
      width: 100,
      filters: [
        { text: 'SZ', value: 'SZ' },
        { text: 'SH', value: 'SH' }
      ],
      filteredValue: filters.market,
      onFilter: (value, record) => record.market === value
    },
    {
      title: 'K线天数',
      dataIndex: 'kline_days',
      key: 'kline_days',
      width: 120,
      sorter: (a, b) => a.kline_days - b.kline_days,
      render: (days: number) => days.toLocaleString()
    },
    {
      title: '最早日期',
      dataIndex: 'earliest_date',
      key: 'earliest_date',
      width: 120
    },
    {
      title: '最新日期',
      dataIndex: 'latest_date',
      key: 'latest_date',
      width: 120
    },
    {
      title: '因子天数',
      dataIndex: 'factor_days',
      key: 'factor_days',
      width: 120,
      sorter: (a, b) => a.factor_days - b.factor_days,
      render: (days: number) => days.toLocaleString()
    },
    {
      title: '因子数量',
      dataIndex: 'factor_count',
      key: 'factor_count',
      width: 120,
      sorter: (a, b) => a.factor_count - b.factor_count
    },
    {
      title: '数据状态',
      dataIndex: 'data_complete',
      key: 'data_complete',
      width: 120,
      fixed: 'right',
      filters: [
        { text: '完整', value: true },
        { text: '不完整', value: false }
      ],
      filteredValue: filters.dataComplete,
      onFilter: (value, record) => record.data_complete === value,
      render: (complete: boolean) => (
        complete ? (
          <Tag icon={<CheckCircleOutlined />} color="success">完整</Tag>
        ) : (
          <Tag icon={<CloseCircleOutlined />} color="error">不完整</Tag>
        )
      )
    }
  ];

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

  if (!data) {
    return <Alert message="无数据" type="warning" showIcon />;
  }

  const completionRate = data.total_stocks > 0
    ? (data.complete_stocks / data.total_stocks * 100).toFixed(1)
    : '0';

  return (
    <div style={{ padding: '24px' }}>
      <h1>股票列表管理</h1>

      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总股票数"
              value={data.total_stocks}
              suffix="只"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="数据完整"
              value={data.complete_stocks}
              suffix="只"
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="数据不完整"
              value={data.incomplete_stocks}
              suffix="只"
              valueStyle={{ color: '#cf1322' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="完整率"
              value={completionRate}
              suffix="%"
              valueStyle={{
                color: parseFloat(completionRate) >= 90 ? '#3f8600' :
                       parseFloat(completionRate) >= 70 ? '#faad14' : '#cf1322'
              }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="股票数据详情"
        extra={
          <Input
            placeholder="搜索股票代码或名称"
            prefix={<SearchOutlined />}
            style={{ width: 250 }}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
        }
      >
        <Table
          columns={columns}
          dataSource={data.stocks}
          rowKey={(record) => record.symbol}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 只股票` }}
          scroll={{ x: 1200 }}
          onChange={(pagination, filters) => {
            setFilters({
              market: (filters.market as string[]) || [],
              dataComplete: (filters.data_complete as (string | number | boolean)[]) || []
            });
          }}
        />
      </Card>
    </div>
  );
};

export default StockList;
