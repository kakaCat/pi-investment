import React, { useState } from 'react'
import { Card, Input, Button, Spin, Alert, Typography, Row, Col, Statistic, Table, Tag } from 'antd'
import { SearchOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'
import axios from 'axios'

const { Title, Text } = Typography

interface Factor {
  name: string
  value: number
  importance: number
  contribution: number
}

interface StockAnalysisData {
  symbol: string
  date: string
  price: number
  prediction: {
    up_probability: number
    direction: 'UP' | 'DOWN'
    confidence: number
  }
  key_factors: Factor[]
}

const StockAnalysis: React.FC = () => {
  const [symbol, setSymbol] = useState('000001')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<StockAnalysisData | null>(null)

  const handleSearch = async () => {
    if (!symbol.trim()) {
      setError('请输入股票代码')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await axios.get(`/api/stock/${symbol}/factors`)
      setData(response.data)
    } catch (err: any) {
      setError(err.response?.data?.error || '获取数据失败')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: '因子名称',
      dataIndex: 'name',
      key: 'name',
      width: 150
    },
    {
      title: '当前值',
      dataIndex: 'value',
      key: 'value',
      render: (value: number) => value.toFixed(4)
    },
    {
      title: '贡献度',
      dataIndex: 'contribution',
      key: 'contribution',
      render: (value: number) => (
        <span style={{ color: value > 0 ? '#52c41a' : '#ff4d4f' }}>
          {value > 0 ? '+' : ''}{value.toFixed(4)}
        </span>
      ),
      sorter: (a: Factor, b: Factor) => Math.abs(b.contribution) - Math.abs(a.contribution)
    },
    {
      title: '方向',
      dataIndex: 'contribution',
      key: 'direction',
      render: (value: number) => (
        <Tag color={value > 0 ? 'green' : 'red'}>
          {value > 0 ? '📈 看涨' : '📉 看跌'}
        </Tag>
      )
    }
  ]

  return (
    <div>
      <Title level={2}>📈 股票因子分析</Title>
      <Text type="secondary">分析单只股票的因子贡献，了解预测依据</Text>

      {/* 搜索框 */}
      <Card style={{ marginTop: 24 }}>
        <Input.Search
          placeholder="输入股票代码，如 000001、600036"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onSearch={handleSearch}
          enterButton={<Button type="primary" icon={<SearchOutlined />}>分析</Button>}
          size="large"
          loading={loading}
        />
      </Card>

      {/* 错误提示 */}
      {error && (
        <Alert
          message="分析失败"
          description={error}
          type="error"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}

      {/* 加载中 */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>分析中...</div>
        </div>
      )}

      {/* 分析结果 */}
      {data && !loading && (
        <>
          {/* 预测结果 */}
          <Row gutter={16} style={{ marginTop: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="股票代码"
                  value={data.symbol}
                  valueStyle={{ fontSize: 20 }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="当前价格"
                  value={data.price}
                  precision={2}
                  prefix="¥"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="上涨概率"
                  value={data.prediction.up_probability * 100}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: data.prediction.direction === 'UP' ? '#3f8600' : '#cf1322' }}
                  prefix={data.prediction.direction === 'UP' ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="置信度"
                  value={data.prediction.confidence * 100}
                  precision={2}
                  suffix="%"
                />
              </Card>
            </Col>
          </Row>

          {/* 预测方向 */}
          <Card style={{ marginTop: 16 }}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <Title level={3} style={{ margin: 0 }}>
                {data.prediction.direction === 'UP' ? '📈 看涨信号' : '📉 看跌信号'}
              </Title>
              <Text type="secondary">
                分析日期: {data.date}
              </Text>
            </div>
          </Card>

          {/* 关键因子表格 */}
          <Card title="🔍 关键因子贡献 (Top 10)" style={{ marginTop: 24 }}>
            <Table
              dataSource={data.key_factors.slice(0, 10)}
              columns={columns}
              rowKey="name"
              pagination={false}
            />
          </Card>

          {/* 因子贡献柱状图 */}
          <Card title="📊 因子贡献可视化" style={{ marginTop: 24 }}>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={data.key_factors.slice(0, 10)} layout="vertical" margin={{ left: 120 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="name" />
                <Tooltip
                  formatter={(value: number) => [value.toFixed(4), '贡献度']}
                />
                <Legend />
                <Bar
                  dataKey="contribution"
                  fill="#1890ff"
                  name="贡献度"
                  label={{ position: 'right', formatter: (value: number) => value.toFixed(3) }}
                />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* 雷达图 */}
          <Card title="🎯 Top 6 因子雷达图" style={{ marginTop: 24 }}>
            <ResponsiveContainer width="100%" height={400}>
              <RadarChart data={data.key_factors.slice(0, 6).map(f => ({
                factor: f.name,
                contribution: Math.abs(f.contribution) * 100
              }))}>
                <PolarGrid />
                <PolarAngleAxis dataKey="factor" />
                <PolarRadiusAxis />
                <Radar name="贡献度" dataKey="contribution" stroke="#1890ff" fill="#1890ff" fillOpacity={0.6} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}
    </div>
  )
}

export default StockAnalysis
