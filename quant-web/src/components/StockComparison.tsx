import React, { useState } from 'react'
import { Card, Input, Button, Spin, Alert, Typography, Table, Tag, Space } from 'antd'
import { PlusOutlined, DeleteOutlined, SwapOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Title, Text } = Typography

interface StockData {
  symbol: string
  date: string
  price: number
  prediction: {
    up_probability: number
    direction: 'UP' | 'DOWN'
    confidence: number
  }
  key_factors: Array<{
    name: string
    value: number
    contribution: number
  }>
}

const StockComparison: React.FC = () => {
  const [symbols, setSymbols] = useState<string[]>(['000001', '600036'])
  const [inputSymbol, setInputSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<StockData[]>([])

  const handleAddSymbol = () => {
    if (!inputSymbol.trim()) return
    if (symbols.includes(inputSymbol)) {
      setError('股票已存在')
      return
    }
    if (symbols.length >= 5) {
      setError('最多对比5只股票')
      return
    }
    setSymbols([...symbols, inputSymbol])
    setInputSymbol('')
    setError(null)
  }

  const handleRemoveSymbol = (symbol: string) => {
    setSymbols(symbols.filter(s => s !== symbol))
  }

  const handleCompare = async () => {
    if (symbols.length < 2) {
      setError('至少需要2只股票')
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await axios.post('/api/stocks/compare', { symbols })
      setData(response.data.comparisons)
    } catch (err: any) {
      setError(err.response?.data?.error || '对比失败')
      setData([])
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: '排名',
      key: 'rank',
      width: 80,
      render: (_: any, __: any, index: number) => (
        <Tag color={index === 0 ? 'gold' : index === 1 ? 'silver' : 'default'}>
          {index + 1}
        </Tag>
      )
    },
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => `¥${price.toFixed(2)}`
    },
    {
      title: '上涨概率',
      key: 'probability',
      render: (record: StockData) => (
        <span style={{ color: record.prediction.direction === 'UP' ? '#52c41a' : '#ff4d4f', fontWeight: 'bold' }}>
          {(record.prediction.up_probability * 100).toFixed(2)}%
        </span>
      ),
      sorter: (a: StockData, b: StockData) => b.prediction.up_probability - a.prediction.up_probability
    },
    {
      title: '方向',
      key: 'direction',
      render: (record: StockData) => (
        <Tag color={record.prediction.direction === 'UP' ? 'green' : 'red'}>
          {record.prediction.direction === 'UP' ? '📈 看涨' : '📉 看跌'}
        </Tag>
      )
    },
    {
      title: '置信度',
      key: 'confidence',
      render: (record: StockData) => `${(record.prediction.confidence * 100).toFixed(2)}%`
    },
    {
      title: '关键因子',
      key: 'factors',
      render: (record: StockData) => (
        <div>
          {record.key_factors.slice(0, 3).map((factor, idx) => (
            <div key={idx} style={{ fontSize: 12 }}>
              {factor.contribution > 0 ? '📈' : '📉'} {factor.name}: {factor.contribution.toFixed(3)}
            </div>
          ))}
        </div>
      )
    }
  ]

  return (
    <div>
      <Title level={2}>🔍 股票对比分析</Title>
      <Text type="secondary">对比多只股票的因子，选择最优标的</Text>

      {/* 添加股票 */}
      <Card title="📝 选择股票" style={{ marginTop: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Input
              placeholder="输入股票代码"
              value={inputSymbol}
              onChange={(e) => setInputSymbol(e.target.value)}
              onPressEnter={handleAddSymbol}
              style={{ width: 200 }}
            />
            <Button icon={<PlusOutlined />} onClick={handleAddSymbol}>
              添加
            </Button>
          </Space>

          <div>
            <Text strong>已选股票 ({symbols.length}/5):</Text>
            <div style={{ marginTop: 8 }}>
              {symbols.map(symbol => (
                <Tag
                  key={symbol}
                  closable
                  onClose={() => handleRemoveSymbol(symbol)}
                  style={{ marginBottom: 8 }}
                >
                  {symbol}
                </Tag>
              ))}
            </div>
          </div>

          <Button
            type="primary"
            icon={<SwapOutlined />}
            onClick={handleCompare}
            loading={loading}
            disabled={symbols.length < 2}
          >
            开始对比
          </Button>
        </Space>
      </Card>

      {/* 错误提示 */}
      {error && (
        <Alert
          message="对比失败"
          description={error}
          type="error"
          showIcon
          style={{ marginTop: 16 }}
          closable
          onClose={() => setError(null)}
        />
      )}

      {/* 加载中 */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>对比分析中...</div>
        </div>
      )}

      {/* 对比结果 */}
      {data.length > 0 && !loading && (
        <>
          <Card title="🏆 对比结果" style={{ marginTop: 24 }}>
            <Table
              dataSource={data}
              columns={columns}
              rowKey="symbol"
              pagination={false}
            />
          </Card>

          {/* 投资建议 */}
          <Card title="💡 投资建议" style={{ marginTop: 24 }}>
            <div>
              <Text strong>首选: </Text>
              <Text style={{ fontSize: 16, color: '#52c41a' }}>
                {data[0].symbol} (上涨概率 {(data[0].prediction.up_probability * 100).toFixed(2)}%)
              </Text>
            </div>
            <div style={{ marginTop: 8 }}>
              <Text strong>关键优势: </Text>
              <Text>
                {data[0].key_factors.slice(0, 2).map(f =>
                  `${f.name}(${f.contribution > 0 ? '+' : ''}${f.contribution.toFixed(3)})`
                ).join('、')}
              </Text>
            </div>
            {data.length > 1 && (
              <div style={{ marginTop: 8 }}>
                <Text strong>次选: </Text>
                <Text>
                  {data[1].symbol} (上涨概率 {(data[1].prediction.up_probability * 100).toFixed(2)}%)
                </Text>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}

export default StockComparison
