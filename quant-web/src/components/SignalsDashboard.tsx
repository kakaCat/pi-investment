import React, { useEffect, useState } from 'react'
import { Card, Spin, Alert, Typography, Table, Tag, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Title, Text } = Typography

interface Signal {
  symbol: string
  name?: string
  signal: 'BUY' | 'SELL'  // API返回的字段名
  reason: string
  confidence: number
  price: number
  date: string
  strategy?: string
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
      // API returns { signals: [...] }
      setSignals(response.data.signals || [])
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
      dataIndex: 'signal',
      key: 'signal',
      render: (signal: string) => (
        <Tag color={signal === 'BUY' ? 'green' : 'red'}>
          {signal === 'BUY' ? '📈 买入' : '📉 卖出'}
        </Tag>
      )
    },
    {
      title: '策略',
      dataIndex: 'strategy',
      key: 'strategy',
      width: 120
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
      render: (confidence: number) => confidence != null ? `${(confidence * 100).toFixed(0)}%` : '-',
      sorter: (a: Signal, b: Signal) => (b.confidence || 0) - (a.confidence || 0)
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => price != null ? `¥${price.toFixed(2)}` : '-'
    },
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date'
    }
  ]

  const buySignals = signals.filter(s => s.signal === 'BUY')
  const sellSignals = signals.filter(s => s.signal === 'SELL')

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
          <div style={{ display: 'flex', justifyContent: 'space-around', gap: '20px' }}>
            <div style={{
              flex: 1,
              padding: '20px',
              background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
              borderRadius: '12px',
              border: '2px solid #bae6fd'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 48, fontWeight: 'bold', color: '#0ea5e9', marginBottom: 8 }}>
                  {buySignals.length}
                </div>
                <div style={{ fontSize: 16, color: '#0369a1', fontWeight: 500 }}>📈 买入信号</div>
                {signals.length > 0 && (
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                    占比 {((buySignals.length / signals.length) * 100).toFixed(1)}%
                  </div>
                )}
              </div>
              {buySignals.length > 0 && (
                <div style={{
                  marginTop: 16,
                  paddingTop: 16,
                  borderTop: '1px solid #bae6fd',
                  textAlign: 'left',
                  maxHeight: '120px',
                  overflowY: 'auto'
                }}>
                  <div style={{ fontSize: 12, color: '#0369a1', fontWeight: 500, marginBottom: 8 }}>股票列表：</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {buySignals.map((signal, idx) => (
                      <span key={idx} style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        background: '#e0f2fe',
                        color: '#0369a1',
                        borderRadius: '4px',
                        border: '1px solid #7dd3fc'
                      }}>
                        {signal.symbol} {signal.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div style={{
              flex: 1,
              padding: '20px',
              background: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
              borderRadius: '12px',
              border: '2px solid #fecaca'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 48, fontWeight: 'bold', color: '#ef4444', marginBottom: 8 }}>
                  {sellSignals.length}
                </div>
                <div style={{ fontSize: 16, color: '#b91c1c', fontWeight: 500 }}>📉 卖出信号</div>
                {signals.length > 0 && (
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                    占比 {((sellSignals.length / signals.length) * 100).toFixed(1)}%
                  </div>
                )}
              </div>
              {sellSignals.length > 0 && (
                <div style={{
                  marginTop: 16,
                  paddingTop: 16,
                  borderTop: '1px solid #fecaca',
                  textAlign: 'left',
                  maxHeight: '120px',
                  overflowY: 'auto'
                }}>
                  <div style={{ fontSize: 12, color: '#b91c1c', fontWeight: 500, marginBottom: 8 }}>股票列表：</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {sellSignals.map((signal, idx) => (
                      <span key={idx} style={{
                        fontSize: 11,
                        padding: '2px 8px',
                        background: '#fee2e2',
                        color: '#b91c1c',
                        borderRadius: '4px',
                        border: '1px solid #fca5a5'
                      }}>
                        {signal.symbol} {signal.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div style={{
              textAlign: 'center',
              flex: 1,
              padding: '20px',
              background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
              borderRadius: '12px',
              border: '2px solid #cbd5e1'
            }}>
              <div style={{ fontSize: 48, fontWeight: 'bold', color: '#475569', marginBottom: 8 }}>
                {signals.length}
              </div>
              <div style={{ fontSize: 16, color: '#334155', fontWeight: 500 }}>📊 总信号数</div>
              <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                最近30天
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* 买入信号 */}
      {buySignals.length > 0 && (
        <Card
          title={<span style={{ fontSize: 18, fontWeight: 600 }}>📈 买入信号</span>}
          style={{ marginBottom: 24 }}
          headStyle={{ background: '#f0f9ff', borderBottom: '2px solid #0ea5e9' }}
        >
          <Table
            dataSource={buySignals}
            columns={columns}
            rowKey={(record) => `${record.symbol}-${record.date}`}
            pagination={{ pageSize: 10 }}
            rowClassName={() => 'hover:bg-blue-50'}
          />
        </Card>
      )}

      {/* 卖出信号 */}
      {sellSignals.length > 0 && (
        <Card
          title={<span style={{ fontSize: 18, fontWeight: 600 }}>📉 卖出信号</span>}
          headStyle={{ background: '#fef2f2', borderBottom: '2px solid #ef4444' }}
        >
          <Table
            dataSource={sellSignals}
            columns={columns}
            rowKey={(record) => `${record.symbol}-${record.date}`}
            pagination={{ pageSize: 10 }}
            rowClassName={() => 'hover:bg-red-50'}
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
