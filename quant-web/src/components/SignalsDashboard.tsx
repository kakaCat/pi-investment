import React, { useEffect, useState } from 'react'
import { Card, Spin, Alert, Typography, Table, Tag, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Title, Text } = Typography

interface Signal {
  symbol: string
  action: 'BUY' | 'SELL'
  reason: string
  confidence: number
  price: number
  date: string
}

const SignalsDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])

  useEffect(() => {
    fetchSignals()
  }, [])

  const fetchSignals = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await axios.get('/api/signals')
      // API returns { signals: { signals: [...] } }, extract the array
      setSignals(response.data.signals?.signals || [])
    } catch (err: any) {
      setError(err.response?.data?.error || '获取信号失败')
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (action: string) => (
        <Tag color={action === 'BUY' ? 'green' : 'red'}>
          {action === 'BUY' ? '📈 买入' : '📉 卖出'}
        </Tag>
      )
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason'
    },
    {
      title: '信心度',
      dataIndex: 'confidence',
      key: 'confidence',
      render: (confidence: number) => `${(confidence * 100).toFixed(0)}%`,
      sorter: (a: Signal, b: Signal) => b.confidence - a.confidence
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => `¥${price.toFixed(2)}`
    },
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date'
    }
  ]

  const buySignals = signals.filter(s => s.action === 'BUY')
  const sellSignals = signals.filter(s => s.action === 'SELL')

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>加载交易信号...</div>
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        message="加载失败"
        description={error}
        type="error"
        showIcon
      />
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={2}>📡 交易信号</Title>
          <Text type="secondary">实时量化交易信号</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={fetchSignals}>
          刷新
        </Button>
      </div>

      {/* 统计 */}
      <div style={{ marginTop: 24, marginBottom: 24 }}>
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-around' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, fontWeight: 'bold', color: '#52c41a' }}>
                {buySignals.length}
              </div>
              <div>买入信号</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, fontWeight: 'bold', color: '#ff4d4f' }}>
                {sellSignals.length}
              </div>
              <div>卖出信号</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, fontWeight: 'bold' }}>
                {signals.length}
              </div>
              <div>总信号数</div>
            </div>
          </div>
        </Card>
      </div>

      {/* 买入信号 */}
      {buySignals.length > 0 && (
        <Card title="📈 买入信号" style={{ marginBottom: 24 }}>
          <Table
            dataSource={buySignals}
            columns={columns}
            rowKey={(record) => `${record.symbol}-${record.date}`}
            pagination={{ pageSize: 10 }}
          />
        </Card>
      )}

      {/* 卖出信号 */}
      {sellSignals.length > 0 && (
        <Card title="📉 卖出信号">
          <Table
            dataSource={sellSignals}
            columns={columns}
            rowKey={(record) => `${record.symbol}-${record.date}`}
            pagination={{ pageSize: 10 }}
          />
        </Card>
      )}

      {signals.length === 0 && (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Text type="secondary">暂无交易信号</Text>
          </div>
        </Card>
      )}
    </div>
  )
}

export default SignalsDashboard
